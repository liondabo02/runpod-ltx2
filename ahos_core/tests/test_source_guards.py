"""Kaynak seviyesinde regresyon kalkanlari.

Iki P0 hatasi da kaynak metninde/davranista gorunur:

1) ''Belge uretildi'' diye gorevi dogrudan SQL ile `completed` yapmak
   (daemon.py icindeki belge yolu bunu yapiyordu).
2) Dogrulama sirasinda kabul kaydi OLUSTURMAK: isci kendi kabul testini
   onaylayabilir hale gelir (`AHOS_PROJECT_QA_TRUSTED` kacisi).

Bu testler, ayni yolun sessizce geri donmesini engeller. Kabul testi
yetkilendirmesi yalnizca gorev ONCESI `enroll_gate()` ile yapilir.
"""

from __future__ import annotations

import ast
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "ahos"

#: Deseni mesru olarak iceren tek dosya: bypass dedektoru.
ALLOWED_SQL_SCANNER = {"completion_integrity.py"}


def direct_completion_sql_sites(folder: Path) -> list[str]:
    """`update missions set ... completed` iceren SQL dizelerini bulur."""
    hits: list[str] = []
    for path in sorted(folder.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        except (OSError, SyntaxError, UnicodeError):
            hits.append(f"{path.name}:unreadable")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            text = " ".join(node.value.casefold().split())
            if (
                "update missions set" in text
                and "status" in text
                and ("'completed'" in text or '"completed"' in text)
            ):
                hits.append(f"{path.name}:{node.lineno}")
    return hits


def write_gate(root: Path, body: str = "print('ok')\n") -> Path:
    tools = root / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    gate = tools / "check_offline.py"
    gate.write_text(body, encoding="utf-8")
    return gate


class DirectCompletionSqlTest(unittest.TestCase):
    def test_uretim_kodunda_dogrudan_sql_tamamlanma_yok(self) -> None:
        hits = [
            hit
            for hit in direct_completion_sql_sites(PACKAGE_DIR)
            if hit.split(":")[0] not in ALLOWED_SQL_SCANNER
        ]
        self.assertEqual(hits, [], f"dogrudan SQL tamamlanma yolu bulundu: {hits}")

    def test_dedektor_bilinen_kacisi_yakalar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "kacan.py").write_text(
                "SQL = \"update missions set status='completed' where mission_id=?\"\n",
                encoding="utf-8",
            )
            hits = direct_completion_sql_sites(folder)
        self.assertEqual(len(hits), 1, hits)


class AcceptanceTrustTest(unittest.TestCase):
    def test_dogrulama_guven_kaydi_olusturmaz(self) -> None:
        from ahos import acceptance

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_gate(root)
            baseline = root / ".ahos" / "acceptance-baseline.json"

            with unittest.mock.patch.dict(
                os.environ, {"AHOS_PROJECT_QA_TRUSTED": "1"}
            ):
                ok, _reason, _digest = acceptance.trusted_gate(root, baseline)

            self.assertFalse(ok, "kayit yokken dogrulama kabul etmemeli")
            self.assertFalse(
                baseline.exists(),
                "dogrulama sirasinda guven kaydi olusmamali (kendi kendini yetkilendirme)",
            )

    def test_onceden_yetkilendirilmis_proje_gecer(self) -> None:
        from ahos import acceptance
        from ahos.acceptance_bootstrap import ensure_baseline

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_gate(root)
            baseline = root / ".ahos" / "acceptance-baseline.json"

            enrolled, reason = ensure_baseline(root, baseline.parent)
            self.assertTrue(enrolled, reason)

            ok, reason, digest = acceptance.trusted_gate(root, baseline)
            self.assertTrue(ok, reason)
            self.assertIsNotNone(digest)

    def test_yetkilendirmeden_sonra_test_degisirse_reddedilir(self) -> None:
        from ahos import acceptance
        from ahos.acceptance_bootstrap import ensure_baseline

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gate = write_gate(root)
            baseline = root / ".ahos" / "acceptance-baseline.json"
            ensure_baseline(root, baseline.parent)

            gate.write_text("print('degistirildi')\n", encoding="utf-8")
            ok, reason, _digest = acceptance.trusted_gate(root, baseline)

            self.assertFalse(ok, "degistirilmis kabul testi kabul edilmemeli")
            self.assertIn("hash", reason)

    def test_dogrulama_kaydi_degistirmez(self) -> None:
        from ahos import acceptance
        from ahos.acceptance_bootstrap import ensure_baseline

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_gate(root)
            baseline = root / ".ahos" / "acceptance-baseline.json"
            ensure_baseline(root, baseline.parent)

            before = baseline.read_bytes()
            acceptance.trusted_gate(root, baseline)
            after = baseline.read_bytes()

            self.assertEqual(before, after, "dogrulama kaydi yeniden yazmamali")


if __name__ == "__main__":
    unittest.main(verbosity=2)
