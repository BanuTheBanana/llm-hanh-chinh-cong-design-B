param(
    [ValidateSet('Start', 'Stop', 'Status')][string]$Action = 'Start',
    [string]$DatasetPath = '',
    [string]$ModelPath = '',
    [ValidateSet('Qwen3-1.7B', 'Qwen3-4B-Instruct-2507')]
    [string]$ModelName = 'Qwen3-1.7B'
)

$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
if (-not $DatasetPath) {
    $DatasetPath = Join-Path $taskRepo '../LLM/data/company_private/company-tthc-9c38dde8-v1-demo10-v1'
}
if (-not $ModelPath) {
    $taskFile = if ($ModelName -eq 'Qwen3-1.7B') {
        'Qwen3-1.7B-Q8_0.gguf'
    } else {
        'qwen3-4b-instruct-2507-q8_0.gguf'
    }
    $ModelPath = Join-Path $taskRepo "../LLM/models/$taskFile"
}
if (-not (Test-Path -LiteralPath $DatasetPath -PathType Container)) {
    throw 'Private dataset not found. Supply -DatasetPath; do not upload it to Git.'
}
if (-not (Test-Path -LiteralPath $ModelPath -PathType Leaf)) {
    throw 'Model not found. Supply -ModelPath to the tested local GGUF.'
}
$taskVariables = @{
    G3_PRIVATE_DATASET_HOST_PATH = (Resolve-Path -LiteralPath $DatasetPath).Path
    G4_MODEL_HOST_PATH = (Resolve-Path -LiteralPath $ModelPath).Path
    G4_MODEL_NAME = $ModelName
    WEB_PORT = '3004'
    BACKEND_PORT = '8004'
    AI_SERVICE_PORT = '8104'
    LLAMA_SERVER_PORT = '8084'
    POSTGRES_PORT = '55434'
    POSTGRES_DB = 'g4_demo'
    DATABASE_URL = ''
    WEB_ORIGIN = 'http://localhost:3004'
    WEB_ORIGINS = 'http://127.0.0.1:3004'
    VITE_API_BASE_URL = 'http://localhost:8004/api/v1'
}
$taskSaved = @{}
foreach ($key in $taskVariables.Keys) {
    $taskSaved[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
    [Environment]::SetEnvironmentVariable($key, $taskVariables[$key], 'Process')
}
$taskCompose = @('-p', 'hanh-chinh-g4', '-f', 'compose.yaml', '-f', 'compose.g3.local.yaml',
    '-f', 'compose.g4.local.yaml', '-f', 'compose.g4.docker.yaml', '--profile', 'full')
Push-Location $taskRepo
try {
    if ($Action -eq 'Start') {
        & docker compose @taskCompose up --detach --build --wait --wait-timeout 180
        if ($LASTEXITCODE -ne 0) { throw 'G4 failed to start. Existing G1/G2/G3 were not changed.' }
        Write-Host 'G4: http://localhost:3004 (experimental claim guard, not full G4 acceptance).'
    } elseif ($Action -eq 'Stop') {
        & docker compose @taskCompose stop
    } else {
        & docker compose @taskCompose ps
    }
    if ($LASTEXITCODE -ne 0) { throw 'Docker command failed.' }
} finally {
    Pop-Location
    foreach ($key in $taskSaved.Keys) {
        [Environment]::SetEnvironmentVariable($key, $taskSaved[$key], 'Process')
    }
}
