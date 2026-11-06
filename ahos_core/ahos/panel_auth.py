"""Panel oturum kapısı — sahip girişi, çerez, kapsam ve giriş denemesi sınırı.

`owner_auth` çekirdeğini panel HTTP katmanına bağlar. Ayrıcalıklı panel
eylemleri (onay, acil durdurma, otonomi, komut) geçerli sahip oturumu ister;
oturum yoksa istek `/owner/login` sayfasına yönlendirilir.

Bu modül ağ çağrısı yapmaz; test edilebilir saf fonksiyonlar + küçük throttle
sınıfı içerir.
"""

from __future__ import annotations

import html
import time
import urllib.parse

COOKIE = "ahos_owner"
PANEL_SCOPES = ("approvals", "authority", "stop")
SESSION_TTL = 1800

_SCOPES = {
    "/action/approve": "approvals",
    "/action/reject": "approvals",
    "/action/kill": "stop",
    "/action/start": "authority",
    "/action/loop-start": "authority",
    "/action/loop-stop": "authority",
    "/action/backup": "authority",
    "/action/command": "authority",
    "/action/autonomy/start": "authority",
    "/action/autonomy/pause": "authority",
    "/action/autonomy/resume": "authority",
    "/action/autonomy/stop": "stop",
}


def scope_for(path: str) -> str | None:
    return _SCOPES.get(path)


def cookie_token(header: str) -> str:
    for part in str(header or "").split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE:
            return urllib.parse.unquote(value.strip())
    return ""


def session_cookie(token: str, ttl_seconds: int = SESSION_TTL) -> str:
    return (f"{COOKIE}={urllib.parse.quote(token)}; HttpOnly; SameSite=Lax; "
            f"Path=/; Max-Age={max(60, int(ttl_seconds))}")


def logout_cookie() -> str:
    return f"{COOKIE}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0"


def owner_configured(runtime) -> bool:
    from . import owner_auth

    return owner_auth._owner(runtime) is not None


def login(runtime, username: str, password: str):
    from . import owner_auth

    return owner_auth.authenticate(runtime, username, password, scopes=list(PANEL_SCOPES),
                                   ttl_seconds=SESSION_TTL)


def require(runtime, cookie_header: str, path: str) -> dict:
    """(allowed, scope, session|None, reason) — istisna fırlatmaz."""

    scope = scope_for(path)
    if scope is None:
        return {"allowed": True, "scope": None, "session": None, "reason": "public"}
    token = cookie_token(cookie_header)
    if not token:
        return {"allowed": False, "scope": scope, "session": None, "reason": "no_session"}
    from . import owner_auth

    try:
        session = owner_auth.verify(runtime, token, scope=scope)
    except PermissionError as exc:
        return {"allowed": False, "scope": scope, "session": None, "reason": str(exc)}
    return {"allowed": True, "scope": scope, "session": session, "reason": "owner"}


class LoginThrottle:
    """Bellek içi kaba kuvvet sınırı: 5 hata → 5 dakika kilit."""

    def __init__(self, max_failures: int = 5, window_seconds: float = 300.0) -> None:
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[str, list[float]] = {}

    def blocked(self, client: str, now: float | None = None) -> bool:
        moment = time.time() if now is None else float(now)
        rows = [stamp for stamp in self._failures.get(client, [])
                if moment - stamp < self.window]
        self._failures[client] = rows
        return len(rows) >= self.max_failures

    def record_failure(self, client: str, now: float | None = None) -> None:
        moment = time.time() if now is None else float(now)
        self._failures.setdefault(client, []).append(moment)

    def reset(self, client: str) -> None:
        self._failures.pop(client, None)


def render_login(next_path: str = "/", error: str = "", setup: bool = False) -> str:
    action = "/owner/setup" if setup else "/owner/login"
    title = "Sahip kurulumu" if setup else "Sahip girişi"
    note = ("İlk kullanım: Harun için güçlü bir parola belirleyin (en az 12 karakter)."
            if setup else "Yalnız sahip onay verebilir; ajanlar giriş yapamaz.")
    error_html = f'<p class="err">{html.escape(error)}</p>' if error else ""
    confirm = ('<label>Parola (tekrar)<input type="password" name="confirm" required></label>'
               if setup else "")
    return f"""<!doctype html><html lang="tr"><meta charset="utf-8">
<title>AHOS · {title}</title>
<style>
body{{background:#0d1827;color:#dbe7ff;font:14px/1.5 system-ui;display:grid;place-items:center;height:100vh;margin:0}}
form{{background:#152338;border:1px solid #24395a;border-radius:12px;padding:22px;width:320px}}
h1{{font-size:16px;margin:0 0 6px}} p{{color:#8fa6c8;font-size:12px;margin:0 0 14px}}
label{{display:block;font-size:12px;color:#9fb4d6;margin-bottom:10px}}
input{{width:100%;margin-top:4px;padding:9px;border-radius:8px;border:1px solid #2c4466;background:#0f1b2c;color:#eaf2ff}}
button{{width:100%;padding:10px;border-radius:8px;border:0;background:#2f7cf6;color:#fff;font-weight:600;cursor:pointer}}
.err{{color:#ff8f8f}}
</style>
<form method="post" action="{action}">
<h1>{title}</h1><p>{note}</p>{error_html}
<input type="hidden" name="next" value="{html.escape(next_path)}">
<label>Kullanıcı<input name="username" value="harun" autocomplete="username" required></label>
<label>Parola<input type="password" name="password" autocomplete="current-password" required></label>
{confirm}
<button type="submit">{'Kur' if setup else 'Giriş'}</button>
</form></html>"""
