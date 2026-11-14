# AHOS Media Factory Worker Protocol — v1 (2026-11-14)

## Exact purpose
Oracle Studio OS owns the persistent episode plan, canon and job queue. The new media queue leases dependency-ready production tasks to independently registered workers over a private SSH tunnel. Real outputs are uploaded and verified by SHA-256. Separate reviewers inspect them. This does not mean a professional cartoon has already been rendered.

### Ready software components
- tools/studio_media_queue.py: Oracle-local SQLite WAL transaction queue; leases, heartbeat, 3-attempt recovery, zero-new-spend worker registry, media upload and reviewer proof.
- tools/studio_oracle_service.py: existing localhost-only Oracle service, now with private Media Factory REST endpoints.
- tools/studio_media_worker_client.py: execute only reviewed, zero-new-spend Python backends registered in studio/pipeline/production-backends.json via --plan/--job-dir/--evidence.
- The queue starts with ZERO approved workers. Workers are not promoted automatically and no remote inference or new GPU purchase occurs.
- After a successful technical backend result the stage becomes AWAITING_QA, not PRODUCTION_READY. A second authorized reviewer must provide actual QA evidence and independently scored criteria; passing QA is still not owner approval.

## Authentication and network
Oracle server binds ONLY to 127.0.0.1:8799. GPU/media clients connect with an authorized SSH tunnel, such as worker localhost:8801 to Oracle localhost:8799. Never expose 8799 or Ollama 11434 to the Internet.

An Oracle-only administrator token is stored privately at /home/ubuntu/.local/share/ahos-studio-os/media-queue-admin.key and is created with filesystem permission 0600. Never commit, log or share it. Registration requires this token. Each separate registered worker/reviewer gets an independent secret token.

Registration requires: worker_id, role worker/reviewer, capabilities, runtime_proof_sha256, runtime_status VERIFIED_RUNTIME, license_status COMMERCIAL_REVIEWED, region EU and new_spend_eur 0. The administrator must independently verify runtime and commercial rights before registration.

### REST actions (base: http://127.0.0.1:8799/api/media)
POST /register — admin only. Returns a worker token once.
GET /status — admin only. Reports states and registered workers, no secrets.
POST /lease — worker token, request seconds=120, response with job_id, lease_key, payload (ahos.media.job.v1).
POST /heartbeat — worker token and active job_id+lease_key. Renew before TTL expires.
PUT /artifact — upload true file bytes. Headers Authorization, X-AHOS-Job-ID, X-AHOS-Filename, X-AHOS-SHA256, X-AHOS-Lease-Key (media worker), and Content-Length. Current cap: 64 MiB per file.
POST /complete — worker token and lease key, valid schema ahos.media.result.v1, real uploaded artifacts and license/cost record.
POST /fail — worker token and lease key, explicit error; job returns to queue (maximum 3 attempts).
POST /review-claim — independent reviewer token; claim an AWAITING_QA job.
GET /artifact?job_id=...&filename=... — claimed reviewer-only download of worker artifact.
PUT /artifact — reviewer token uploads independent QA evidence file after claiming.
POST /review — claimed reviewer, proof filename+SHA, scores and a real external review method. Weak categories fail the shot and requeue a bounded correction.

Only ONE media lease per worker. Every claim uses a random active lease key. A stale lease cannot submit/extend after another worker receives a retry. SQLite ensures transactional claims. Output file hashes are recalculated on the Oracle server.

### Worker input, typed payload
The production job includes episode_id, task_id, capability, kind, series_id, cast, languages, story_direction, dependencies, cost_policy, and production_ready=false. The worker is not allowed to substitute different character identities or infer missing asset rights. The canonical identity data must come from the existing accepted Studio-16 series reference registry.

### Backend CLI contract (DeepSeek)
Existing dispatcher adapter interface:

    python tools/studio_backends/<backend_name>.py --plan <job_dir>/production-plan.json --job-dir <job_dir> --evidence <job_dir>/backend-evidence.json

The evidence JSON must have exact stage, status PASSED, cost_eur=0, commercial_license_verified true only when evidenced, and artifact list {kind,path,sha256}. Artifact paths must stay inside job_dir and must be real verified media files.

The worker client validates the evidence, source file bytes, filenames and hashes, uploads each to Oracle, and submits a result:

    {
      "job_id":"<lease-job-id>",
      "lease_key":"<lease-key>",
      "result":{
        "schema":"ahos.media.result.v1",
        "capability":"character_model",
        "technical_status":"PASSED",
        "new_spend_eur":0,
        "license_status":"COMMERCIAL_REVIEWED",
        "artifacts":[{"filename":"real-model.glb","sha256":"<real-sha256>"}],
        "creative_approved":false,
        "production_ready":false
      }
    }

Real MP4/video artifacts require valid container, ffprobe-audited video/audio stream, positive duration and review-quality resolution. Model GLB/BLEND, WAV and other stage outputs require appropriate format signatures. Technical integrity never substitutes for independent visual/creative QA.

Nine independent QA scores are required: identity, acting, motion, continuity, cinematography, story_adherence, audio, child_safety and rights. Major identity failures are NEVER averaged away. The reviewer is a different identity than the producer and must upload a hash-matching proof file. Even QA_PASS remains distinct from full professional release and owner signoff.

## What this DOES NOT deliver yet
- No actual verified LTX-2.5, Wan Animate, TRELLIS.2 GPU or licensed child-grade audio/lipsync runtime has been registered.
- No completed 8-minute video or independent validated visual/audio judge is produced by these software tests.
- Initial transport limit is 64 MiB per file; long final MP4/media requires audited chunked upload or object storage before full operation.
- Oracle currently uses SQLite WAL locally. Remote GPU workers NEVER open/share the DB directly; all calls use authenticated HTTP over SSH forwarding.
- RunPod API key previously lacked pods:read and returned HTTP 403. Do not bypass entitlement or launch billable resources without explicit owner permission.

## Acceptance for integration
1. DeepSeek demonstrates a real production media worker, licence proof, GPU resources/expense and a 5-second source-identity-locked shot on existing authorized capacity.
2. Admin reviews it, registers it as an explicit capability, safely delivers its token and starts the isolated worker client.
3. Oracle leases the real task; it uploads real artifact(s) and an independent reviewer verifies visual identity, motion, child safety and commercial rights.
4. Oracle records QA_PASS for the stage and unlocks the next dependency. Failed shots are requeued up to the allowed retry limit.
5. The film is only ready when every stage, professional gate and owner final approval has actual evidence.

No force push, no merge to main and no new billable GPU or API access as part of this protocol.


## Canonical reference and retry-history hardening (14 November 2026)

The production assignment now includes \`canonical_source=owner_accepted_roster_v1\` and \`canonical_reference_sha256\`, an immutable mapping for the characters in the episode. A media task is NOT placed in the runnable queue when the episode's 'canon' task lacks verified SHA values. This fixes the previous unsafe worker interface that only transmitted names such as "aden" and "kaan".

A production worker with an active lease can call:
- GET /api/media/reference?episode_id=<episode_id>&character=<canonical_character_id>
- Authorization: Bearer <registered-worker-token>
- Response: exact owner-approved PNG bytes, X-Reference-SHA256 header and Content-Length.

The server verifies the original reference bytes against the SHA snapshot recorded at story intake. A request from a worker without an active lease for that episode, for an unknown character or for a changed source is rejected. The worker client fetches and checks SHA-256 again; it refuses to run a Blender/AI model if a canonical reference is missing, then supplies local reference file paths in the backend production plan as approved_reference_files.

New guest characters are candidate assets, not approved canonical actors; they need source/rights review and a successful independent identity gate before future scenes reuse the guest.

The retry system also keeps every earlier attempt's artifact files and metadata in media_artifact_history while permitting the next attempt to upload the SAME file name (e.g. model.glb). No old bytes are deleted on QA failure; filenames are unblocked for corrected renders, and attempts remain limited to three. Tests cover expired leases, stale keys and reusing filenames after failed QA.

These guardrails protect the exact canonical source and queue provenance, but do not yet replace human/validated multimodal verification of every generated character and final episode.
