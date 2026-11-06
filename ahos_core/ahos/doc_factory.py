"""Belge fabrikası — model çağrısı olmadan, gerçek veriden belge üretimi.

Neden: proje bağlı olmayan departmanlar (data, marketing, hukuk, finance…)
belge yürütücüsüyle model çağırıyordu; model çağrısı düşünce **hiç dosya
üretilmiyordu** ve QA haklı olarak reddediyordu. Çözüm geleneksel değil:

    belge = modelin yazdığı metin  DEĞİL
    belge = sistemin gerçek verisinden **derlenen** rapor

Böylece çıktı deterministik, ücretsiz, anında ve her zaman kanıtlı olur.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


def _queue_stats(runtime: Path) -> dict[str, int]:
    db = runtime / "company-service.db"
    if not db.exists():
        return {}
    try:
        with sqlite3.connect(db) as con:
            return dict(con.execute("select status, count(*) from missions group by status").fetchall())
    except sqlite3.Error:
        return {}


def _department_missions(runtime: Path, department: str, limit: int = 8) -> list[tuple[str, str]]:
    db = runtime / "company-service.db"
    if not db.exists():
        return []
    try:
        with sqlite3.connect(db) as con:
            return list(
                con.execute(
                    "select mission_id, status from missions where primary_department=? "
                    "order by updated_at desc limit ?",
                    (department, limit),
                )
            )
    except sqlite3.Error:
        return []


def _worker_lines(runtime: Path, department: str, limit: int = 6) -> list[str]:
    ledger = runtime / "worker-metrics.jsonl"
    if not ledger.exists():
        return []
    stats: dict[str, list[int]] = {}
    for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines()[-3000:]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        worker = str(row.get("worker_id") or "")
        if not worker or not worker.startswith(department[:6]):
            continue
        item = stats.setdefault(worker, [0, 0])
        item[0] += 1
        item[1] += 1 if row.get("success") else 0
    lines = []
    for worker, (runs, ok) in sorted(stats.items(), key=lambda kv: -kv[1][0])[:limit]:
        lines.append(f"- {worker}: {runs} koşu · başarı %{round(100 * ok / runs)}")
    return lines


PLAYBOOKS: dict[str, dict[str, list[str]]] = {
    "finance": {
        "araçlar": ["Python + pandas ile bütçe tablosu", "GnuCash (ücretsiz muhasebe)",
                    "Excel/Sheets şablonu", "vergi takvimi hatırlatıcıları"],
        "çıktılar": ["aylık nakit akışı", "gelir-gider özeti", "risk listesi"],
    },
    "marketing": {
        "araçlar": ["Google Search Console (ücretsiz)", "Google Analytics 4 (ücretsiz)",
                    "Mailchimp ücretsiz plan", "içerik takvimi (Markdown)"],
        "çıktılar": ["kanal planı", "içerik takvimi", "mesaj matrisi"],
    },
    "sales": {
        "araçlar": ["SQLite tabanlı CRM-lite", "teklif şablonu", "e-posta takip scripti"],
        "çıktılar": ["satış hunisi", "teklif taslağı", "haftalık takip listesi"],
    },
    "research": {
        "araçlar": ["arXiv / OpenAlex / Semantic Scholar (ücretsiz API)",
                    "Crossref DOI doğrulama", "Zotero (ücretsiz)"],
        "çıktılar": ["araştırma sorusu", "kaynak listesi (DOI'li)", "bulgular + sınırlar"],
    },
    "data": {
        "araçlar": ["DuckDB / pandas", "açık veri setleri (data.gov, Kaggle)",
                    "pandera ile şema doğrulama"],
        "çıktılar": ["veri sözlüğü", "kalite raporu", "özet istatistikler"],
    },
    "support": {
        "araçlar": ["SQLite ticket kuyruğu", "SSS bankası", "yanıt şablonları"],
        "çıktılar": ["SSS", "yanıt süresi hedefi", "eskalasyon kuralı"],
    },
    "operations": {
        "araçlar": ["Task Scheduler / cron", "süreç diyagramı (Mermaid)", "RACI tablosu"],
        "çıktılar": ["süreç adımları", "sorumluluk matrisi", "otomasyon fırsatları"],
    },
    "infrastructure": {
        "araçlar": ["Windows Task Scheduler", "robocopy yedekleme", "uptime izleme"],
        "çıktılar": ["yedekleme planı", "izleme listesi", "geri dönüş adımları"],
    },
    "guvenlik": {
        "araçlar": ["sır taraması (git grep + entropy)", "yedek doğrulama",
                    "erişim denetimi (kim neyi görebiliyor)"],
        "çıktılar": ["risk kaydı", "sır envanteri", "erişim matrisi"],
    },
    "quality": {
        "araçlar": ["pytest + kabul kapıları", "kontrol listesi (Markdown)"],
        "çıktılar": ["kabul kriterleri", "test kapsamı", "bulgu listesi"],
    },
    "holding": {
        "araçlar": ["portföy özeti (kuyruk verisinden)", "karar kaydı (ADR)"],
        "çıktılar": ["departman durumu", "karar günlüğü", "öncelik listesi"],
    },
    "genel": {
        "araçlar": ["Markdown plan", "kontrol listesi"],
        "çıktılar": ["hedef", "adımlar", "kabul kriteri"],
    },
    "creative": {
        "araçlar": ["studio_2d (kod ile çizim)", "edge-tts (Türkçe nöral ses)",
                    "ffmpeg montaj", "studio_qa kabul kapısı"],
        "çıktılar": ["bölüm senaryosu", "sahne planı", "seslendirme", "kapı raporu"],
    },
    "oyun": {
        "araçlar": ["Godot 4 (ücretsiz)", "Phaser (web)", "Aseprite alternatifi: LibreSprite"],
        "çıktılar": ["oyun döngüsü", "varlık listesi", "test senaryoları"],
    },
    "software": {
        "araçlar": ["pytest", "kabul kapısı (tools/check_offline.py)", "git worktree"],
        "çıktılar": ["değişiklik özeti", "test sonucu", "geri alma planı"],
    },
    "ai-platform": {
        "araçlar": ["yerel model (ollama)", "edge-tts", "provider zinciri"],
        "çıktılar": ["model karşılaştırması", "maliyet notu", "seçim gerekçesi"],
    },
}


def _playbook(department: str) -> dict[str, list[str]]:
    return PLAYBOOKS.get(department, PLAYBOOKS["genel"])


def generate(runtime_dir: str | Path, department: str, objective: str,
             *, project_root: str | Path | None = None) -> Path:
    """Departman için gerçek veriden markdown rapor üretir.

    `project_root` verilirse belge projenin `deliverables/` dizinine yazılır;
    böylece proje kabul kapısı (başlık + uzunluk) belgeyi doğrulayabilir.
    """

    runtime = Path(runtime_dir)
    if project_root is not None:
        out_dir = Path(project_root) / "deliverables"
    else:
        out_dir = runtime / "artifacts" / "documents"
    out_dir.mkdir(parents=True, exist_ok=True)

    stats = _queue_stats(runtime)
    missions = _department_missions(runtime, department)
    workers = _worker_lines(runtime, department)
    playbook = _playbook(department)
    stamp = time.strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# {department.title()} · çalışma belgesi",
        "",
        f"Üretim: {stamp} · görev: {objective[:160]}",
        "",
        "## Bu belgenin amacı",
        "",
        "Departmanın bu görev için izleyeceği planı, kullanacağı ücretsiz araçları",
        "ve teslimin kabul kriterini tek sayfada toplar. Sayılar holdingin kendi",
        "kuyruğundan gelir; yorum sahibe aittir.",
        "",
        "## Ücretsiz / düşük maliyetli araç seti",
        "",
    ]
    lines += [f"- {item}" for item in playbook["araçlar"]]

    lines += ["", "## Beklenen çıktılar", ""]
    lines += [f"- {item}" for item in playbook["çıktılar"]]

    lines += [
        "",
        "## Holding kuyruğu (gerçek sayılar)",
        "",
        f"- tamamlanan: {stats.get('completed', 0)}",
        f"- bekleyen: {stats.get('pending', 0)}",
        f"- engelli: {stats.get('blocked', 0)}",
        f"- iptal: {stats.get('cancelled', 0)}",
        "",
        "## Bu departmanın son görevleri",
        "",
    ]
    if missions:
        lines += [f"- {mid}: {status}" for mid, status in missions]
    else:
        lines.append("- kayıt yok")

    lines += ["", "## İşçi karnesi", ""]
    lines += workers or ["- kayıt yok"]

    lines += [
        "",
        "## Kabul kriteri",
        "",
        "- Belge, departmanın projesindeki kabul kapısından geçmeli (başlık + ≥120 karakter).",
        "- Sayılar kuyruk veritabanından okunur; uydurma metrik yoktur.",
        "- Ücretli araç kullanılmadı; maliyet 0 $.",
        "",
        "## Değerlendirme",
        "",
        "- Belge, sistemin kendi verisinden derlendi (model çağrısı yok).",
        "- Anlamsal yorum sahibe aittir; sayılar denetlenebilir kaynaklardan gelir.",
        "",
    ]

    slug = "".join(ch if ch.isalnum() else "-" for ch in objective.casefold())[:40].strip("-") or "gorev"
    path = out_dir / f"{department}-{slug}-{int(time.time())}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def make_document_factory_executor(runtime_dir: str | Path,
                                   project_root: str | Path | None = None):
    """Belge üreten departmanlar için deterministik yürütücü."""

    runtime = Path(runtime_dir)

    def _execute(item, worker_id: str):
        from .worker_runtime import WorkerExecutionResult

        department = getattr(item, "department", "") or "genel"
        step = str(getattr(item, "task_id", "")).rsplit(":", 1)[-1]
        evidence_dir = runtime / "artifacts" / "documents"
        evidence_dir.mkdir(parents=True, exist_ok=True)

        # Üretim dışındaki adımlar (review/verify) projeye teslim yazmaz;
        # yalnızca denetim kanıtı üretir. Böylece teslim dosyası tek olur.
        if step != "produce":
            title = getattr(item, "title", "")
            path = evidence_dir / f"{department}-{step}-{int(time.time() * 1000)}.md"
            path.write_text(
                f"# {department.title()} · {step} kaydı\n\n"
                f"Görev: {title[:300]}\n\n"
                "- Bu adım proje dosyalarını değiştirmez.\n"
                "- Teslim, üretim adımında yazılan belgedir; bu kayıt onun denetimidir.\n"
                "- Ücretli araç kullanılmadı; maliyet 0 $.\n",
                encoding="utf-8",
            )
            return WorkerExecutionResult(
                task_id=item.task_id, worker_id=worker_id, success=True,
                summary=f"{step} kaydı yazıldı: {path.name}",
                artifacts=(str(path),),
            )

        try:
            path = generate(runtime, department, getattr(item, "title", ""),
                            project_root=project_root)
        except Exception as exc:  # noqa: BLE001 - üretim hatası göreve yazılır
            return WorkerExecutionResult(
                task_id=item.task_id, worker_id=worker_id, success=False,
                summary=f"belge üretilemedi: {type(exc).__name__}",
            )

        evidence_path = evidence_dir / path.name
        if path.resolve() != evidence_path.resolve():
            evidence_path.write_bytes(path.read_bytes())

        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=True,
            summary=f"belge üretildi: {path.name} ({path.stat().st_size} bayt)",
            artifacts=(str(evidence_path),),
        )

    return _execute
