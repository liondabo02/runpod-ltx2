"""Rollback / geri alma.

- snapshot(project_root, files: list[str]) -> Path
  · artifacts/rollback/<YYYYmmdd-HHMMSS>/ altına dosyaların kopyasını al
  · döndür: snapshot dizini
- restore(snapshot_dir, project_root) -> int  (geri yüklenen dosya sayısı)
- last(artifacts_root) -> Path | None  (en yeni snapshot)
- __main__: python -m ahos.rollback --last  → en yeni snapshot'ı geri yükler, sayı yazdırır
"""

import json
import os
import shutil
import time
from pathlib import Path

from datetime import datetime

ARTIFACTS_ROOT = Path('artifacts')


def snapshot(project_root: str | Path, files: list[str] | None = None) -> Path:
    """Project rootundaki dosyaların snapshotını al.

    Args:
        project_root: proje kök dizini
        files: snapshot alınacak dosya listesi (None = tüm önemli dosyalar)

    Returns:
        Oluşturulan snapshot dizini
    """
    project_root = Path(project_root)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    base = ARTIFACTS_ROOT / "rollback"
    for suffix in range(1000):
        snapshot_dir = base / (timestamp if suffix == 0 else f"{timestamp}-{suffix}")
        try:
            snapshot_dir.mkdir(parents=True, exist_ok=False)
            break
        except FileExistsError:
            continue
    else:
        raise FileExistsError("Rollback snapshot adı oluşturulamadı")
    
    # Önemli dosyalar (eğer specified None ise)
    if files is None:
        # Önemli dosya desenleri
        patterns = [
            "ahos_core/ahos/*.py",
            "ahos_core/config/*.json",
            "ahos_core/tests/*.py",
        ]
        # Basit implementasyon: mevcut klasördeki tüm .py ve .json dosyaları
        all_files = list(project_root.rglob("*.py")) + list(project_root.rglob("*.json"))
        files = [str(f.relative_to(project_root)) for f in all_files if f.is_file()]
    
    copied = 0
    root = project_root.resolve()
    for filepath in files:
        relative = Path(filepath)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Snapshot yolu proje dışına çıkamaz: {relative.name}")
        source = project_root / relative
        if source.is_symlink() or not source.resolve().is_relative_to(root):
            raise ValueError(f"Snapshot kaynağı proje dışına çıkamaz: {relative.name}")
        if source.is_file():
            target = snapshot_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied += 1
    
    return snapshot_dir


def restore(snapshot_dir: Path, project_root: Path) -> int:
    """Snapshot'tan dosyaları geri yükle.

    Args:
        snapshot_dir: geri yüklenecek snapshot dizini
        project_root: dosyaların yükleneceği proje kök dizini

    Returns:
        Geri yüklenen dosya sayısı
    """
    snapshot_dir = Path(snapshot_dir)
    project_root = Path(project_root)
    
    if not snapshot_dir.exists():
        return 0
    
    restored = 0
    root = project_root.resolve()
    for filepath in snapshot_dir.rglob("*"):
        if filepath.is_symlink():
            raise ValueError("Sembolik bağlantıdan rollback yapılamaz")
        if filepath.is_file():
            relative = filepath.relative_to(snapshot_dir)
            target = project_root / relative
            if target.is_symlink() or not target.resolve().is_relative_to(root):
                raise ValueError("Rollback hedefi proje dışına çıkamaz")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(filepath, target)
            restored += 1
    
    return restored


def last(artifacts_root: Path = None) -> Path | None:
    """En yeni snapshot'ı bul."""
    root = Path(artifacts_root) if artifacts_root else ARTIFACTS_ROOT / "rollback"
    
    if not root.exists():
        return None
    
    # Tüm rollback snapshot'larını bul ve tarihe göre sırala
    snapshots = list(root.iterdir())
    if not snapshots:
        return None
    
    # Tarih formatı: YYYYmmdd-HHMMSS
    def get_timestamp(d):
        return d.name
    
    snapshots.sort(key=get_timestamp, reverse=True)
    return snapshots[0]


def main():
    """__main__ entrance."""
    snapshot_dir = last()
    if snapshot_dir is None:
        print("No snapshots found")
        return
    
    project_root = Path(".")
    restored = restore(snapshot_dir, project_root)
    print(f"Restored {restored} files from {snapshot_dir.name}")


if __name__ == "__main__":
    main()
