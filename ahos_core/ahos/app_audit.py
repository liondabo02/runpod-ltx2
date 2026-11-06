"""Uygulama/sayfa denetimi: eksikleri bulur ve düzeltme önerir.

Bir HTML dosyası veya klasör verilir; statik olarak incelenir (ağ yok, tarayıcı
yok). Amaç "daha iyisini çıkarmak": her bulgu bir eylem önerisiyle gelir.

Ölçülenler: başlık, açıklama, dil, viewport, Open Graph, favicon, h1,
görsel alt metni, form etiketi, bağlantı hedefleri, satır içi stil oranı,
dış kaynak sayısı, dosya boyutu, yinelenen id, PWA manifesti, erişilebilirlik
işaretleri (aria/role), kırık yerel bağlantılar.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

SEVERITY_WEIGHT = {"high": 12, "medium": 6, "low": 2}


class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict]] = []
        self.images: list[dict] = []
        self.links: list[str] = []
        self.forms: int = 0
        self.labels: int = 0
        self.inputs: int = 0
        self.ids: list[str] = []
        self.inline_styles: int = 0
        self.scripts: int = 0
        self.external_scripts: int = 0
        self.h1: int = 0
        self.aria: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {k: (v or "") for k, v in attrs}
        self.tags.append((tag, data))
        if "id" in data and data["id"]:
            self.ids.append(data["id"])
        if "style" in data:
            self.inline_styles += 1
        if "aria-" in " ".join(data.keys()) or "role" in data:
            self.aria += 1
        if tag == "img":
            self.images.append(data)
        if tag == "a" and data.get("href"):
            self.links.append(data["href"])
        if tag == "form":
            self.forms += 1
        if tag == "label":
            self.labels += 1
        if tag == "input":
            self.inputs += 1
        if tag == "h1":
            self.h1 += 1
        if tag == "script":
            self.scripts += 1
            if data.get("src", "").startswith(("http://", "https://")):
                self.external_scripts += 1


def _meta(page: _Page, name: str) -> str:
    for tag, data in page.tags:
        if tag == "meta" and (data.get("name") == name or data.get("property") == name):
            return data.get("content", "")
    return ""


def audit_html(index: str | Path | None = None, *, text: str | None = None,
               root: str | Path | None = None) -> dict:
    """Tek sayfa denetimi; `text` verilirse dosya okunmaz."""

    base = Path(root) if root else (Path(index).parent if index else Path("."))
    if text is None:
        if index is None or not Path(index).is_file():
            return {"passed": False, "score": 0, "findings": [{"severity": "high",
                    "issue": "dosya yok", "fix": "geçerli bir index.html ver"}]}
        text = Path(index).read_text(encoding="utf-8", errors="replace")

    page = _Page()
    page.feed(text)

    findings: list[dict] = []

    def add(severity: str, issue: str, fix: str) -> None:
        findings.append({"severity": severity, "issue": issue, "fix": fix})

    if not re.search(r"<title[^>]*>\s*\S", text, re.I):
        add("high", "sayfa başlığı yok", "<title> ile 50-60 karakterlik başlık ekle")
    if not _meta(page, "description"):
        add("high", "meta description yok", "arama sonuçları için 140-160 karakterlik açıklama ekle")
    if not re.search(r"<html[^>]*lang=", text, re.I):
        add("medium", "html lang eksik", '<html lang="tr"> ekle (ekran okuyucu ve SEO)')
    if "viewport" not in text:
        add("high", "viewport meta yok", 'mobil için <meta name="viewport" content="width=device-width, initial-scale=1">')
    if not _meta(page, "og:title"):
        add("low", "Open Graph etiketi yok", "paylaşımda düzgün kart için og:title/og:image ekle")
    if "rel=\"icon\"" not in text and "rel='icon'" not in text:
        add("low", "favicon yok", "sekme simgesi için <link rel=\"icon\"> ekle")
    if page.h1 == 0:
        add("medium", "h1 başlığı yok", "sayfaya tek bir anlamlı <h1> ekle")
    elif page.h1 > 1:
        add("low", f"{page.h1} adet h1 var", "tek h1 kullan, alt başlıklar için h2")
    for image in page.images:
        if not image.get("alt"):
            add("medium", "görselde alt metni yok", f"<img src=\"{image.get('src', '')[:40]}\"> için alt ekle")
    if page.inputs and page.labels < page.inputs:
        add("medium", "form alanlarında etiket eksik", "her <input> için <label for> veya aria-label ekle")
    if any(link.strip() in {"#", ""} for link in page.links):
        add("medium", "boş/# bağlantı var", "gerçek hedef ver veya <button> kullan")
    broken = []
    for link in page.links:
        if link.startswith(("http://", "https://", "mailto:", "tel:", "#", "javascript:")):
            continue
        target = (base / link.split("?")[0].split("#")[0]).resolve()
        if not target.exists():
            broken.append(link)
    if broken:
        add("high", f"{len(broken)} kırık yerel bağlantı", "hedef dosyaları oluştur: " + ", ".join(broken[:5]))
    duplicates = {i for i in page.ids if page.ids.count(i) > 1}
    if duplicates:
        add("medium", f"yinelenen id: {', '.join(sorted(duplicates)[:5])}", "id'leri benzersiz yap")
    if page.inline_styles > 10:
        add("low", f"{page.inline_styles} satır içi stil", "stilleri tek bir CSS dosyasına taşı")
    if page.external_scripts and not re.search(r"integrity=", text):
        add("low", "dış script bütünlük doğrulaması yok", "mümkünse integrity/crossorigin ekle veya yerelleştir")
    if "manifest" not in text:
        add("low", "PWA manifesti yok", "kurulabilir uygulama için site.webmanifest ekle")
    if page.aria == 0:
        add("low", "erişilebilirlik işareti yok", "gezinme ve butonlarda aria-label/role kullan")
    size_kb = len(text.encode("utf-8")) / 1024
    if size_kb > 300:
        add("medium", f"sayfa büyük: {size_kb:.0f} KB", "görsel/JS'i böl, sıkıştır, tembel yükle")

    penalty = sum(SEVERITY_WEIGHT[f["severity"]] for f in findings)
    score = max(0, 100 - penalty)
    return {
        "passed": score >= 70 and not any(f["severity"] == "high" for f in findings),
        "score": score,
        "findings": findings,
        "counts": {
            "high": sum(1 for f in findings if f["severity"] == "high"),
            "medium": sum(1 for f in findings if f["severity"] == "medium"),
            "low": sum(1 for f in findings if f["severity"] == "low"),
        },
        "measurements": {
            "kb": round(size_kb, 1), "h1": page.h1, "images": len(page.images),
            "links": len(page.links), "forms": page.forms, "inputs": page.inputs,
            "scripts": page.scripts, "inline_styles": page.inline_styles,
        },
        "scope": "statik HTML denetimi; gerçek tarayıcı performansı ve görsel tasarım ölçülmez",
    }


def audit_path(target: str | Path) -> dict:
    path = Path(target)
    if path.is_dir():
        index = path / "index.html"
        if not index.is_file():
            html_files = sorted(path.glob("*.html"))
            index = html_files[0] if html_files else None
        if index is None:
            return {"passed": False, "score": 0, "findings": [{"severity": "high",
                    "issue": "HTML dosyası yok", "fix": "klasöre index.html ekle"}]}
        report = audit_html(index, root=path)
        report["file"] = str(index)
        return report
    report = audit_html(path, root=path.parent)
    report["file"] = str(path)
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="uygulama/sayfa denetimi")
    parser.add_argument("target", help="HTML dosyası veya klasör")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    report = audit_path(args.target)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
