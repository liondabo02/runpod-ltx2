param([Parameter(Mandatory=$true)][string]$ImageDigest)
$ErrorActionPreference = 'Stop'
if ($ImageDigest -notmatch '^itzcrazykns1337/vane@sha256:[a-f0-9]{64}$') {
    throw 'Use the reviewed immutable Vane image digest, not a mutable tag.'
}
& docker image inspect $ImageDigest *> $null
if ($LASTEXITCODE -ne 0) { throw 'Reviewed image is not installed locally.' }
$existing = & docker ps -a --filter 'name=^/ahos-vane$' --format '{{.Names}}'
if ($existing) {
    $actual = & docker inspect ahos-vane --format '{{.Config.Image}}'
    if ($actual -ne $ImageDigest) { throw 'Existing Vane uses a different image; review migration first.' }
    & docker start ahos-vane
} else {
    & docker run -d --pull never --name ahos-vane --restart unless-stopped `
        --cpus 1 --memory 2g --pids-limit 256 `
        -p 127.0.0.1:3010:3000 `
        -v ahos-vane-data:/home/vane/data -v ahos-vane-uploads:/home/vane/uploads `
        -e OLLAMA_BASE_URL=http://host.docker.internal:11434 $ImageDigest
}
if ($LASTEXITCODE -ne 0) { throw 'Vane container failed to start.' }
Write-Output 'Vane started. Verify http://127.0.0.1:3010/api/providers before claiming readiness.'
