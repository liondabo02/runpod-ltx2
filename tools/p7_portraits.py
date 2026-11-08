"""Offline portrait intake and reviewed-only poster gate; never calls a model."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
PENDING = 'CANDIDATE_PENDING_REVIEW'

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    temporary.replace(path)

@contextmanager
def exclusive(root):
    path = root / 'studio/candidates/.p7-write-lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        try:
            yield
        finally:
            handle.close()
            path.unlink()  # only this operation's own lock

def design(root, cid):
    ids = {r['character_id'] for r in read(root / 'studio/canon/cast-manifest.json')['characters']}
    if cid not in ids:
        raise ValueError('Unknown canonical character')
    return read(root / 'studio/characters' / cid / 'portrait-design.json')

def fingerprint(path):
    with Image.open(path) as im:
        pixels = list(ImageOps.grayscale(ImageOps.exif_transpose(im)).resize((9, 8)).getdata())
    return sum((pixels[y*9+x] > pixels[y*9+x+1]) << (y*8+x) for y in range(8) for x in range(8))

def pixel_digest(path):
    with Image.open(path) as im:
        normalized = ImageOps.exif_transpose(im).convert('RGB')
        return hashlib.sha256(str(normalized.size).encode() + normalized.tobytes()).hexdigest()

def import_portrait(root, cid, image, *, source, model, prompt, seed=None, license_status='UNVERIFIED'):
    root, image = Path(root), Path(image)
    spec = design(root, cid)
    if not all(isinstance(x, str) and x.strip() for x in (source, model, prompt, license_status)):
        raise ValueError('Source, model, prompt and license status required; use UNKNOWN explicitly')
    with Image.open(image) as im:
        fmt, size = im.format, im.size
        im.verify()
    if fmt not in {'PNG', 'JPEG'} or min(size) < 512:
        raise ValueError('PNG/JPEG portrait must be at least 512 x 512')
    raw = image.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    perceptual = fingerprint(image)
    pixels_sha = pixel_digest(image)
    with exclusive(root):
        flags = []
        for meta in (root / 'studio/candidates').glob('*/*.json'):
            row = read(meta)
            if 'sha256' not in row or 'character_id' not in row:
                continue
            if row['character_id'] != cid and row['sha256'] == sha:
                raise ValueError('Same original cannot represent two identities, including twins')
            if row['character_id'] != cid and row.get('pixels_sha256') == pixels_sha:
                raise ValueError('Same pixels cannot represent two identities, including twins')
            if 'dhash' not in row:
                flags.append({'character_id': row['character_id'], 'decision': 'LEGACY_REFERENCE_HUMAN_REVIEW_REQUIRED'})
                continue
            distance = (int(row['dhash'], 16) ^ perceptual).bit_count()
            if row['character_id'] != cid and distance <= 8:
                flags.append({'character_id': row['character_id'], 'distance': distance,
                              'decision': 'HUMAN_REVIEW_REQUIRED'})
        directory = root / 'studio/candidates' / cid
        directory.mkdir(parents=True, exist_ok=True)
        meta = directory / (sha + '.json')
        if meta.exists():
            return read(meta)  # preserve provenance and review on reimport
        target = directory / (sha + ('.png' if fmt == 'PNG' else '.jpg'))
        if not target.exists():
            with target.open('xb') as f:
                f.write(raw)
        if digest(target) != sha:
            raise ValueError('Original integrity failure')
        dna = root / 'studio/characters' / cid / 'visual-dna.json'
        row = dict(schema='ahos.studio.portrait.v1', character_id=cid, sha256=sha,
                   path=target.relative_to(root).as_posix(), width=size[0], height=size[1],
                   source=source, model=model, prompt=prompt, seed=seed,
                   design_version=spec['version'], design_sha256=digest(root / 'studio/characters' / cid / 'portrait-design.json'),
                   visual_dna={'path': dna.relative_to(root).as_posix(), 'sha256': digest(dna)},
                   commercial_license=license_status, status=PENDING, owner_approval='NONE',
                   identity_lock_modified=False, final_use_allowed=False,
                   dhash=f'{perceptual:016x}', pixels_sha256=pixels_sha, similarity_flags=flags,
                   algorithm_limit='Image hash is triage, not face recognition or canon approval',
                   imported_at=datetime.now(timezone.utc).isoformat())
        write(meta, row)
        registry_path = directory / 'registry.json'
        registry = read(registry_path) if registry_path.exists() else {'character_id': cid, 'candidates': []}
        registry['candidates'].append({'sha256': sha, 'path': row['path'], 'status': PENDING, 'owner_approval': 'NONE'})
        registry['awaiting_import'] = False
        write(registry_path, registry)
        return row

def approved_rows(root):
    """Require explicit human review tied to original and current design hashes."""
    root = Path(root)
    approvals = read(root / 'studio/production/approvals.json')['approvals']
    result = []
    for cast in read(root / 'studio/canon/cast-manifest.json')['characters']:
        cid = cast['character_id']
        matching = [a for a in approvals if a.get('character_id') == cid and a.get('status') == 'APPROVED']
        if len(matching) != 1:
            raise ValueError(f'{cid}: exactly one explicit portrait approval required')
        a = matching[0]
        sha = a.get('sha256', '')
        if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError('Invalid SHA-256')
        row = read(root / 'studio/candidates' / cid / (sha + '.json'))
        p = (root / row['path']).resolve()
        if not p.is_relative_to((root / 'studio/candidates' / cid).resolve()):
            raise ValueError('Candidate outside identity directory')
        if not a.get('approved_by') or not a.get('approved_at') or not a.get('canon_review_passed') or not a.get('similarity_review_passed'):
            raise ValueError('Human canon and pairwise similarity review required')
        design_hash = digest(root / 'studio/characters' / cid / 'portrait-design.json')
        dna_hash = digest(root / 'studio/characters' / cid / 'visual-dna.json')
        if (row['character_id'] != cid or row['sha256'] != sha or digest(p) != sha or row['design_sha256'] != design_hash
                or a.get('design_sha256') != design_hash or row['visual_dna']['sha256'] != dna_hash):
            raise ValueError('Stale approval or modified portrait/design')
        if row['commercial_license'] != 'VERIFIED_COMMERCIAL':
            raise ValueError('Commercial license unverified')
        result.append((cast, row, p))
    if len({row['sha256'] for _, row, _ in result}) != len(result):
        raise ValueError('Duplicate original across identities')
    return result

def export_openmontage(root, output):
    """Create a separate public-dir bundle for installed OpenMontage Explainer."""
    rows = approved_rows(root)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    public = output / 'public' / 'portraits'
    public.mkdir(parents=True)
    cuts = []
    for i, (cast, row, path) in enumerate(rows):
        target = public / (cast['character_id'] + path.suffix)
        with target.open('xb') as f:
            f.write(path.read_bytes())
        cuts.append({'id': cast['character_id'], 'type': 'image',
                     'source': 'portraits/' + target.name, 'in_seconds': i*3, 'out_seconds': (i+1)*3})
    payload = {'theme': 'studio-cast', 'cuts': cuts, 'status': 'APPROVED_PORTRAIT_GALLERY_NOT_ANIMATION'}
    write(output / 'props.json', payload)
    return payload

def poster(root, output):
    rows = approved_rows(root)  # validate everything before creating output
    canvas = Image.new('RGB', (1600, 2000), '#f4efe5')
    draw = ImageDraw.Draw(canvas)
    for i, (cast, row, path) in enumerate(rows):
        with Image.open(path) as im:
            tile = ImageOps.contain(ImageOps.exif_transpose(im).convert('RGB'), (380, 440))
        x, y = (i % 4)*400, (i // 4)*500
        canvas.paste(tile, (x + (400-tile.width)//2, y))
        draw.text((x+20, y+450), cast['character_id'], fill='black')
    output = Path(output)
    with output.open('xb') as f:
        canvas.save(f, format='PNG')
    return {'path': str(output), 'sha256': digest(output), 'portraits': len(rows)}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('import')
    for name in ('character', 'image', 'source', 'model', 'prompt'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--seed', type=int)
    p.add_argument('--license-status', default='UNVERIFIED')
    p = sub.add_parser('poster'); p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('export'); p.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'import':
        result = import_portrait(args.root, args.character, args.image, source=args.source,
            model=args.model, prompt=args.prompt, seed=args.seed, license_status=args.license_status)
    elif args.command == 'export':
        result = export_openmontage(args.root, args.output)
    else:
        result = poster(args.root, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
