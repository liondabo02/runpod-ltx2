import json
import shutil
import sys
from pathlib import Path
import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import p7_portraits as p7
import identity_lock

@pytest.fixture
def repo(tmp_path):
    shutil.copytree(ROOT / 'studio/canon', tmp_path / 'studio/canon')
    shutil.copytree(ROOT / 'studio/characters', tmp_path / 'studio/characters')
    p7.write(tmp_path / 'studio/production/approvals.json', {'approvals': []})
    return tmp_path

def image(root, n=0):
    path = root / f'fixture-{n}.png'
    im = Image.new('RGB', (512, 512), (n*13 % 255, n*27 % 255, 180))
    ImageDraw.Draw(im).rectangle((n+5, 30, 200+n, 400), fill=(200, n*11 % 255, 20))
    im.save(path)
    return path

def intake(repo, cid, n=0):
    return p7.import_portrait(repo,cid,image(repo,n),source='synthetic-test-only',
        model='Pillow fixture, not a character portrait',prompt='test fixture',seed=n,
        license_status='VERIFIED_COMMERCIAL')

def test_owner_canon_and_unique_designs():
    manifest=p7.read(ROOT/'studio/canon/cast-manifest.json')['characters']
    assert len(manifest)==16
    specs=[p7.design(ROOT,r['character_id']) for r in manifest]
    assert len({s['face_preset'] for s in specs})==16
    assert all(s['visual_reference'] is None and s['owner_approval']=='NONE' for s in specs)
    assert {r['character_id'] for r in manifest if r['hijab']}=={'esma','esra','oznur'}
    assert 'BLUE' in p7.design(ROOT,'veysel')['eyes_shape_spacing_color']
    assert 'heavy' in p7.design(ROOT,'davut')['body_height_age_proportions']
    assert p7.design(ROOT,'harun')['head_jaw'] != p7.design(ROOT,'davut')['head_jaw']
    assert identity_lock.verify()==[]

def test_family_and_timeline():
    rel=p7.read(ROOT/'studio/canon/family-relations.json')['relations']
    assert {'from':'harun','type':'partner_of','to':'esma'} in rel
    assert any(r['from']=='harun' and r['type']=='uncle_by_marriage_of' for r in rel)
    assert not any(r['from'] in {'veysel','oznur','davut','fatos'} and r['type'] in {'uncle_of','aunt_of','cousin_of'} for r in rel)
    trait=p7.read(ROOT/'studio/canon/story-timeline.json')['temporary_traits'][0]
    assert trait['months']==5 and trait['permanent_identity'] is False

def test_import_original_provenance_pending_and_idempotent(repo):
    row=intake(repo,'esma')
    assert row['status']==p7.PENDING and not row['final_use_allowed']
    assert p7.digest(repo/row['path'])==p7.digest(repo/'fixture-0.png')
    assert row['model'] and row['prompt'] and row['design_version']
    assert intake(repo,'esma')==row
    assert len(p7.read(repo/'studio/candidates/esma/registry.json')['candidates'])==1

@pytest.mark.parametrize('pair',[('aden','emos'),('berzan','aras')])
def test_duplicate_original_rejected_even_for_twins(repo,pair):
    intake(repo,pair[0])
    with pytest.raises(ValueError,match='two identities'): intake(repo,pair[1])

def test_similar_images_go_to_human_review(repo):
    intake(repo,'harun',1)
    row=intake(repo,'davut',2)
    assert row['similarity_flags']
    assert row['status']==p7.PENDING

def test_unknown_identity_and_small_image(repo):
    with pytest.raises(ValueError): intake(repo,'../x')
    path=repo/'small.png';Image.new('RGB',(12,12)).save(path)
    with pytest.raises(ValueError):p7.import_portrait(repo,'aden',path,source='x',model='x',prompt='x')

def test_concurrent_import_fails_closed(repo):
    with p7.exclusive(repo):
        with pytest.raises(FileExistsError):intake(repo,'aden')

def test_unapproved_poster_has_no_output(repo):
    out=repo/'poster.png'
    with pytest.raises(ValueError,match='approval'):p7.poster(repo,out)
    assert not out.exists()

def test_end_to_end_approved_fixture_poster_and_stale_guard(repo):
    approvals=[]
    rows=p7.read(repo/'studio/canon/cast-manifest.json')['characters']
    for n,cast in enumerate(rows):
        row=intake(repo,cast['character_id'],n)
        approvals.append(dict(character_id=cast['character_id'],status='APPROVED',sha256=row['sha256'],
             design_sha256=row['design_sha256'],approved_by='TEST FIXTURE ONLY',approved_at='test',
             canon_review_passed=True,similarity_review_passed=True))
    p7.write(repo/'studio/production/approvals.json',{'approvals':approvals})
    result=p7.poster(repo,repo/'poster.png')
    assert result['portraits']==16 and Image.open(repo/'poster.png').size==(1600,2000)
    bundle=p7.export_openmontage(repo,repo/'bundle')
    assert len(bundle['cuts'])==16
    assert all((repo/'bundle/public'/c['source']).is_file() for c in bundle['cuts'])
    p=repo/'studio/characters/aden/portrait-design.json'
    data=p7.read(p);data['version']='changed';p7.write(p,data)
    with pytest.raises(ValueError,match='Stale'):p7.poster(repo,repo/'stale.png')
    assert not (repo/'stale.png').exists()

def test_missing_human_review_and_license_block(repo):
    row=intake(repo,'aden')
    p7.write(repo/'studio/production/approvals.json',{'approvals':[dict(character_id='aden',status='APPROVED',sha256=row['sha256'])]})
    with pytest.raises(ValueError,match='Human'):p7.approved_rows(repo)


def test_same_pixels_with_different_metadata_rejected(repo):
    from PIL.PngImagePlugin import PngInfo
    row=intake(repo,'berzan')
    p=repo/'reencoded.png';info=PngInfo();info.add_text('name','different bytes')
    with Image.open(repo/row['path']) as im: im.save(p,pnginfo=info)
    assert p7.digest(p)!=row['sha256']
    with pytest.raises(ValueError,match='Same pixels'):
        p7.import_portrait(repo,'aras',p,source='fixture',model='fixture',prompt='fixture')

def test_portrait_design_is_part_of_identity_lock(repo,tmp_path):
    design=repo/'studio/characters/aden/portrait-design.json'
    data=p7.read(design);data['head_jaw']='tampered';p7.write(design,data)
    errors=identity_lock.verify(ROOT/'studio/identity/identity-lock.json',repo/'studio/characters')
    assert any('aden' in e and 'portrait-design.json' in e for e in errors)

def test_legacy_builder_cannot_reset_p7():
    import build_studio_cast
    with pytest.raises(SystemExit,match='P7 canon installed'):build_studio_cast.build()
