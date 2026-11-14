# AHOS Studio OS | Oracle worker queue deployment & DeepSeek contract

Status: worker queue code and staged media pipeline pass 56 targeted GitHub Actions tests. Not yet live on Oracle, no professional film delivered.

## Powershell commands on authorized Windows Kahta machine
```powershell
$repo = 'C:\actions-runner\_work\AHOS-STUDIO-WORKER-QUEUE-20261114'
$record = 'C:\actions-runner\_work\AHOS-CLOUD-FED-20261024\ops\oracle\last-instance.json'
if (-not (Test-Path $repo) -or -not (Test-Path $record)) { throw 'Required private repo or Oracle record is missing' }
$dirty = git -C $repo status --porcelain
if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'Existing worktree is dirty; stop, do not overwrite' }
git -C $repo fetch origin feature/ahos-studio-worker-queue-20261114
if ($LASTEXITCODE -ne 0) { throw 'Git fetch failed' }
git -C $repo merge --ff-only origin/feature/ahos-studio-worker-queue-20261114
if ($LASTEXITCODE -ne 0) { throw 'Fast-forward-only update failed' }
python "$repo\tools\deploy_media_queue_oracle.py" --record $record --mode preflight
if ($LASTEXITCODE -ne 0) { throw 'Oracle preflight failed; stop' }
python "$repo\tools\deploy_media_queue_oracle.py" --record $record --mode deploy
if ($LASTEXITCODE -ne 0) { throw 'Deployment failed; inspect rollback and logs' }
python "$repo\tools\deploy_media_queue_oracle.py" --record $record --mode verify
if ($LASTEXITCODE -ne 0) { throw 'Post-deploy verification failed' }
```

No passwords, SSH key bytes or API tokens are printed. The script snapshots the episode SQLite database and systemd unit, clones a dedicated Oracle checkout, restarts only ahos-studio-os.service, checks loopback health and authenticated media queue state, and rolls back the service unit on a failed health check. It refuses overwriting an existing target directory.

## Media worker versioned job contract
- Oracle 127.0.0.1:8799 is SSH-forwarded to worker localhost:8801; NEVER publicly expose 8799 or 11434.
- Only reviewed runtime with EU-approved commercial rights, zero unapproved spend and true SHA proof may be enrolled by an administrator.
- Input schema: ahos.media.job.v1 with episode_id, task_id, cast, canonical_reference_sha256, dependencies, specific scene_plan/plot_beat, shotplan_sha256, cost_policy, production_ready=false.
- Worker downloads immutable reference images via GET /api/media/reference and QA-approved upstream model/rig/scene bytes via GET /api/media/dependencies and GET /api/media/dependency; all verified by SHA locally.
- Generic backend CLI: python tools/studio_backends/NAME.py --plan JOB/production-plan.json --job-dir JOB --evidence JOB/backend-evidence.json
- Backend evidence requires correct stage, status PASSED only for real execution, cost_eur 0, commercial_license_verified true only with proof, and actual artifact kind/path/sha256.
- Worker may only submit ahos.media.result.v1. Oracle marks AWAITING_QA, NOT a finished film.
- Separate reviewer claims the work and uploads a real QA proof, scoring identity, acting, motion, continuity, cinematography, story_adherence, audio, child_safety and rights. Failed scenes requeue with old evidence archived.
- A registered worker can run: python tools/studio_media_worker_client.py --server http://127.0.0.1:8801 --repo-root PATH_TO_APPROVED_REPO --job-root PATH_TO_PRIVATE_JOBDIR
- Worker token must be injected as AHOS_MEDIA_WORKER_TOKEN from private approved storage; never commit or paste it.

## DeepSeek media factory priority
Continue ONLY on its separate feature/ahos-media-factory-deepseek branch and worktree AHOS-MEDIA-FACTORY-DS. Do not modify the Oracle service, queue and other agents' branches.
1. Generic character asset generation, real source-approved Blender/GLB with UV/rig, no one-character hardcoding; preserve canonical image and source SHA.
2. Real rig, skinning, face controls, walking, blinking and interacting with props on TWO visually distinct recurring characters.
3. Plan-driven real 3-5-second animated shot with camera and natural audio (not a static garden, sliding posters, test tone or title card).
4. Natural licensed Turkish dialogue and forced phoneme/viseme alignment, a true lip-synced actor close-up.
5. Implement per-stage adapters and their real artifact proofs; connect to the Oracle private job API when independently qualified.
6. On already-owned and verified GPU only, compare Blender, Wan 2.2 Animate and LTX-2.5 using the SAME canonical identity and scene; no new paid resources or bypass of RunPod pods:read restriction.
7. Demonstrate two different stories with identical approved actor/voice assets and a failing-shot QA repair; expand to real 8-minute exports only with evidence.

## Not yet completed
Oracle queue deployment cannot be claimed until --mode verify succeeds on authorized server.
Real GPU media workers, approved rigs/voices, independent multimodal visual critic, >64 MiB media transfer and Hollywood-level finished episodes remain separate verified acceptance gates.
Never set PRODUCTION_READY=true from software test counts or existence of an MP4.
