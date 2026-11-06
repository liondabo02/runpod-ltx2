"""Bounded execution of trusted operator commands. No shell, no model calls.

Windows bootstrap waits for the parent to attach it to a kill-on-close job
BEFORE starting the target command. Failing to establish ownership fails closed.
Job handles are not inherited; parent crash closes the job and kills children.
This is lifetime containment, not isolation from files, network or user rights.
"""
from __future__ import annotations
import math,os,signal,subprocess,sys,tempfile,time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

class _Scratch(tempfile.TemporaryDirectory):
    def cleanup(self):
        # Windows may retire inherited file handles slightly after job accounting
        # reaches zero. Retry only our own temporary directory, with a deadline.
        target=Path(self.name).absolute()
        base=Path(tempfile.gettempdir()).absolute()
        if target.parent!=base or not target.name.startswith('q99-process-'):
            raise RuntimeError('unexpected cleanup target')
        for attempt in range(20):
            try:
                return super().cleanup()
            except PermissionError:
                if attempt==19:raise
                time.sleep(.05)

@dataclass(frozen=True)
class ProcessResult:
    status:str
    exit_code:int|None
    duration:float
    output:str
    cleanup_verified:bool

def run_bounded(command:list[str],*,cwd:str|Path,timeout:float=60,cancelled:Callable[[],bool]|None=None,memory_bytes:int=256*1024*1024,max_output_bytes:int=1024*1024,env:dict[str,str]|None=None)->ProcessResult:
    if not command or any(not isinstance(v,str) or '\0' in v for v in command):raise ValueError('invalid argv')
    if not math.isfinite(timeout) or not 0<timeout<=600:raise ValueError('invalid timeout')
    if not 16*1024*1024<=memory_bytes<=512*1024*1024:raise ValueError('invalid memory limit')
    if not 1024<=max_output_bytes<=4*1024*1024:raise ValueError('invalid output limit')
    root=Path(cwd).resolve(strict=True)
    if not root.is_dir():raise ValueError('cwd must be a directory')
    started=time.monotonic();proc=None;job=None;clean=True;status='unavailable';code=None
    safe_env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','COMSPEC','PATHEXT','LOCALAPPDATA'}}
    safe_env.update(env or {});safe_env['PYTHONIOENCODING']='utf-8'
    bootstrap="import sys,subprocess; token=sys.stdin.buffer.read(1); sys.exit(125) if token!=b'1' else None; p=subprocess.Popen(sys.argv[1:],stdin=subprocess.DEVNULL); sys.exit(p.wait())"
    with _Scratch(prefix='q99-process-') as tmp:
        paths=[Path(tmp)/'out',Path(tmp)/'err']
        with paths[0].open('wb') as out,paths[1].open('wb') as err:
            try:
                if cancelled and cancelled():return ProcessResult('cancelled',None,0,'',True)
                if os.name=='nt':
                    from .studio_process_job import WindowsJob
                    job=WindowsJob(memory_bytes)
                proc=subprocess.Popen([sys.executable,'-I','-c',bootstrap,*command],cwd=root,env=safe_env,stdin=subprocess.PIPE,stdout=out,stderr=err,start_new_session=os.name!='nt',creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                if job:job.assign(proc)
                proc.stdin.write(b'1');proc.stdin.flush();proc.stdin.close()
                while True:
                    code=proc.poll()
                    if sum(p.stat().st_size for p in paths)>max_output_bytes:status='output_limit';break
                    if cancelled and cancelled():status='cancelled';break
                    if time.monotonic()-started>=timeout:status='timeout';break
                    if code is not None:status='passed' if code==0 else 'failed';break
                    time.sleep(.02)
            except (OSError,ValueError):status='unavailable'
            finally:
                if job:clean=job.close()
                elif proc and os.name!='nt':
                    try:os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                if proc:
                    try:
                        if proc.poll() is None:proc.kill()
                        proc.wait(timeout=3)
                    except (OSError,subprocess.TimeoutExpired):clean=False
                if not clean:status='cleanup_unverified'
        chunks=[]
        for path in paths:
            with path.open('rb') as stream:
                stream.seek(max(0,path.stat().st_size-2000));chunks.append(stream.read(2000).decode('utf-8','replace'))
        return ProcessResult(status,code,round(time.monotonic()-started,3),'\n'.join(chunks),clean)

