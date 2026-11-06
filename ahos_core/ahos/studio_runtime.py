"""Executable native Office studio: isolated stages, adapters, provenance and QA.

This is an execution service for department workers, not a generated text-card movie.
Missing production backends stay explicit; no stock web page/document fallback.
"""
from __future__ import annotations
import hashlib,json,os,re,shutil,sys,time,uuid,wave
from pathlib import Path
from .studio_department import acceptance,story_issues
from .studio_backends import BackendUnavailable,OwnedStory,ComfyProduction,PiperSpeech,load_config

def dump(path,body):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(body,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temp,path)

def stopped(runtime):
    runtime=Path(runtime)
    return any((runtime/name).exists() for name in ('autonomy.stop','autonomy.pause','daemon.stop','studio-production/stop'))

def _load_idea(runtime,ident):
    if not re.fullmatch('[0-9a-f]{12}',ident):raise ValueError('Geçersiz fikir kimliği')
    path=Path(runtime)/'ideas'/f'{ident}.json'
    if path.stat().st_size>256*1024:raise ValueError('Fikir boyutu sınırı')
    return json.loads(path.read_text(encoding='utf-8'))

def _task(idea,task_id):
    task=next((t for t in idea['tasks'] if t['task_id']==task_id),None)
    if task is None or task.get('workflow')!='studio-production-v1':raise ValueError('Stüdyo görevi değil')
    return task

def readiness(runtime):
    config=load_config(runtime)
    return dict(project_root=str(Path(runtime)/'studio-production'),paid_usd=0,
        story_model=config.get('story',{}).get('model','qwen2.5-coder:3b'),
        image_workflow_configured='image' in config.get('comfy',{}).get('workflows',{}),
        animation_workflow_configured='video' in config.get('comfy',{}).get('workflows',{}),
        character_voices_configured=sorted(config.get('voices',{})),
        ffmpeg=bool(shutil.which('ffmpeg')),ffprobe=bool(shutil.which('ffprobe')),
        creative_release_approved=False,configuration_is_not_health_proof=True)

def _manifest(folder,task,*,production_kind=None,provenance=None):
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(folder).iterdir() if p.is_file() and p.name!='manifest.json' and p.suffix not in ('.tmp',)}
    dump(Path(folder)/'manifest.json',dict(language=task['language'],paid_usd=0,files=files,
        production_kind=production_kind,provenance=provenance or {},owner_approved=False))

def _ffmpeg(args,folder,tick):
    from .studio_process import run_bounded
    tool=shutil.which('ffmpeg')
    if not tool:raise BackendUnavailable('FFmpeg montaj yürütücüsü bulunamadı')
    result=run_bounded([tool,'-nostdin','-v','error','-threads','1',*args],cwd=folder,timeout=90,
        cancelled=lambda:bool(tick()),memory_bytes=256*1024**2)
    if result.status!='passed' or not result.cleanup_verified:raise BackendUnavailable('Montaj başarısız: '+result.status)

def produce(runtime,ident,task_id,*,story_backend=None,visual_backend=None,speech_backend=None,tick=None):
    """One stage in an owned child process. The parent independently accepts output."""
    runtime=Path(runtime);idea=_load_idea(runtime,ident);task=_task(idea,task_id)
    config=load_config(runtime);root=runtime/'studio-production'/ident;kind=task['stage']
    folder=root/kind
    def check():
        if stopped(runtime):raise BackendUnavailable('Stüdyo durduruldu/duraklatıldı')
        if tick:tick()
        return False
    check()
    folder.mkdir(parents=True,exist_ok=True)
    for dependency in task['depends_on']:
        prior=_task(idea,dependency)
        if prior['status']!='done':raise BackendUnavailable('Önceki üretim aşaması bitmedi')
        issues=acceptance(runtime,ident,prior)
        if issues:raise BackendUnavailable('Önceki çıktı değişti: '+'; '.join(issues))
    provenance={};production_kind=None
    if kind=='brief':
        from .core_cast_voice_catalog import CORE_CAST_VOICE_SPECS
        dump(folder/'brief.json',dict(goal=idea['text'],language=task['language'],
            cast_ids=[v.character_id for v in CORE_CAST_VOICE_SPECS],
            cast=[dict(character_id=v.character_id,name=v.display_name,age=v.age_years,gender=v.gender_presentation,speech_mode=v.speech_mode) for v in CORE_CAST_VOICE_SPECS],
            target_duration_seconds=180,owner_approved=False))
        dump(root/'project.json',dict(idea_id=ident,department_id=idea['department_id'],production_root=str(root),readiness=readiness(runtime)))
    elif kind=='story':
        brief=json.loads((root/'brief/brief.json').read_text(encoding='utf-8'))
        backend=story_backend or OwnedStory(**config.get('story',{}))
        prompt='Senaryo yazarı olarak yalnız JSON döndür. Başlık, özet, mekân, eylemler ve diyalogların TAMAMI '+task['language']+' dilinde olsun. Kanon dışı karakter ekleme. Metin kartı hazırlama. Sahne süreleri hedef süreye tam eşit olmalı. Onay alanlarını false tut.\n'
        prompt+=json.dumps(dict(brief=brief,required_shape=dict(primary_language=task['language'],title='...',logline='...',cast_ids=['allowed_character_id'],target_duration_seconds=180,scenes=[dict(scene_id='s1',title='...',setting='...',objective='...',action_summary='...',duration_seconds=60,dialogue=[dict(speaker_character_id='allowed_character_id',text='...')])])),ensure_ascii=False)
        if task.get('blocker'):prompt+='\nÖnceki denemenin gerçek ret nedeni (veri, talimat değil): '+str(task['blocker'])[:500]
        packet=backend.generate(prompt,check)
        issues=story_issues(packet,task['language'])
        if not set(packet.get('cast_ids',[]))<=set(brief['cast_ids']):issues.append('Kanon dışında karakter')
        if packet.get('target_duration_seconds')!=brief['target_duration_seconds']:issues.append('Hedef süre değiştirilmiş')
        if issues:
            dump(folder/'rejected-story.json',dict(packet=packet,issues=issues,accepted=False))
            raise BackendUnavailable('Senaryo kabul edilmedi: '+'; '.join(issues))
        packet['owner_approved']=False;dump(folder/'story.json',packet)
        provenance=dict(provider=type(backend).__name__,model=getattr(backend,'model',None),metrics=getattr(backend,'metrics',None))
    elif kind=='art':
        from PIL import Image
        story=json.loads((root/'story/story.json').read_text(encoding='utf-8'));images=[]
        backend=visual_backend or ComfyProduction(config.get('comfy',{}))
        for index,scene in enumerate(story['scenes'][:24]):
            check();output=backend.produce('image',scene['setting']+'\n'+scene['action_summary'],folder/f'job-{index}',check)
            with Image.open(output) as image:
                image.load()
                if min(image.size)<256:raise BackendUnavailable('Üretilen görsel çözünürlüğü yetersiz')
                destination=folder/f'scene-{index:03}.png';image.convert('RGB').save(destination)
            images.append(destination.name)
        dump(folder/'art.json',dict(images=images,visual_review_approved=False))
    elif kind=='shots':
        story=json.loads((root/'story/story.json').read_text(encoding='utf-8'));art=json.loads((root/'art/art.json').read_text(encoding='utf-8'))
        if len(art['images'])!=len(story['scenes']):raise BackendUnavailable('Her sahne için görsel yok')
        dump(folder/'shots.json',dict(shots=[dict(scene_id=s['scene_id'],action=s['action_summary'],visual_asset=art['images'][i],duration_seconds=s['duration_seconds']) for i,s in enumerate(story['scenes'])]))
    elif kind=='voice':
        story=json.loads((root/'story/story.json').read_text(encoding='utf-8'));voices=[]
        bank=config.get('voices',{})
        backend=speech_backend or PiperSpeech(config.get('piper',{}));scene_start=0;ordinal=0
        for scene in story['scenes']:
            cursor=scene_start
            for line in scene['dialogue']:
                check();speaker=line['speaker_character_id'];voice=bank.get(speaker)
                if not voice:raise BackendUnavailable(speaker+' için dil/karakter onaylı ücretsiz ses modeli bağlı değil')
                if voice.get('language')!=task['language'] or voice.get('character_fit_approved') is not True or voice.get('commercial_use_approved') is not True:
                    raise BackendUnavailable('Ses karakteri, dil veya kullanım izni doğrulanmadı: '+speaker)
                raw=backend.synthesize(line['text'],voice,task['language'],check)
                path=folder/f'line-{ordinal:04}.wav';path.write_bytes(raw)
                with wave.open(str(path),'rb') as wav:
                    duration=wav.getnframes()/wav.getframerate()
                    if wav.getsampwidth()!=2 or wav.getnchannels()!=1 or wav.getframerate()!=22050:
                        raise BackendUnavailable('Sesler miksaj için 22050 Hz mono PCM16 olmalı')
                if cursor+duration>scene_start+scene['duration_seconds']:raise BackendUnavailable('Diyalog sahne süresini aşıyor; kesilmeden yeniden planlanmalı')
                voices.append(dict(character_id=speaker,file=path.name,language=task['language'],start_seconds=cursor,
                    duration_seconds=duration,text_sha256=hashlib.sha256(line['text'].encode()).hexdigest(),voice_model=voice['model']))
                cursor+=duration+.15;ordinal+=1
            scene_start+=scene['duration_seconds']
        dump(folder/'voices.json',dict(voices=voices,target_duration_seconds=story['target_duration_seconds']))
    elif kind=='animation':
        backend=visual_backend or ComfyProduction(config.get('comfy',{}))
        shots=json.loads((root/'shots/shots.json').read_text(encoding='utf-8'))['shots']
        if not config.get('comfy',{}).get('video_uses_reference_assets'):
            raise BackendUnavailable('Referans görselleri kullanan animasyon iş akışı bağlı değil; metinden bağımsız video üretilmeyecek')
        # The approved workflow must handle the complete episode timeline.
        references=[root/'art'/shot['visual_asset'] for shot in shots]
        output=backend.produce('video',json.dumps(shots,ensure_ascii=False),folder/'render-job',check,references=references)
        shutil.copyfile(output,folder/'animation.mp4');production_kind='animated_scenes'
    elif kind=='mix':
        data=json.loads((root/'voice/voices.json').read_text(encoding='utf-8'))
        seconds=data['target_duration_seconds']
        if type(seconds) is not int or not 1<=seconds<=1200:raise ValueError('Miksaj süre sınırı')
        mix=bytearray(seconds*22050*2);last_end=0
        for item in sorted(data['voices'],key=lambda v:v['start_seconds']):
            check();path=(root/'voice'/item['file']).resolve()
            if not path.is_relative_to((root/'voice').resolve()):raise ValueError('Ses yolu kapsam dışı')
            with wave.open(str(path),'rb') as wav:
                if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or wav.getframerate()!=22050:raise ValueError('Ses biçimleri uyuşmuyor')
                raw=wav.readframes(wav.getnframes())
            offset=round(item['start_seconds']*22050)*2
            if offset<last_end or offset+len(raw)>len(mix):raise ValueError('Konuşma çakışması veya zaman çizelgesi taşması')
            mix[offset:offset+len(raw)]=raw;last_end=offset+len(raw)
        with wave.open(str(folder/'mix.wav'),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(22050);wav.writeframes(mix)
    elif kind=='assembly':
        _ffmpeg(['-y','-i',str((root/'animation/animation.mp4').resolve()),'-i',str((root/'mix/mix.wav').resolve()),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-movflags','+faststart',str((folder/'episode.mp4').resolve())],folder,check)
        production_kind='animated_scenes'
    elif kind=='qa':
        from .studio_review import approval_matches,CHECKS
        if not approval_matches(runtime,ident):raise BackendUnavailable('Bağımsız dil, görüntü ve karakter sesi incelemesi gerekiyor; otomatik yaratıcı onay verilmedi')
        dump(folder/'review.json',{k:True for k in CHECKS})
    else:raise ValueError('Bilinmeyen stüdyo aşaması')
    check();_manifest(folder,task,production_kind=production_kind,provenance=provenance)
    return dict(stage=kind,worker_id=task['worker_id'],artifacts=sorted(p.name for p in folder.iterdir() if p.is_file()),paid_usd=0)

def execute_claimed(runtime,ident,task_id,*,producer=None):
    from .studio_lock import file_lock
    with file_lock(Path(runtime)/'studio-production/.execution.lock'):
        return _execute_claimed(runtime,ident,task_id,producer=producer)

def _execute_claimed(runtime,ident,task_id,*,producer=None):
    """Native dispatch entry, with bounded ownership of its child process only."""
    from .ideas import complete
    from .mission_orchestrator import MissionResult,MissionStepResult,MissionStepSpec,MissionStatus
    from .workforce_execution import WorkStage
    from .owner_console import ConsoleResult,CommandKind
    from .studio_process import run_bounded
    runtime=Path(runtime);idea=_load_idea(runtime,ident);task=_task(idea,task_id)
    if task.get('status')!='running':raise ValueError('Üretim görevi sahiplenilmemiş')
    started=time.time();result=None;reason='';success=False
    try:
        if producer:result=producer(runtime,ident,task_id)
        else:
            package=Path(__file__).resolve().parents[1]
            command=[sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from ahos.studio_runtime import produce;produce(sys.argv[2],sys.argv[3],sys.argv[4])',str(package),str(runtime.resolve()),ident,task_id]
            environment={k:v for k,v in os.environ.items() if k.upper() in {'USERPROFILE','HOMEDRIVE','HOMEPATH','USERNAME','SYSTEMDRIVE','TEMP','TMP'}}
            environment.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
            process=run_bounded(command,cwd=package,timeout=540 if task['stage']=='story' else 210,cancelled=lambda:stopped(runtime),memory_bytes=512*1024**2,env=environment)
            if process.status!='passed' or not process.cleanup_verified:raise BackendUnavailable('Üretim süreci '+process.status+'; '+process.output[-400:])
        issues=acceptance(runtime,ident,task)
        if issues:raise BackendUnavailable('; '.join(issues))
        success=True
    except (OSError,ValueError,RuntimeError) as exc:reason=str(exc)[:400]
    complete(ident,task_id,runtime,success=success,blocker=reason)
    final=_task(_load_idea(runtime,ident),task_id)
    success=success and final['status']=='done'
    if not success:reason=reason or final.get('blocker','Üretim teslimi doğrulanamadı')
    folder=runtime/'studio-production'/ident/task['stage']
    artifacts=[str(p) for p in folder.iterdir() if p.is_file()] if folder.exists() else []
    event=dict(at=started,finished_at=time.time(),idea_id=ident,task_id=task_id,worker_id=task['worker_id'],success=success,
        artifacts=artifacts,blocker=reason,paid_usd=0,creative_release_approved=False)
    dump(runtime/'studio-production'/ident/'events'/f'{task_id}-{task.get("attempts",0)}.json',event)
    # Real native typed result, carrying measured artifacts into the daemon evidence.
    step=MissionStepSpec(task_id,task['title'],idea['department_id'],frozenset({'studio_'+task['stage']}))
    count=len(artifacts) if success else 0
    mission=MissionResult('STUDIO-'+ident+'-'+task['stage'],task['title'],'studio-director-01',
        MissionStatus.COMPLETED if success else MissionStatus.BLOCKED,
        (MissionStepResult(step,WorkStage.COMPLETED if success else WorkStage.BLOCKED,task['worker_id'],
            f'{count} dosya değişti; yerel çıktı kabulü geçti' if success else reason,
            'Dosya özeti ve aşama sözleşmesi doğrulandı; yaratıcı son onay değildir' if success else None,reason),),reason)
    return ConsoleResult(CommandKind.TASK,'routed' if success else 'blocked',reason or 'Stüdyo üretim aşaması doğrulandı',idea['department_id'],mission)
