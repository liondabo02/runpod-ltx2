param(
    [Parameter(Mandatory=$true)][string]$ImageDigest,
    [string]$OllamaBaseUrl = 'http://host.docker.internal:11434',
    [string]$OllamaNetwork = ''
)
$ErrorActionPreference = 'Stop'
if ($OllamaBaseUrl -notmatch '^http://(host\.docker\.internal|harun-ollama|localhost|127\.0\.0\.1):11434/?$') {
    throw 'Use a local Ollama HTTP endpoint on port 11434 without credentials or a path.'
}
if ($OllamaNetwork) {
    if ($OllamaNetwork -notmatch '^[a-zA-Z0-9_.-]+$') { throw 'Invalid Docker network name.' }
    & docker network inspect $OllamaNetwork *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Ollama network does not exist; start the local AI hub first.' }
}
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
        -e "OLLAMA_BASE_URL=$OllamaBaseUrl" $ImageDigest
}
if ($LASTEXITCODE -ne 0) { throw 'Vane container failed to start.' }
if ($OllamaNetwork) {
    $networks = & docker inspect ahos-vane --format '{{json .NetworkSettings.Networks}}'
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect Vane networks.' }
    $connected = ($networks | ConvertFrom-Json).PSObject.Properties.Name
    if ($OllamaNetwork -notin $connected) {
        & docker network connect $OllamaNetwork ahos-vane
        if ($LASTEXITCODE -ne 0) { throw 'Could not connect Vane to the local Ollama network.' }
    }
}
Write-Output 'Vane started. Verify http://127.0.0.1:3010/api/providers before claiming readiness.'
Write-Output 'Existing provider settings are preserved. Confirm their baseURL matches the selected Ollama endpoint.'
