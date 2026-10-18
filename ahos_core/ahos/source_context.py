"""Bounded, local goal-to-source discovery. Does not execute repository code."""
import ast
import hashlib
import os
import re
import unicodedata
from pathlib import Path

IGNORED={'.git','.venv','venv','node_modules','__pycache__','dist','build','.pytest_cache','runtime'}
SUFFIXES={'.py','.js','.ts','.tsx','.jsx','.html','.css'}
ALIASES={'kuyruk':('queue','task'),'gorev':('task','mission'),'rezerv':('reservation','reserve'),
         'kapasit':('capacity','available'),'bellek':('memory',),'zaman':('timeout','deadline'),
         'oturum':('session',),'klavye':('keyboard','keys'),'dokun':('touch','click','guard'),
         'hafiza':('memory','store'),'yeniden':('retry','recover')}


def tokens(value):
    value=unicodedata.normalize('NFKD',value.lower().replace('ı','i'))
    return set(re.findall('[a-z0-9]+',''.join(c for c in value if not unicodedata.combining(c))))


def select_context(root, goal):
    original=Path(root)
    if original.is_symlink() or getattr(original,'is_junction',lambda:False)():raise ValueError('Bağlantılı proje kökü reddedildi')
    root=original.resolve()
    if not root.is_dir():raise ValueError('Proje kökü geçersiz')
    query=tokens(goal)
    for token in tuple(query):
        for stem,terms in ALIASES.items():
            if token.startswith(stem):query.update(terms)
    ranked=[];entries=0;files=0;scanned_bytes=0
    for directory,dirs,names in os.walk(root,followlinks=False):
        entries+=len(dirs)+len(names)
        if entries>2048:raise ValueError('Kaynak tarama girdi sınırı; görev bölünmeli')
        dirs[:]=sorted(d for d in dirs if d not in IGNORED and not (Path(directory)/d).is_symlink()
                      and not getattr(Path(directory)/d,'is_junction',lambda:False)()
                      and (Path(directory)/d).resolve().is_relative_to(root))
        for name in sorted(names):
            path=Path(directory)/name
            if path.suffix.lower() not in SUFFIXES:continue
            relative=path.relative_to(root).as_posix()
            if path.is_symlink() or not path.resolve().is_relative_to(root):continue
            if name.startswith(('test_','test-')) or 'tests' in path.relative_to(root).parts:continue
            if any(word in name.lower() for word in ('credential','secret','password')):continue
            files+=1
            if files>256:raise ValueError('Kaynak dosya sınırı; görev bölünmeli')
            size=path.stat().st_size
            if size>256*1024:raise ValueError('Kaynak dosyası çok büyük; kapsam daraltılmalı')
            scanned_bytes+=size
            if scanned_bytes>4*1024*1024:raise ValueError('Kaynak tarama bayt sınırı')
            with path.open('rb') as stream:raw=stream.read(size+1)
            if len(raw)!=size:raise ValueError('Tarama sırasında kaynak değişti')
            try:text=raw.decode('utf-8')
            except UnicodeDecodeError:raise ValueError('Kaynak UTF-8 değil; bağlam doğrulanamadı')
            symbols=set()
            if path.suffix=='.py':
                try:tree=ast.parse(text)
                except SyntaxError:raise ValueError('Python kaynağı ayrıştırılamadı')
                symbols=tokens(' '.join(n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))))
            score=8*len(query&tokens(relative))+2*len(query&symbols)
            if score:ranked.append((score,relative,text,hashlib.sha256(raw).hexdigest()))
    ranked.sort(key=lambda r:(-r[0],r[1]))
    if not ranked:raise ValueError('Güvenilir kaynak eşleşmesi yok; beklenen davranışı netleştir')
    selected=ranked[:3]
    if sum(len(row[2]) for row in selected)>7000:raise ValueError('Yerel model bağlamı aşılıyor; görev bölünmeli')
    return dict(scanned_files=files,selected=[dict(path=p,text=t,sha256=h,score=s) for s,p,t,h in selected],
                scan_complete=True,selection_scope='lexical paths and Python symbols; not complete dependency closure')
