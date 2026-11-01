from __future__ import annotations

from ahos.intent import analyze
from ahos.legal import review

# ---------- intent ----------


def test_intent_detects_feature() -> None:
    result = analyze("oyuna yeni bir zorluk seviyesi ekle")

    assert result.intent == "feature"
    assert any(dep == "oyun" for dep, _ in result.departments)


def test_intent_detects_example_url() -> None:
    result = analyze("şu site gibi bir ana sayfa yap https://example.com")

    assert result.example_kind == "url"
    assert "example.com" in result.example


def test_intent_detects_example_file() -> None:
    result = analyze("www/card-keys.js gibi bir dosya oluştur")

    assert result.example_kind == "dosya"
    assert result.example == "www/card-keys.js"


def test_intent_extracts_targets() -> None:
    result = analyze("www/oyun-yazi.js ve index.html dosyalarını düzelt")

    assert "www/oyun-yazi.js" in result.targets
    assert "index.html" in result.targets


def test_intent_scores_legal_department() -> None:
    result = analyze("çocuk oyunu için kvkk aydınlatma metni yaz")

    assert any(dep == "hukuk" for dep, _ in result.departments)


def test_intent_detects_constraints() -> None:
    result = analyze("acil olarak android için ücretsiz sürüm hazırla")

    assert "süre" in result.constraints
    assert "platform" in result.constraints


def test_intent_summary_is_readable() -> None:
    result = analyze("oyun için video jenerik hazırla")

    assert "niyet=" in result.summary()


# ---------- legal ----------


def test_legal_flags_copyright_with_alternative() -> None:
    result = review("Minecraft'ın birebir aynısını klonla")

    assert result.risk in {"orta", "yüksek"}
    assert result.warnings
    assert result.alternatives


def test_legal_flags_personal_data() -> None:
    result = review("çocukların e-posta adresini topla ve kaydet")

    assert "personal_data" in result.flags
    assert result.risk == "yüksek"


def test_legal_clean_request_has_no_warning() -> None:
    result = review("oyun menüsüne yeni bir buton ekle")

    assert result.risk == "yok"
    assert result.text() == ""


def test_legal_text_contains_alternative_heading() -> None:
    result = review("kumar oyunu ekle")

    text = result.text()
    assert "Hukuk uyarısı" in text
    assert "Yasal alternatif" in text


def test_legal_needs_confirmation_for_medium() -> None:
    result = review("rakip oyunun tasarımını kopyala")

    assert result.needs_owner_confirmation is True
