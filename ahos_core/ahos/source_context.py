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
         'hafiza':('memory','store'),'yeniden':('retry','recover'),
         'oyun':('game',),'hata':('error','exception'),'yazilim':('software',),
         'yetki':('authorization','permission'),'giris':('login','auth'),
         'kaydet':('save','persist'),'kayit':('record','store'),'dogrula':('verify','validate')}


def tokens(value):
    value=unicodedata.normalize('NFKD',value.lower().replace('ı','i'))
    return set(re.findall('[a-z0-9]+',''.join(c for c in value if not unicodedata.combining(c))))


def _excerpt(text, query, budget=2200):
    """Bounded exact source lines, with explicit ranges rather than silent truncation."""
    lines = text.splitlines(keepends=True)
    if len(text) <= budget:
        return text, False, [{'start': 1, 'end': len(lines)}] if lines else []
    ranked = sorted(range(len(lines)), key=lambda i: (-len(query & tokens(lines[i])), i))
    chosen = set()
    size = 0
    for center in ranked:
        if chosen and not (query & tokens(lines[center])):
            break
        window = set(range(max(0, center-3), min(len(lines), center+5))) - chosen
        added = sum(len(lines[i]) for i in window)
        if size + added + 2*len(chosen) > budget:
            continue
        chosen.update(window)
        size += added
    if not chosen:
        raise ValueError('İlgili kaynak satırı bağlama sığmıyor; görev bölünmeli')
    ranges=[]
    for i in sorted(chosen):
        if ranges and ranges[-1]['end'] == i:
            ranges[-1]['end'] = i+1
        else:
            ranges.append({'start': i+1, 'end': i+1})
    return '\n\n'.join(''.join(lines[r['start']-1:r['end']]) for r in ranges), True, ranges


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
                      and not d.startswith('.') and not any(s in d.casefold() for s in ('credential','secret','password'))
                      and not getattr(Path(directory)/d,'is_junction',lambda:False)()
                      and (Path(directory)/d).resolve().is_relative_to(root))
        for name in sorted(names):
            path=Path(directory)/name
            if path.suffix.lower() not in SUFFIXES:continue
            relative=path.relative_to(root).as_posix()
            if path.is_symlink() or not path.resolve().is_relative_to(root):continue
            if name.startswith(('test_','test-')) or 'tests' in path.relative_to(root).parts:continue
            if name.startswith('.') or any(word in name.lower() for word in ('credential','secret','password')):continue
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
    sources=[]
    for score,path,text,digest in selected:
        excerpt,shortened,ranges=_excerpt(text,query)
        sources.append(dict(path=path,text=excerpt,sha256=digest,score=score,
                            excerpted=shortened,line_ranges=ranges))
    return dict(scanned_files=files,selected=sources,
                scan_complete=True,selection_scope='lexical paths and Python symbols; not complete dependency closure')
