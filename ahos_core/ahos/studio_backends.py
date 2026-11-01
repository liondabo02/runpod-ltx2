"""Explicit zero-token-cost, self-hosted production adapters; never paid fallback."""
from __future__ import annotations
import copy,hashlib,json,sys,tempfile,time,urllib.parse,urllib.request,uuid
from pathlib import Path

class BackendUnavailable(RuntimeError):pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ValueError('Üretim isteği başka adrese yönlendirilemez')

class LocalHTTP:
    def __init__(self,base,*,timeout=8):
        u=urllib.parse.urlsplit(base)
        if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost','::1') or u.username or u.password or u.query or u.fragment:
            raise ValueError('Yalnız açıkça yapılandırılmış yerel/SSH tüneli uçları kullanılabilir')
        self.base=base.rstrip('/');self.timeout=timeout
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    def call(self,path,body=None,*,limit=2*1024*1024,raw=False,timeout=None,content_type='application/json'):
        if not path.startswith('/') or path.startswith('//'):raise ValueError('Geçersiz API yolu')
        payload=body if isinstance(body,bytes) else (None if body is None else json.dumps(body,ensure_ascii=False).encode())
        req=urllib.request.Request(self.base+path,data=payload,headers={'Content-Type':content_type})
        with self.opener.open(req,timeout=timeout or self.timeout) as r:
            # Redirects must not forward prompts to external services.
            if urllib.parse.urlsplit(r.url).netloc!=urllib.parse.urlsplit(self.base).netloc:raise ValueError('Uç yönlendirmesi reddedildi')
            value=r.read(limit+1)
        if len(value)>limit:raise ValueError('Sağlayıcı yanıtı boyut sınırını aştı')
        return value if raw else json.loads(value)
    def stream(self,path,body,tick,*,deadline=480):
        if path!='/api/generate':raise ValueError('Desteklenmeyen akış yolu')
        req=urllib.request.Request(self.base+path,data=json.dumps(body,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
        started=time.monotonic();total=0
        with self.opener.open(req,timeout=60) as response:
            while True:
                tick()
                if time.monotonic()-started>deadline:raise TimeoutError('Senaryo akış süresi doldu')
                line=response.readline(32769);total+=len(line)
                if len(line)>32768 or total>256*1024:raise ValueError('Model akış boyutu sınırı')
                if not line:break
                part=json.loads(line)
                if not isinstance(part,dict) or part.get('error'):raise BackendUnavailable('Model akışı başarısız')
                yield part
                if part.get('done') is True:break

class PiperSpeech:
    """Existing self-hosted Piper HTTP API. No downloads or silent voice fallback."""
    def __init__(self,config,http=None):
        self.config=config;self.http=http or LocalHTTP(config.get('base_url','http://127.0.0.1:5000'))
    def synthesize(self,text,voice,language,tick):
        if not text.strip() or len(text)>2000:raise ValueError('Konuşma metni sınırı')
        model=voice.get('model')
        info=self.http.call('/voices').get(model)
        if not info:raise BackendUnavailable('Onaylı Piper modeli sunucuda yok')
        code=info.get('language',{}).get('code','').split('_')[0]
        if code!=language:raise BackendUnavailable('Ses modelinin gerçek dili hedefle eşleşmiyor')
        tick();raw=self.http.call('/synthesize',dict(text=text,voice=model),raw=True,limit=8*1024*1024,timeout=60);tick()
        if raw[:4]!=b'RIFF' or raw[8:12]!=b'WAVE':raise BackendUnavailable('Sentezlenmiş WAV alınamadı')
        return raw

class OwnedStory:
    def __init__(self,base='http://127.0.0.1:11500',model='qwen2.5-coder:3b',http=None,lock_path=None,capacity_probe=None):
        if model not in ('qwen2.5-coder:3b','qwen2.5-coder:7b'):raise ValueError('Model açıkça doğrulanmış sahip modeli değil')
        self.http=http or LocalHTTP(base);self.model=model
        self.lock_path=Path(lock_path) if lock_path else Path.home()/'Downloads/harun-ai-foundry/harun-ai-foundry/data/operations/local-inference.lock'
        if capacity_probe is not None and not callable(capacity_probe):raise ValueError('Geçersiz kapasite denetleyicisi')
        self.capacity_probe=capacity_probe
    def capacity(self):
        if self.capacity_probe:return self.capacity_probe()
        foundry=self.lock_path.parents[2]
        if not (foundry/'scripts/oracle_ssh_transport.py').is_file():raise BackendUnavailable('Sahip kapasite denetimi bağlı değil')
        sys.path.insert(0,str(foundry/'scripts'))
        from oracle_ssh_transport import exchange
        with tempfile.TemporaryDirectory(prefix='ahos-studio-probe-') as folder:
            return exchange({'action':'probe'},Path(folder)/'probe',timeout=20)
    def generate(self,prompt,tick):
        from .studio_lock import file_lock
        if not self.lock_path.parent.is_dir():raise BackendUnavailable('Ortak sahip model kilidi bulunamadı')
        with file_lock(self.lock_path):return self._generate(prompt,tick)
    def _generate(self,prompt,tick):
        tick()
        tags=self.http.call('/api/tags')
        if self.model not in {m.get('name') for m in tags.get('models',[])}:raise BackendUnavailable('Sahip senaryo modeli kullanılamıyor')
        capacity=self.capacity()
        if capacity.get('ready') is not True:raise BackendUnavailable('Sahip sunucuda kapasite veya başka model işi engeli; yeni üretim başlatılmadı')
        if len(prompt)>14000:raise ValueError('Senaryo bağlam sınırı')
        pieces=[];result={}
        request=dict(model=self.model,prompt=prompt,stream=True,format='json',
            keep_alive='30s',options=dict(temperature=.25,num_predict=1400,num_ctx=4096,num_thread=1))
        for part in self.http.stream('/api/generate',request,tick,deadline=480):
            result=part;text=part.get('response','')
            if not isinstance(text,str):raise ValueError('Geçersiz model akış parçası')
            pieces.append(text)
        tick()
        if result.get('done') is not True or result.get('done_reason')=='length' or result.get('model')!=self.model:raise BackendUnavailable('Senaryo modelinden tamamlanmış sonuç alınmadı')
        self.metrics={k:result.get(k) for k in ('model','eval_count','prompt_eval_count','total_duration')}
        return json.loads(''.join(pieces))

class ComfyProduction:
    """Submit one owned job. Never call global interrupt/free/queue clear routes."""
    def __init__(self,config,http=None):
        self.config=config;self.http=http or LocalHTTP(config.get('base_url','http://127.0.0.1:8188'))
    def produce(self,kind,text,folder,tick,*,timeout=180,references=()):
        spec=self.config.get('workflows',{}).get(kind)
        if not isinstance(spec,dict):raise BackendUnavailable(kind+' için onaylı ComfyUI iş akışı bağlı değil')
        if spec.get('paid_usd')!=0:raise BackendUnavailable('Görsel sağlayıcısının sıfır bütçesi doğrulanmadı')
        workflow=copy.deepcopy(spec.get('graph',{}));allowed=spec.get('allowed_nodes',[])
        if not workflow or not allowed or len(workflow)>100:raise ValueError('Üretim grafiği/izin verilen düğümler eksik')
        for node in workflow.values():
            if node.get('class_type') not in allowed:raise ValueError('İzin verilmeyen ComfyUI düğümü')
        target=spec.get('text_input',[])
        if len(target)!=2 or target[0] not in workflow:raise ValueError('Metin girdisi bağlantısı eksik')
        if len(text)>6000:raise ValueError('Görsel istemi sınırı')
        workflow[target[0]]['inputs'][target[1]]=text
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
        refs=[Path(p) for p in references]
        if len(refs)>24 or any(p.stat().st_size>16*1024*1024 for p in refs):raise ValueError('Referans görsel boyut/adet sınırı')
        request_hash=hashlib.sha256(json.dumps(dict(graph=workflow,refs=[hashlib.sha256(p.read_bytes()).hexdigest() for p in refs]),sort_keys=True).encode()).hexdigest()
        journal=folder/'comfy-job.json'
        tick();self.http.call('/system_stats')
        if journal.exists():
            job=json.loads(journal.read_text())
            if job.get('request_sha256')!=request_hash:raise ValueError('Uzak iş girdisi değişti; yeniden planlama gerekli')
            ident=job['prompt_id']
        else:
            bindings=spec.get('reference_inputs',[])
            if len(bindings)!=len(refs):raise BackendUnavailable('Referans görselleri üretim düğümlerine tam bağlanmamış')
            for path,binding in zip(refs,bindings):
                if len(binding)!=2 or binding[0] not in workflow:raise ValueError('Referans girdi bağlantısı geçersiz')
                content=path.read_bytes();boundary='ahos'+uuid.uuid4().hex
                filename='ahos-'+hashlib.sha256(content).hexdigest()+'.png'
                body=(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{filename}"\r\nContent-Type: image/png\r\n\r\n'.encode()+content+f'\r\n--{boundary}--\r\n'.encode())
                uploaded=self.http.call('/upload/image',body,content_type='multipart/form-data; boundary='+boundary)
                name=uploaded.get('name','');sub=uploaded.get('subfolder','')
                if '/' in name or '\\' in name or name in ('','.','..') or '..' in Path(sub).parts or '\\' in sub or sub.startswith('/') or ':' in sub:raise ValueError('Yüklenen referans yolu geçersiz')
                workflow[binding[0]]['inputs'][binding[1]]=(sub+'/' if sub else '')+name
            answer=self.http.call('/prompt',dict(prompt=workflow,client_id='ahos-studio-'+uuid.uuid4().hex))
            ident=answer.get('prompt_id')
            if not isinstance(ident,str) or not ident or len(ident)>100:raise BackendUnavailable('Görsel işi kabul edilmedi')
            journal.write_text(json.dumps(dict(prompt_id=ident,request_sha256=request_hash,paid_usd=0)))
        started=time.monotonic()
        while time.monotonic()-started<timeout:
            tick();history=self.http.call('/history/'+urllib.parse.quote(ident,safe=''))
            entry=history.get(ident,{})
            status=entry.get('status',{})
            if status.get('status_str')=='error':raise BackendUnavailable('Görsel üretim işi başarısız; iş kimliği korundu')
            if status.get('completed') is True:
                outputs=entry.get('outputs',{}).get(str(spec.get('output_node')),{}).get(spec.get('output_key','images'),[])
                if not outputs:raise BackendUnavailable('Üretim tamamlandı ancak beklenen medya yok')
                data=outputs[0];name=data.get('filename','');sub=data.get('subfolder','')
                if not isinstance(name,str) or '/' in name or '\\' in name or name in ('','.','..') or '..' in Path(sub).parts or '\\' in sub or sub.startswith('/') or ':' in sub:
                    raise ValueError('Sağlayıcı dosya yolu reddedildi')
                if data.get('type')!='output':raise ValueError('Yalnız üretim çıktısı alınabilir')
                query=urllib.parse.urlencode(dict(filename=name,subfolder=sub,type='output'))
                raw=self.http.call('/view?'+query,raw=True,limit=32*1024*1024)
                path=folder/('generated.png' if kind=='image' else 'generated.mp4');path.write_bytes(raw)
                tick();return path
            time.sleep(.5)
        raise BackendUnavailable('Uzak üretim süresi doldu; aynı iş kimliği saklandı, ikinci iş başlatılmadı')

def load_config(runtime):
    path=Path(runtime)/'studio-production-config.json'
    if not path.is_file():return {}
    if path.stat().st_size>256*1024:raise ValueError('Stüdyo yapılandırması çok büyük')
    body=json.loads(path.read_text(encoding='utf-8-sig'))
    if body.get('paid_usd')!=0:raise ValueError('Stüdyo için sıfır bütçe şartı sağlanmadı')
    return body
