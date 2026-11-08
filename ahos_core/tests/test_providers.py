from __future__ import annotations

from ahos.providers import Provider, choose_chain, default_chain, probe


def test_default_chain_is_free_and_ordered() -> None:
    chain = default_chain()

    names = [provider.name for provider in chain]
    # Tünel açıkken sıra değişebilir; ikisi de ücretsiz zincirde olmalı.
    assert "lokal-ollama" in names and "tunel-ollama" in names
    assert chain[0].name in {"lokal-ollama", "tunel-ollama"}
    assert all(provider.is_free() for provider in chain)


def test_openrouter_added_only_with_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    names_without = [p.name for p in default_chain()]

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    names_with = [p.name for p in default_chain()]

    assert "openrouter-free" not in names_without
    assert "openrouter-free" in names_with


def test_choose_chain_picks_first_healthy() -> None:
    chain = [
        Provider("a", "http://a/v1", "m1"),
        Provider("b", "http://b/v1", "m2"),
    ]

    chosen, report = choose_chain(chain, probe_fn=lambda p: p.name == "b")

    assert chosen is not None and chosen.name == "b"
    assert report == [("a", False), ("b", True)]


def test_choose_chain_returns_none_when_all_down() -> None:
    chain = [Provider("a", "http://a/v1", "m1")]

    chosen, report = choose_chain(chain, probe_fn=lambda p: False)

    assert chosen is None
    assert report == [("a", False)]


def test_probe_rejects_removed_model(monkeypatch) -> None:
    class FakeResponse:
        status = 200

        def read(self) -> bytes:
            return b'{"data":[{"id":"baska-model"}]}'

        def __enter__(self):
            return self

        def __exit__(self, *args) -> bool:
            return False

    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **k: FakeResponse(), raising=True
    )

    assert probe(Provider("x", "http://x/v1", "yok-model")) is False
