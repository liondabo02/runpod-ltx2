AHOS MEMORY VAULT — OPERATIONS AND RECOVERY

Purpose
- Back up worker minds, learning, cognition, departments and the actual SQLite mission database in verified, locally stored snapshots.
- This is not consciousness, infallibility, global simultaneous file consistency, or zero data-loss guarantee.

Operation
- ahos.memory_vault.snapshot_if_due(runtime): 6-hour default interval, called in normal daemon cycles and when mission-hour quota is reached.
- Existing recent snapshot must pass SHA-256 checks, archive CRC and SQLite PRAGMA quick_check before being reused. Damaged snapshots remain intact, while a new one may be created.
- SQLite uses the online backup API (consistent transaction snapshot). Other files are sampled independently and hashed.
- Saved sets: minds, learning, cognition, brains, departments, goals, knowledge, ceo, ideas, and selected runtime metadata.
- By-name sensitive files (.env, password, token, private keys, credentials) are skipped. No secret scanning of text contents is performed: protect the backups themselves from unauthorized access.
- Runtime and existing backups are NEVER overwritten. Automatic restore and backup deletion are not implemented.
- For the current Windows runner, location is C:\actions-runner\_work\AHOS_BACKUPS\vault-<timestamp>.
- manifest.json, memories.zip and company-service.db are essential parts of each snapshot.
- ahos.memory_vault.verify(snapshot_dir) verifies all archived bytes, names, checksums and SQLite integrity.
- ahos.memory_vault.audit_worker_minds(runtime) reports missing/invalid rostered worker memory files read-only.

Safety and recovery
- Never restore into the running runtime without Harun's express approval and a separate pre-restore backup.
- First validate the snapshot, test recovery in a separate directory, and stop affected processes before any authorized repair.
- Never convert cancelled/blocked missions into successes or silently regenerate corrupted minds.
- Check learning.memory_vault in daemon-state.json for status, verified, and roster_integrity. A status=error or verified=false is a real problem, not a success.
- Archive encryption and off-host disaster recovery are NOT provided here; secure the local backup folder and separately arrange protected remote copies only with explicit approval.

Testing
  cd ahos_core
  python -m pytest -q tests/test_memory_vault.py
  python -m pytest -q tests
Use the existing control_plane_v2/.venv Python or the configured test environment.
