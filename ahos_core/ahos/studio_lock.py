"""Nonblocking process ownership; never remove another writer's lock file."""
from contextlib import contextmanager
from functools import wraps
import inspect,os,threading
from pathlib import Path

_threads={};_guard=threading.Lock()

@contextmanager
def file_lock(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with _guard:mutex=_threads.setdefault(str(path.absolute()).casefold(),threading.Lock())
    if not mutex.acquire(blocking=False):raise RuntimeError('Stüdyo yazıcısı meşgul')
    try:
        with path.open('a+b') as handle:
            handle.seek(0,2)
            if handle.tell()==0:handle.write(b'0');handle.flush()
            handle.seek(0);locked=False
            try:
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
                locked=True;yield
            finally:
                if locked:
                    handle.seek(0)
                    if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
                    else:fcntl.flock(handle,fcntl.LOCK_UN)
    finally:mutex.release()

def idea_writer(function):
    signature=inspect.signature(function)
    @wraps(function)
    def wrapped(*args,**kwargs):
        runtime=signature.bind(*args,**kwargs).arguments['runtime_dir']
        with file_lock(Path(runtime)/'ideas/.writer.lock'):return function(*args,**kwargs)
    return wrapped
