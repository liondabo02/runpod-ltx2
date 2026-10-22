"""Company foundry: found a company, hire its workers, deliver the work.

When the owner asks for something no existing company covers, the holding does
not refuse. It founds a company with a mission, capabilities and a small
workforce, writes a charter, and delivers a real document through the business
delivery module.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .business_delivery import write_deliverable

ROLE_TEMPLATES = (
    ("manager", "Müdür", ["planning", "routing", "quality_oversight"]),
    ("specialist", "Uzman", ["research", "content"]),
    ("quality", "Kalite", ["verification", "acceptance"]),
)


@dataclass
class CompanyResult:
    company_id: str
    company_name: str
    created: bool
    workers: list[str]
    charter: str
    deliverable: str
    validated: bool
    problems: list[str]
    summary: str


def _slug(text: str) -> str:
    folded = (
        text.casefold()
        .replace("ı", "i").replace("ş", "s").replace("ğ", "g")
        .replace("ü", "u").replace("ö", "o").replace("ç", "c")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    return slug[:40] or "yeni-sirket"


def _theme(request: str) -> str:
    words = [
        word for word in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]{3,}", request)
        if word.casefold() not in {
            "için", "bir", "ile", "ve", "olan", "hazırla", "yap", "istiyorum",
            "lütfen", "plan", "rapor", "oluştur",
        }
    ]
    return " ".join(words[:3]) or "genel"


def found(
    book,
    workforce,
    runtime_dir: str | Path,
    request: str,
    *,
    spec=None,
) -> CompanyResult:
    """Ensure a company exists for this request, with workers and a deliverable.

    ``spec`` verildiğinde mevcut şirket kullanılır (ör. kod projesi olmayan bir
    departman); aksi hâlde talep için yeni şirket kurulur.
    """

    runtime = Path(runtime_dir)
    theme = _theme(request)
    companies_dir = runtime / "companies"
    companies_dir.mkdir(parents=True, exist_ok=True)

    from .owner_console import synthesize_department

    created = False
    if spec is None:
        company_id = _slug(theme)
        desired = synthesize_department(request, department_id=company_id)
        existing = book.get(company_id)
        if existing is None:
            spec = book.add(desired)
            created = True
        else:
            spec = existing
    company_id = spec.department_id

    # İşçi kadrosu: departmanın kendi spec'i zaten müdür + uzmanları taşır.
    workers = [
        worker.profile.worker_id
        for worker in workforce.all()
        if str(getattr(worker.profile, "worker_id", "")).startswith(spec.department_id + "-")
        or str(getattr(worker.profile, "team_id", "")).startswith(spec.department_id)
    ]
    if not workers:
        workers = [getattr(worker, "worker_id", "") for worker in getattr(spec, "workers", ())]
        workers = [worker_id for worker_id in workers if worker_id]

    charter_dir = companies_dir / company_id
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_path = charter_dir / "CHARTER.md"
    charter = (
        f"# {spec.name}\n\n"
        f"**Kuruluş:** {request}\n\n"
        f"**Misyon:** {getattr(spec, 'mission', '') or request}\n\n"
        "## Yetenekler\n"
        + "\n".join(f"- {cap}" for cap in getattr(spec, "capabilities", ()) or ())
        + "\n\n## Kadro\n"
        + "\n".join(f"- {worker_id}" for worker_id in workers)
        + "\n\n## Çalışma biçimi\n"
        "1. Talep müdür tarafından işe bölünür.\n"
        "2. Uzman teslimatı üretir.\n"
        "3. Kalite, teslimatı kontrol listesine göre doğrular.\n"
    )
    charter_path.write_text(charter, encoding="utf-8")

    deliverable_path, validated, problems = write_deliverable(
        charter_dir, request, spec.name
    )

    summary = (
        f"{spec.name} kuruldu" if created else f"{spec.name} mevcut"
    ) + (
        f"; {len(workers)} işçi; teslimat doğrulandı"
        if validated
        else f"; {len(workers)} işçi; teslimat EKSİK: {', '.join(problems[:3])}"
    )

    record = {
        "company_id": company_id,
        "company_name": spec.name,
        "request": request,
        "created": created,
        "workers": workers,
        "validated": validated,
        "problems": problems,
    }
    (charter_dir / "company.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return CompanyResult(
        company_id=company_id,
        company_name=spec.name,
        created=created,
        workers=workers,
        charter=str(charter_path),
        deliverable=str(deliverable_path),
        validated=validated,
        problems=problems,
        summary=summary,
    )


def main(argv: list[str] | None = None) -> int:
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    request = " ".join(args).strip()
    if not request:
        print('kullanım: python -m ahos.company_foundry "talep metni"')
        return 2
    from .owner_console import build_default_console

    runtime = Path("runtime")
    console = build_default_console(runtime)
    book = console.book
    workforce = book.workforce() if hasattr(book, "workforce") else None
    if workforce is None:
        print("işgücü kaydı bulunamadı")
        return 2
    result = found(book, workforce, runtime, request)
    print(result.summary)
    print("şirket :", result.company_id)
    print("işçiler:", ", ".join(result.workers))
    print("teslimat:", result.deliverable)
    return 0 if result.validated else 1


if __name__ == "__main__":
    raise SystemExit(main())
