"""Kapalı döngü onarım: doğrulama hatasını modele geri besle.

Uzman mühendisin başarısızlıklarının %19'u "kabul kapısı": model bir kez yanlış
yama üretiyor, kapı düşüyor, değişiklik geri alınıyor ve görev bitiyor.
Bu modül, kapı çıktısını modele **geri bildirim** olarak verip ikinci (ve
gerekirse üçüncü) denemeyi yapılandırır.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_ATTEMPTS = 2


@dataclass(frozen=True)
class RepairAttempt:
    number: int
    prompt: str


def error_excerpt(output: str, limit: int = 1200) -> str:
    """Kapı çıktısından en bilgilendirici hata satırlarını seçer."""

    text = (output or "").strip()
    if not text:
        return "(çıktı yok)"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    key_lines = [
        line
        for line in lines
        if any(
            token in line.casefold()
            for token in ("hata", "error", "başarısız", "basarisiz", "eksik", "missing", "fail", "syntax", "sorun", "bulundu")
        )
    ]
    chosen = key_lines[-8:] if key_lines else lines[-8:]
    return "\n".join(chosen)[:limit]


def feedback_prompt(base_prompt: str, output: str, files: dict[str, str] | None = None) -> str:
    """Modele "şu hata çıktı, düzelt" diyen yeni istem üretir."""

    parts = [
        base_prompt,
        "",
        "### KABUL KAPISI HATASI",
        error_excerpt(output),
        "",
        "Yukarıdaki hata senin son yamandan kaynaklandı. Yalnızca hatayı gideren",
        "en küçük yamayı üret. Aynı içeriği tekrar gönderme; JSON şemasına uy.",
    ]
    if files:
        for path, content in list(files.items())[:2]:
            parts += ["", f"### {path} (gerçek içerik)", "```", content[:3000], "```"]
    return "\n".join(parts)


def should_retry(attempt: int, *, max_attempts: int = MAX_ATTEMPTS) -> bool:
    """Kaçıncı denemeden sonra vazgeçileceğini söyler (1 tabanlı)."""

    return attempt < max_attempts


def plan_attempts(failure_output: str, *, max_attempts: int = MAX_ATTEMPTS) -> tuple[int, str]:
    """Kaç ek deneme yapılacağını ve gerekçesini döndürür."""

    if not (failure_output or "").strip():
        return 0, "kapı çıktısı boş; onarım anlamsız"
    if any(token in failure_output.casefold() for token in ("permission", "yetki", "erişim")):
        return 0, "yetki hatası; model denemesi çözmez"
    return max_attempts - 1, "kapı hatası modele geri beslenebilir"
