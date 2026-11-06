"""Explicit operator review bound to exact episode assets, outside worker outputs.

Only call record_review on a direct owner decision. This is provenance, not an
OS authentication boundary; the studio child never calls the approval writer.
"""
import argparse,hashlib,json,sqlite3,time
from pathlib import Path
from .studio_department import STAGES,acceptance,tasks

CHECKS=('language_reviewed','continuity_reviewed','visual_reviewed','voice_reviewed','owner_approved')

def fingerprint(runtime,ident):
    from .studio_runtime import _load_idea
    idea=_load_idea(runtime,ident);root=(Path(runtime)/'studio-production'/ident).resolve();pins=[]
    for task in idea['tasks']:
        if task['stage']=='qa':continue
        if task.get('status')!='done':raise ValueError('Tüm üretim aşamaları incelemeye hazır değil')
        issues=acceptance(runtime,ident,task)
        if issues:raise ValueError('İnceleme öncesi çıktı doğrulanamadı: '+'; '.join(issues))
        manifest=root/task['stage']/'manifest.json'
        pins.append((task['stage'],hashlib.sha256(manifest.read_bytes()).hexdigest()))
    return hashlib.sha256(json.dumps(pins,sort_keys=True).encode()).hexdigest()

def _connect(runtime,create=False):
    path=(Path(runtime)/'studio-owner-decisions.sqlite3').resolve()
    if not create and not path.exists():return None
    db=sqlite3.connect(str(path) if create else path.as_uri()+'?mode=ro',uri=not create,timeout=3)
    if create:
        db.execute('CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY,idea_id TEXT,fingerprint TEXT,approved INTEGER,checks TEXT,actor TEXT,at REAL)')
    return db

def approval_matches(runtime,ident):
    try:db=_connect(runtime)
    except (OSError,sqlite3.Error):return False
    if db is None:return False
    try:row=db.execute('SELECT fingerprint,approved,checks,actor FROM reviews WHERE idea_id=? ORDER BY id DESC LIMIT 1',(ident,)).fetchone()
    except sqlite3.Error:return False
    finally:db.close()
    if not row or row[1]!=1 or row[3]!='owner' or not all(json.loads(row[2]).get(k) is True for k in CHECKS):return False
    try:return row[0]==fingerprint(runtime,ident)
    except (OSError,ValueError,TypeError,KeyError):return False

def record_review(runtime,ident,expected,*,approved,checks,confirmation):
    if confirmation!='STUDIO '+ident+' '+expected:raise ValueError('Somut bölüm özeti için açık sahip onayı gerekli')
    current=fingerprint(runtime,ident)
    if current!=expected:raise ValueError('İncelenen bölüm değişmiş; eski onay uygulanamaz')
    if approved and not all(checks.get(k) is True for k in CHECKS):raise ValueError('Dil, görsel, süreklilik ve ses incelemesi eksik')
    db=_connect(runtime,create=True)
    try:
        with db:db.execute('INSERT INTO reviews(idea_id,fingerprint,approved,checks,actor,at) VALUES(?,?,?,?,?,?)',(ident,current,int(approved),json.dumps(checks),'owner',time.time()))
    finally:db.close()

def main():
    parser=argparse.ArgumentParser(description='Bölümün gerçek dosyalarına bağlı son sahip incelemesi')
    parser.add_argument('--runtime',type=Path,required=True);parser.add_argument('--idea',required=True)
    parser.add_argument('--approve',action='store_true');parser.add_argument('--fingerprint');parser.add_argument('--confirm')
    args=parser.parse_args()
    if args.approve:
        record_review(args.runtime,args.idea,args.fingerprint,approved=True,checks={k:True for k in CHECKS},confirmation=args.confirm)
    print(json.dumps(dict(idea=args.idea,fingerprint=fingerprint(args.runtime,args.idea),approved=approval_matches(args.runtime,args.idea))))

if __name__=='__main__':main()
