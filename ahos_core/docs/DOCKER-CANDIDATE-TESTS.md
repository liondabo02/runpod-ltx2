# Candidate tests in local Docker

`DockerTestExecutor` runs candidate pytest commands inside a Linux container.
This is **local Docker isolation**, not proof of the existing off-host research
sandbox policy. Host/model requests remain outside this backend. No automatic
image downloads or dependency installation occur.

Configure an existing, trusted image by immutable `sha256:` image ID or repository
`@sha256:` digest. It must contain Python and every required test dependency,
with no declared image volumes. Its provenance and dependency contents require
review. A mutable tag is rejected. Only Python `-m pytest` argv is mapped into
the image; a Windows executable path is never executed inside the container.

The source snapshot contains tracked candidate files, indexed blobs omitted by
sparse checkout, and new files within approved paths. Candidate deletions remain
deleted. Git metadata, runtime directories, virtual environments, dotenv files,
common credential files, keys, links and special files are excluded/rejected.
This is filename-based filtering, not a guarantee that arbitrary source files
contain no secrets; do not commit credentials into the source repository.

Source travels through standard input as a bounded archive. There are no host
bind mounts or Docker socket mounts. Container restrictions include no network,
a read-only root, non-root UID, dropped capabilities, no-new-privileges, CPU,
RAM and process caps, and bounded temporary filesystems. Test subprocesses receive
a fixed environment rather than the host's API keys. The Docker CLI also uses a
fresh configuration directory and a small environment allowlist. An explicit
local `unix://` or `npipe://` endpoint can be supplied when the default endpoint
is not the desired Docker daemon.

Timeouts kill the container and CLI process; output is drained with a fixed
capture cap. Cleanup is verified before results are returned. Any unavailable
image, invalid command, container setup/inspection/cleanup error blocks the task;
there is no fallback to host execution. Receipts include source/log hashes and
explicitly record `off_host_verified: false`.

Unit tests verify command restrictions, archive contents, environment isolation,
resource flags, timeout handling, output caps and cleanup failure behavior.
Real Docker execution and network/host-access containment still require an
integration probe on the configured daemon. Docker version alone is not evidence
of containment. Tests depending on host binaries, external network, native
executables in writable tmpfs or Windows behavior may need an explicitly reviewed
image/test strategy rather than weakened isolation.


The PID cap is 128 (processes and threads share this budget). The parallel
11-department acceptance test exceeded the initial cap of 64 in an actual
Windows Docker run, so the bounded cap was raised without reducing coverage.
Each receipt records the effective limits; a failed new call clears any prior
receipt. Containers are fresh per invocation, so application threads cannot
carry over from a completed, verified-cleaned previous invocation. Host/daemon
resource pressure can still affect a run and should be diagnosed separately.
