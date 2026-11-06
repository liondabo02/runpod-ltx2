"""Opt-in local 1.5B inference, sharing Foundry's OS lock; never downloads."""
import ctypes
import json
import os
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from .llm_executor import ModelError

MODEL = 'qwen2.5-coder:1.5b'
BASE = 'http://127.0.0.1:11434/v1'
LOCK = Path(os.environ.get('USERPROFILE', 'C:/Users/esmak')) / 'Downloads/harun-ai-foundry/harun-ai-foundry/data/operations/local-inference.lock'


def memory_available():
    class Memory(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [(name, ctypes.c_ulonglong) for name in ('total','available','total_page','available_page','total_virtual','available_virtual','extended')]
    state=Memory();state.length=ctypes.sizeof(state)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
        return 0
    return state.available


@contextmanager
def inference_lock():
    import msvcrt
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open('a+b') as handle:
        if handle.seek(0, 2) == 0:handle.write(b'0');handle.flush()
        handle.seek(0)
        acquired=False
        try:
            try:msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1);acquired=True
            except OSError:pass
            yield acquired
        finally:
            if acquired:
                handle.seek(0);msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ModelError('Yerel model yönlendirmesi reddedildi')


def request(endpoint, body=None, timeout=5):
    if endpoint not in ('tags', 'generate'):raise ModelError('Geçersiz yerel işlem')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    query=urllib.request.Request('http://127.0.0.1:11434/api/'+endpoint,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json'})
    try:
        with opener.open(query, timeout=timeout) as response:
            raw=response.read(65537)
        if len(raw)>65536:raise ModelError('Yerel yanıt boyut sınırı')
        return json.loads(raw)
    except ModelError:raise
    except Exception as exc:raise ModelError('Yerel model erişimi: '+type(exc).__name__) from exc


def transport(system, prompt, settings):
    if settings.base_url.rstrip('/') != BASE or settings.model != MODEL:
        raise ModelError('Bu yerel işçi yalnız sabit localhost ve kurulu 1.5B modeli kullanır')
    if len(system)+len(prompt)>12000:raise ModelError('Yerel bağlam sınırı; görev bölünmeli')
    with inference_lock() as acquired:
        if not acquired:raise ModelError('Yerel model başka görevde; tekrar denemek için bekle')
        if memory_available()<2*1024**3:raise ModelError('En az 2 GiB kullanılabilir RAM gerekli')
        tags=request('tags')
        if not any(row.get('name')==MODEL for row in tags.get('models',[])):
            raise ModelError('Yerel model kurulu değil; otomatik indirme yapılmadı')
        body=dict(model=MODEL,system=system,prompt=prompt,format='json',stream=False,keep_alive=0,
                  options=dict(num_ctx=4096,num_predict=1024,temperature=0))
        result=request('generate',body,timeout=min(settings.timeout_seconds,90))
        if result.get('done') is not True or result.get('done_reason')=='length':
            raise ModelError('Yerel model çıktısı tamamlanmadı')
        answer=result.get('response')
        if not isinstance(answer,str) or not answer.strip():raise ModelError('Yerel model boş yanıt verdi')
        return answer
