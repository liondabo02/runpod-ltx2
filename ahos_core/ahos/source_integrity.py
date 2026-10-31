"""Read-only Git provenance audit for AHOS internal Python imports.

A package that imports local-only, untracked Python modules may work on one
developer machine but break on a clean CI or cloud deployment.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path


def missing_tracked_imports(repository: str | Path) -> tuple[str, ...]:
    """Return exact internal import targets absent from Git's file index.

    Only files under ahos_core/ahos are analyzed. This does not import or
    execute untrusted code, open config/secrets, or modify Git/index.
    """
    repo = Path(repository)
    listing = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z", "--", "ahos_core/ahos"],
        capture_output=True, check=True, timeout=12,
    )
    paths = {Path(path) for path in listing.stdout.decode("utf-8", "replace").split("\0") if path}
    package = Path("ahos_core/ahos")
    missing: set[str] = set()

    def check(mod: Path, *, explicit: bool = False) -> None:
        candidates = (mod.with_suffix(".py"), mod / "__init__.py")
        if any(candidate in paths for candidate in candidates):
            return
        # "from .foo import bar" explicitly requires a foo module and must
        # fail even if foo.py is completely absent on a clean checkout.
        # "from . import bar" may refer to an attribute exported by __init__,
        # so in that case report only untracked modules that actually exist.
        if explicit or any((repo / candidate).is_file() for candidate in candidates):
            missing.add(mod.as_posix())

    for name in paths:
        if name.parent != package or name.suffix != ".py":
            continue
        try:
            content = (repo / name).read_text(encoding="utf-8")
            tree = ast.parse(content, filename=name.as_posix())
        except (OSError, SyntaxError, UnicodeError):
            missing.add(name.as_posix() + " [unreadable]")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    # Single-dot imports originate in ahos; multi-dot imports
                    # may target the parent package and are not considered.
                    if node.level != 1:
                        continue
                    if node.module:
                        check(package.joinpath(*node.module.split(".")), explicit=True)
                    else:
                        for alias in node.names:
                            if alias.name != "*":
                                check(package / alias.name)
                elif node.module and (
                    node.module == "ahos" or node.module.startswith("ahos.")
                ):
                    parts = node.module.split(".")[1:]
                    if parts:
                        check(package.joinpath(*parts), explicit=True)
                    else:
                        for alias in node.names:
                            if alias.name != "*":
                                check(package / alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("ahos."):
                        check(package.joinpath(*alias.name.split(".")[1:]), explicit=True)
    return tuple(sorted(missing))
