from __future__ import annotations

import os
from dataclasses import dataclass

from .agents import AGENTS


@dataclass(frozen=True)
class PreflightResult:
    configured_roles: tuple[str, ...]
    missing_roles: tuple[str, ...]
    configured_providers: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.missing_roles


def _provider(model: str) -> str:
    return model.split('/', 1)[0] if '/' in model else 'unknown'


def check() -> PreflightResult:
    configured: list[str] = []
    missing: list[str] = []
    providers: set[str] = set()
    for role, spec in AGENTS.items():
        model = (os.getenv(spec.model_env) or '').strip()
        if model:
            configured.append(role)
            providers.add(_provider(model))
        else:
            missing.append(role)
    return PreflightResult(tuple(configured), tuple(missing), tuple(sorted(providers)))


def main() -> int:
    result = check()
    print('Miniverse multi-agent preflight')
    print('configured roles:', ', '.join(result.configured_roles) or 'none')
    print('providers:', ', '.join(result.configured_providers) or 'none')
    if result.missing_roles:
        print('missing roles:', ', '.join(result.missing_roles))
        return 2
    print('READY: all five agent model routes are configured')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
