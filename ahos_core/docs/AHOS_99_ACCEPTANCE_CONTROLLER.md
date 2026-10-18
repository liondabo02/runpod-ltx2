# AHOS 99% Acceptance Controller

The acceptance controller is the final read-only composition layer.

It combines:

1. the existing core verification baseline,
2. the production proof bundle,
3. the live runtime audit,
4. the layered requirement audit,
5. the weighted maturity model, and
6. the strict final readiness gate.

A result can report **ready=true** only when all evidence is tied to the same
commit and platform, the runtime is healthy, every production proof is present,
all platform and department requirements are proven, and the effective score is
at least 99%.

The controller performs no deployment, publishing, payment, restore, restart,
or privileged mutation.
