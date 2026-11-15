from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class CostGuard:
    daily_budget_usd: float
    spent_usd: float = 0.0
    day: date = date.today()

    def _roll_day(self) -> None:
        today = date.today()
        if today != self.day:
            self.day = today
            self.spent_usd = 0.0

    def can_spend(self, amount_usd: float) -> bool:
        self._roll_day()
        if amount_usd < 0:
            raise ValueError("amount_usd must be >= 0")
        return self.spent_usd + amount_usd <= self.daily_budget_usd

    def record(self, amount_usd: float) -> None:
        self._roll_day()
        if amount_usd < 0:
            raise ValueError("amount_usd must be >= 0")
        if not self.can_spend(amount_usd):
            raise RuntimeError("daily budget would be exceeded")
        self.spent_usd += amount_usd


# --- Maliyet modeli (config tabanlı) ----------------------------------------
# Fiyat/unit/vendor koda gömülmez: `studio/pipeline/costs.json` okunur.
# Ücretli sağlayıcı yalnızca açık approval token'ı ile seçilir; bütçe aşımı
# ücretli çağrıdan ÖNCE reddedilir (fail-closed).


class BudgetRefusal(RuntimeError):
    """Tahmini maliyet bütçe tavanını aşıyor; çağrı yapılmadan reddedilir."""


class CostCatalogError(ValueError):
    """Maliyet kataloğu eksik/geçersiz."""


def cost_catalog_path():
    from pathlib import Path

    return Path(__file__).resolve().parents[2] / "studio" / "pipeline" / "costs.json"


def load_cost_catalog(path=None) -> dict:
    import json
    from pathlib import Path

    source = Path(path) if path else cost_catalog_path()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CostCatalogError(f"maliyet kataloğu okunamadı ({source}): {exc}") from exc
    providers = payload.get("providers")
    if not isinstance(providers, dict) or not providers:
        raise CostCatalogError(f"katalog 'providers' içermeli: {source}")
    for provider_id, row in providers.items():
        if not isinstance(row, dict) or "price" not in row or "unit" not in row:
            raise CostCatalogError(f"{provider_id}: 'unit' ve 'price' zorunlu")
    return {"currency": str(payload.get("currency") or "USD"), "providers": providers}


def _price(catalog: dict, provider_id: str):
    row = catalog["providers"].get(provider_id)
    if row is None:
        raise CostCatalogError(f"bilinmeyen sağlayıcı: {provider_id}")
    return float(row["price"]), str(row["unit"])


def order_providers(providers, *, catalog: dict | None = None,
                    approval: str | None = None) -> list[dict]:
    """Ücretsiz/yerel önce; ücretli yalnızca approval token varsa sıralanır."""

    data = catalog or load_cost_catalog()
    rows = []
    for provider_id in providers:
        price, unit = _price(data, provider_id)
        rows.append({"provider_id": provider_id, "unit": unit, "price": price,
                     "paid": price > 0})
    allowed = [row for row in rows if not row["paid"] or str(approval or "").strip()]
    return sorted(allowed, key=lambda row: (row["paid"], row["price"], row["provider_id"]))


def estimate(job_plan, *, catalog: dict | None = None) -> dict:
    """Stage bazında ve toplam maliyet tahmini (çağrı yapılmaz).

    `job_plan`: [{"stage": "voice", "provider": "local-edge", "units": 12.5}, ...]
    """

    data = catalog or load_cost_catalog()
    stages: dict[str, dict] = {}
    lines = []
    total = 0.0
    for item in job_plan:
        stage = str(item.get("stage") or "unknown")
        provider = str(item.get("provider") or "")
        units = float(item.get("units") or 0.0)
        if units < 0:
            raise ValueError(f"units negatif olamaz: {item}")
        price, unit = _price(data, provider)
        cost = round(units * price, 4)
        total += cost
        bucket = stages.setdefault(stage, {"cost": 0.0, "providers": {}})
        bucket["cost"] = round(bucket["cost"] + cost, 4)
        bucket["providers"][provider] = round(bucket["providers"].get(provider, 0.0) + cost, 4)
        lines.append({"stage": stage, "provider": provider, "unit": unit,
                      "units": round(units, 3), "price": price, "cost": cost})
    return {"currency": data["currency"], "stages": stages,
            "total_cost": round(total, 4), "lines": lines,
            "paid_providers": sorted({row["provider"] for row in lines if row["price"] > 0})}


def guard(report: dict, *, episode_cap: float, provider_caps: dict | None = None) -> dict:
    """Bütçe tavanı kontrolü; aşımda `BudgetRefusal` (çağrı yapılmadan)."""

    total = float(report.get("total_cost") or 0.0)
    if episode_cap is not None and total > float(episode_cap) + 1e-9:
        raise BudgetRefusal(
            f"episode cap aşıldı: tahmini {total:.4f} > cap {float(episode_cap):.4f} "
            f"{report.get('currency')}")
    per_provider: dict[str, float] = {}
    for line in report.get("lines") or []:
        per_provider[line["provider"]] = round(
            per_provider.get(line["provider"], 0.0) + float(line["cost"]), 4)
    for provider_id, cap in (provider_caps or {}).items():
        spent = per_provider.get(provider_id, 0.0)
        if spent > float(cap) + 1e-9:
            raise BudgetRefusal(
                f"provider cap aşıldı ({provider_id}): {spent:.4f} > {float(cap):.4f}")
    return {"ok": True, "total_cost": total, "episode_cap": float(episode_cap),
            "per_provider": per_provider, "currency": report.get("currency")}


class CostLedger:
    """Bitmiş bölüm için stage bazında maliyet defteri + evidence yazımı."""

    def __init__(self, *, currency: str = "USD") -> None:
        self.currency = currency
        self.charges: list[dict] = []

    def charge(self, stage: str, provider: str, *, units: float, cost: float) -> dict:
        row = {"stage": str(stage), "provider": str(provider),
               "units": round(float(units), 3), "cost": round(float(cost), 4),
               "currency": self.currency}
        self.charges.append(row)
        return row

    def breakdown(self) -> dict:
        stages: dict[str, float] = {}
        for row in self.charges:
            stages[row["stage"]] = round(stages.get(row["stage"], 0.0) + row["cost"], 4)
        return {"currency": self.currency, "stages": stages,
                "total_cost": round(sum(row["cost"] for row in self.charges), 4),
                "charges": list(self.charges)}

    def write_evidence(self, path, *, blocked: bool = False, reason: str = "") -> dict:
        import json
        from pathlib import Path

        payload = {"schema": "ahos.cost-evidence.v1", **self.breakdown(),
                   "blocked_budget": bool(blocked), "reason": str(reason)[:300]}
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

