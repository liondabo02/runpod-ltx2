# AHOS-QUALITY-99 — Active Blockers

## High risk

### Q99-BLOCKER-001 — Windows coding queue lock race
Status: OPEN / SHARED-FILE OWNERSHIP CONFLICT

Observed during 100-task / four-synthetic-worker Windows stress:
`CodingSupervisorStore._locked()` can receive `PermissionError` while creating
`queue.json.lock`.

The shared implementation file `ahos_core/ahos/coding_supervisor.py` is also
modified by active branch `improve/ahos-99-conflict-safety`. AHOS-QUALITY-99
will not write that file concurrently. A later stress run passed, confirming
intermittency rather than disproving the defect.

Acceptance:
- shared-file owner fixes lock acquisition portability
- repeated Windows stress passes without PermissionError
- no duplicate claim and no lost record

### Q99-BLOCKER-002 — Real product acceptance
Status: OPEN

STUDIO-005 through STUDIO-008 still require real production assets/render/audio,
human identity/language listening acceptance, and final owner-approved release
candidate evidence.

### Q99-BLOCKER-003 — Android device E2E
Status: OPEN

`adb devices -l` returned zero connected devices. No Android success is claimed.

Acceptance:
- device visible to ADB
- APK/content hash bound to evidence
- install, launch and critical smoke pass
- evidence tied to exact commit/device/Android version

### Q99-BLOCKER-004 — Real Codex/DeepSeek separation
Status: OPEN

Zero-cost routing policy is tested, but a real two-provider builder/reviewer
execution has not been proven with zero paid cost.

## Medium / evidence gaps

- production deployment remains owner-gated and unproven
- unattended long-duration runtime evidence remains incomplete
- browser Control Center render is proven, but Android remains open
