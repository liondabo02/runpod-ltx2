# AHOS Studio OS — Oracle coordinator: deployment and rollback

## Purpose
One natural-language owner prompt enters a persistent cloud coordinator. Oracle writes the story draft, shot plan, and durable scene/dependency tasks even while the Windows computer is off. This does not yet produce a complete cinematic video.

## Architecture
- Oracle: new systemd ahos-studio-os.service at 127.0.0.1:8799, distinct from preexisting AHOS worker services.
- State: /home/ubuntu/.local/share/ahos-studio-os/episodes.sqlite3, SQLite WAL and episode-artifacts folder, owner prompts never pushed to GitHub.
- Oracle Ollama: local 127.0.0.1:11434 API, qwen2.5-coder:3b, scene groups of three or fewer, strict JSON output.
- Windows: python tools/open_oracle_studio.py creates private SSH forwarding and opens http://127.0.0.1:8800/.
- Security: loopback only; 300-pending cap; request size cap; one model generation worker at a time; no paid API or GPU creation.

## Deployment verification
1. Clone dedicated branch feature/ahos-studio-oracle-coordinator-20261114 into /home/ubuntu/ahos-studio-coordinator without overwriting any existing directories.
2. Install ops/oracle/ahos-studio-os.service into /etc/systemd/system/ahos-studio-os.service.
3. sudo systemctl daemon-reload
4. sudo systemctl enable --now ahos-studio-os.service
5. systemctl is-active ahos-studio-os.service
6. curl --max-time 5 http://127.0.0.1:8799/health
7. Submit a story through authenticated SSH tunnel. Expect persistent episode ID, draft scene plan, and HONEST WAITING_PROVIDER statuses. No finished movie claim.
8. Test service restart without deleting the database; verified episode should still be there.

## Safe rollback
sudo systemctl disable --now ahos-studio-os.service
Leave Oracle state directory intact for recovery. No force push, no main merge, no editing existing ahos-cloud-worker.timer.

## Real remaining limitations
- Current Studio OS still does not render Hollywood-level 8-minute film. Technical Blender P12B is not approved character identity. LTX-2.5 candidate worker has not been run on licensed available GPU.
- RunPod API key was refused pods:read (403); cannot verify current paid GPU entitlement. Never bypass permissions or start billable resources without owner approval.
- Next priority: GPU/creative workers registered with real output and rights proof, indexed artifact store, independent multimodal QA, bounded shot repairs, preserved character identity across episodes.
- The local Oracle SQLite database is an appropriate single-server durable coordinator, NOT a distributed SQLite filesystem shared between machines.
