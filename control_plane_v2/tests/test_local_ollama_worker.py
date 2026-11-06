from contextlib import contextmanager
from unittest.mock import patch
import json
import pytest
from ahos import local_ollama as local
from ahos.llm_executor import ModelError, ModelSettings, load_settings, http_transport


@contextmanager
def free_lock():yield True


@contextmanager
def busy_lock():yield False


def settings():return load_settings({'AHOS_LLM_BASE_URL':local.BASE,'AHOS_LLM_MODEL':local.MODEL})


def test_no_key_required_only_for_fixed_free_local_configuration():
    config=settings()
    assert config.api_key=='local-only'
    assert config.input_usd_per_1k==config.output_usd_per_1k==0
    assert load_settings({'AHOS_LLM_BASE_URL':'https://outside.invalid/v1','AHOS_LLM_MODEL':local.MODEL}) is None


def test_busy_worker_never_calls_model():
    with patch.object(local,'inference_lock',busy_lock),patch.object(local,'request') as call:
        with pytest.raises(ModelError):local.transport('system','task',settings())
        call.assert_not_called()


def test_low_memory_never_calls_model():
    with patch.object(local,'inference_lock',free_lock),patch.object(local,'memory_available',return_value=1),patch.object(local,'request') as call:
        with pytest.raises(ModelError):local.transport('system','task',settings())
        call.assert_not_called()


def test_uninstalled_model_not_downloaded():
    with patch.object(local,'inference_lock',free_lock),patch.object(local,'memory_available',return_value=3*1024**3),patch.object(local,'request',return_value={'models':[]}) as call:
        with pytest.raises(ModelError):local.transport('system','task',settings())
        assert call.call_count==1
        assert call.call_args.args==('tags',)


def test_success_uses_shared_lock_and_bounded_generation():
    calls=[]
    def request(endpoint,body=None,timeout=5):
        calls.append((endpoint,body,timeout))
        return {'models':[{'name':local.MODEL}]} if endpoint=='tags' else {'done':True,'response':'{"edits":[]}'}
    with patch.object(local,'inference_lock',free_lock),patch.object(local,'memory_available',return_value=3*1024**3),patch.object(local,'request',side_effect=request):
        assert http_transport('system','task',settings())=='{"edits":[]}'
    assert calls[1][1]['options']['num_ctx']==4096
    assert calls[1][1]['options']['num_predict']==1024
    assert calls[1][1]['keep_alive']==0
    assert calls[1][2]<=90


def test_truncated_generation_is_not_success():
    with patch.object(local,'inference_lock',free_lock),patch.object(local,'memory_available',return_value=3*1024**3),patch.object(local,'request',side_effect=[{'models':[{'name':local.MODEL}]},{'done':True,'done_reason':'length','response':'{}'}]):
        with pytest.raises(ModelError):local.transport('system','task',settings())


def test_remote_or_large_model_configuration_rejected():
    with patch.object(local,'request') as call:
        for config in [ModelSettings(base_url='https://outside.invalid',api_key='none',model=local.MODEL),ModelSettings(base_url=local.BASE,api_key='local',model='qwen2.5-coder:7b')]:
            with pytest.raises(ModelError):local.transport('system','task',config)
        call.assert_not_called()


def test_oversized_context_never_calls_model():
    with patch.object(local,'request') as call:
        with pytest.raises(ModelError):local.transport('system','x'*12001,settings())
        call.assert_not_called()
