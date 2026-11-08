from pathlib import Path
import pytest
from ahos.source_context import select_context
from ahos.llm_executor import build_prompt, ModelError


def project(tmp_path):
    (tmp_path/'reservation_math.py').write_text('def available(capacity, used):\n    return capacity + used\n',encoding='utf-8')
    (tmp_path/'unrelated.py').write_text('raise RuntimeError("must not execute")\n',encoding='utf-8')
    return tmp_path


def test_turkish_goal_finds_source_without_filename(tmp_path):
    root=project(tmp_path)
    selected=select_context(root,'Rezervasyon kapasitesi kullanım sonrası yanlış hesaplanıyor')
    assert selected['selected'][0]['path']=='reservation_math.py'
    assert selected['scan_complete']
    assert 'raise RuntimeError' not in build_prompt(root,'Rezervasyon kapasitesini düzelt',auto_context=True)


def test_tests_and_secrets_never_become_editable_context(tmp_path):
    root=project(tmp_path)
    (root/'reservation_secrets.py').write_text('TOKEN = "never include me"',encoding='utf-8')
    (root/'test_reservation.py').write_text('SECRET = "test file not editable"',encoding='utf-8')
    (root/'.env').write_text('PRIVATE=never',encoding='utf-8')
    prompt=build_prompt(root,'Rezervasyon kapasitesini düzelt',auto_context=True)
    assert 'never include me' not in prompt and 'test file not editable' not in prompt and 'PRIVATE=' not in prompt


def test_incomplete_large_scan_fails_instead_of_guessing(tmp_path):
    root=project(tmp_path)
    (root/'huge.py').write_text('#'*(256*1024+1),encoding='utf-8')
    with pytest.raises(ModelError):build_prompt(root,'Rezervasyon kapasitesini düzelt',auto_context=True)


def test_no_match_requires_behavior_clarification(tmp_path):
    root=project(tmp_path)
    with pytest.raises(ModelError):build_prompt(root,'Başka belirsiz bir şey',auto_context=True)


def test_environment_directory_is_not_scanned(tmp_path):
    root=project(tmp_path)
    (root/'.venv').mkdir()
    (root/'.venv/reservation.py').write_text('this is invalid python !',encoding='utf-8')
    assert len(select_context(root,'Rezervasyon kapasitesi')['selected'])==1


def test_oversized_selected_source_is_not_silently_truncated(tmp_path):
    root=project(tmp_path)
    (root/'reservation_math.py').write_text('def available(capacity,used):\n    return 0\n'+'#'*7100,encoding='utf-8')
    with pytest.raises(ModelError):build_prompt(root,'Rezervasyon kapasitesi',auto_context=True)
