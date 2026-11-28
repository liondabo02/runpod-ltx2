"""V7: ücretli LLM çağrısı sahibin açık izni olmadan yapılmaz (ağ kullanmaz)."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import pytest, llm_guard, writers_room, office_live

LOCAL = "http://localhost:20128/v1"


@pytest.mark.parametrize("model", ["gpt-4o", "o3-mini", "claude-sonnet-4", "anthropic/claude-3", "gemini-2.5-pro", "grok-4", "openai/gpt-5"])
def test_ucretli_model_adi_engellenir(model):
    assert llm_guard.check(model, LOCAL, {})["ok"] is False


def test_yerel_olmayan_adres_engellenir():
    assert llm_guard.check("auto", "https://api.openai.com/v1", {})["ok"] is False


def test_auto_gecer_ama_maliyet_dogrulanmadi_notu_var():
    r = llm_guard.check("auto", LOCAL, {})
    assert r["ok"] and "doğrulanmadı" in r["note"]


def test_izin_ve_ucretsiz_liste():
    assert llm_guard.check("gpt-4o", LOCAL, {"AHOS_ALLOW_PAID": "1"})["ok"]
    assert llm_guard.check("gpt-4o", LOCAL, {"AHOS_FREE_MODELS": "gpt-4o"})["ok"]
    assert llm_guard.check("gpt-4o", LOCAL, {"AHOS_ALLOW_PAID": "0"})["ok"] is False


def test_yazarlar_odasi_ucretli_modelde_aga_cikmadan_durur(monkeypatch):
    monkeypatch.setenv("AHOS_LLM_MODEL", "gpt-4o"); monkeypatch.delenv("AHOS_ALLOW_PAID", raising=False)
    def yasak(*a, **k): raise AssertionError("ağ çağrısı yapıldı")
    monkeypatch.setattr(writers_room.urllib.request, "urlopen", yasak)
    with pytest.raises(RuntimeError, match="LLM_ODENEK_ENGELI"):
        writers_room.llm_call("s", "u")


def test_ofis_ceo_yaniti_ucretli_modelde_none_ve_agsiz():
    def yasak(*a, **k): raise AssertionError("ağ çağrısı yapıldı")
    assert office_live.model_reply("merhaba", "k", env={"AHOS_LLM_MODEL": "claude-opus", "AHOS_LLM_BASE": LOCAL}, opener=yasak) is None


def test_bilerek_bozma_koruma_kaldirilinca_ag_cagrisi_olur(monkeypatch):
    """Koruma yokmuş gibi (izin açık) aynı çağrı ağa çıkar: testlerin gerçekten korumayı ölçtüğünün kanıtı."""
    cagri = []
    class R:
        def __enter__(s): return s
        def __exit__(s, *a): return False
        def read(s): return b'{"choices":[{"message":{"content":"x"}}]}'
    monkeypatch.setenv("AHOS_LLM_MODEL", "gpt-4o"); monkeypatch.setenv("AHOS_ALLOW_PAID", "1")
    monkeypatch.setattr(writers_room.urllib.request, "urlopen", lambda *a, **k: (cagri.append(1), R())[1])
    monkeypatch.setattr(writers_room.json, "load", lambda r: {"choices": [{"message": {"content": "x"}}]})
    assert writers_room.llm_call("s", "u") == "x" and cagri
