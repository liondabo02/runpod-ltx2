from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

BROWSER_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


@dataclass(frozen=True, slots=True)
class BrowserCheck:
    ok: bool
    url: str
    exit_code: int
    problems: tuple[str, ...] = ()
    dom_bytes: int = 0
    screenshot: str | None = None
    seconds: float = 0.0

    def summary(self) -> str:
        if self.ok:
            return f"tarayıcı: sayfa yüklendi ({self.dom_bytes} bayt DOM, {self.seconds:.1f}s)"
        return "tarayıcı: " + "; ".join(self.problems[:3])


def find_browser() -> str | None:
    for candidate in BROWSER_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


Runner = Callable[[list[str], float], subprocess.CompletedProcess]


def _default_runner(argv: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _file_url(path: Path) -> str:
    return "file:///" + path.resolve().as_posix().lstrip("/")


def check_page(
    html_path: str | Path,
    artifacts_dir: str | Path,
    *,
    browser: str | None = None,
    runner: Runner | None = None,
    timeout: float = 90.0,
) -> BrowserCheck:
    """Load the page in headless Chrome/Edge and assert a healthy document."""

    page = Path(html_path)
    out_dir = Path(artifacts_dir)
    started = time.time()

    if not page.exists():
        return BrowserCheck(False, _file_url(page), -1, ("index.html bulunamadı",))

    binary = browser or find_browser()
    if binary is None:
        return BrowserCheck(True, _file_url(page), 0, ("tarayıcı yok; kontrol atlandı",))

    out_dir.mkdir(parents=True, exist_ok=True)
    run = runner or _default_runner
    url = _file_url(page)
    common = [
        binary,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    try:
        dump = run([*common, "--virtual-time-budget=5000", "--dump-dom", url], timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BrowserCheck(
            False,
            url,
            -1,
            (f"tarayıcı çalıştırılamadı: {exc}",),
            seconds=time.time() - started,
        )

    problems: list[str] = []
    dom = dump.stdout or ""
    if dump.returncode != 0:
        problems.append(f"tarayıcı çıkış kodu {dump.returncode}")
    if len(dom) < 200:
        problems.append("DOM boş/çok kısa")
    lowered = dom.lower()
    for marker in ("<html", "<head", "<body"):
        if marker not in lowered:
            problems.append(f"DOM'da {marker} yok")
    if "data-game" not in dom and "id=\"stage\"" not in dom and "id='stage'" not in dom:
        problems.append("oyun arayüzü işaretleri bulunamadı")

    screenshot = out_dir / "browser.png"
    try:
        run(
            [
                *common,
                "--virtual-time-budget=5000",
                "--window-size=1200,900",
                f"--screenshot={screenshot}",
                url,
            ],
            timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        screenshot = None

    return BrowserCheck(
        ok=not problems,
        url=url,
        exit_code=dump.returncode,
        problems=tuple(problems),
        dom_bytes=len(dom),
        screenshot=str(screenshot) if screenshot and screenshot.exists() else None,
        seconds=round(time.time() - started, 2),
    )


def render_report(check: BrowserCheck) -> str:
    lines = [
        "# Tarayıcı Davranış Kontrolü",
        "",
        f"- **URL:** `{check.url}`",
        f"- **Sonuç:** {'GEÇTİ' if check.ok else 'BAŞARISIZ'}",
        f"- **Çıkış kodu:** {check.exit_code}",
        f"- **DOM boyutu:** {check.dom_bytes} bayt",
        f"- **Süre:** {check.seconds}s",
        "",
        "## Sorunlar",
        "",
    ]
    lines += [f"- {problem}" for problem in check.problems] or ["Yok."]
    if check.screenshot:
        lines += ["", f"![Sayfa]({Path(check.screenshot).name})"]
    lines.append("")
    return "\n".join(lines)
