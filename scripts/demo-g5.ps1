param(
    [ValidateSet('Start', 'Stop', 'Status')][string]$Action = 'Start',
    [string]$DatasetPath = '',
    [string]$GenerationModelPath = '',
    [string]$EmbeddingModelPath = '',
    [string]$IntentModelPath = '',
    [string]$IntentAdapterPath = '',
    [ValidateSet('Qwen3-1.7B', 'Qwen3-4B-Instruct-2507')]
    [string]$GenerationModelName = 'Qwen3-1.7B',
    [ValidatePattern('^$|^[A-Fa-f0-9]{64}$')][string]$GenerationModelSha256 = '',
    [ValidatePattern('^$|^[A-Fa-f0-9]{64}$')][string]$EmbeddingModelSha256 = '',
    [ValidatePattern('^$|^[A-Fa-f0-9]{64}$')][string]$IntentModelSha256 = '',
    [ValidatePattern('^$|^[A-Fa-f0-9]{64}$')][string]$IntentAdapterSha256 = '',
    [string]$ReviewToken = ''
)

$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
if (-not $DatasetPath) {
    $DatasetPath = Join-Path $taskRepo '../LLM/data/company_private/company-tthc-9c38dde8-v1-demo10-v1'
}
if (-not $GenerationModelPath) {
    $taskFile = if ($GenerationModelName -eq 'Qwen3-1.7B') {
        'Qwen3-1.7B-Q8_0.gguf'
    } else {
        'qwen3-4b-instruct-2507-q8_0.gguf'
    }
    $GenerationModelPath = Join-Path $taskRepo "../LLM/models/$taskFile"
}
if (-not $EmbeddingModelPath) {
    $EmbeddingModelPath = Join-Path $taskRepo '../LLM/models/Qwen3-Embedding-0.6B-Q8_0.gguf'
}
if (-not $IntentModelPath) {
    $IntentModelPath = Join-Path $taskRepo '../LLM/models/qwen3-4b-instruct-2507-q8_0.gguf'
}
if (-not $IntentAdapterPath) {
    $IntentAdapterPath = Join-Path $taskRepo 'training/output/qwen3-4b-intent-pilot-r16/adapter-f16.gguf'
}
foreach ($taskPath in @(
    $DatasetPath,
    $GenerationModelPath,
    $EmbeddingModelPath,
    $IntentModelPath,
    $IntentAdapterPath
)) {
    if (-not (Test-Path -LiteralPath $taskPath)) {
        throw "Missing local artifact: $taskPath"
    }
}
if (-not (Test-Path -LiteralPath $DatasetPath -PathType Container)) {
    throw 'DatasetPath must be a directory.'
}
foreach ($taskModelPath in @(
    $GenerationModelPath,
    $EmbeddingModelPath,
    $IntentModelPath,
    $IntentAdapterPath
)) {
    if (-not (Test-Path -LiteralPath $taskModelPath -PathType Leaf)) {
        throw "Model path must be a file: $taskModelPath"
    }
    if ([System.IO.Path]::GetExtension($taskModelPath) -ne '.gguf') {
        throw "Model artifact must use the .gguf extension: $taskModelPath"
    }
}
foreach ($taskArtifact in @(
    @($GenerationModelPath, $GenerationModelSha256),
    @($EmbeddingModelPath, $EmbeddingModelSha256),
    @($IntentModelPath, $IntentModelSha256),
    @($IntentAdapterPath, $IntentAdapterSha256)
)) {
    if ($taskArtifact[1]) {
        $taskActualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $taskArtifact[0]).Hash
        if ($taskActualHash -ne $taskArtifact[1]) {
            throw "Model SHA-256 mismatch: $($taskArtifact[0])"
        }
    }
}
if ($ReviewToken.Length -lt 12) { throw 'ReviewToken must contain at least 12 characters.' }

$taskVariables = @{
    G3_PRIVATE_DATASET_HOST_PATH = (Resolve-Path -LiteralPath $DatasetPath).Path
    G4_MODEL_HOST_PATH = (Resolve-Path -LiteralPath $GenerationModelPath).Path
    G4_MODEL_NAME = $GenerationModelName
    G5_EMBEDDING_MODEL_HOST_PATH = (Resolve-Path -LiteralPath $EmbeddingModelPath).Path
    G5_INTENT_MODEL_HOST_PATH = (Resolve-Path -LiteralPath $IntentModelPath).Path
    G5_INTENT_ADAPTER_HOST_PATH = (Resolve-Path -LiteralPath $IntentAdapterPath).Path
    G5_SOURCE_REVIEW_TOKEN = $ReviewToken
    WEB_PORT = '3005'
    BACKEND_PORT = '8005'
    AI_SERVICE_PORT = '8105'
    LLAMA_SERVER_PORT = '8085'
    EMBEDDING_SERVER_PORT = '8095'
    SOURCE_SERVICE_PORT = '8096'
    INTENT_SERVER_PORT = '8087'
    POSTGRES_PORT = '55435'
    POSTGRES_DB = 'g5_demo'
    DATABASE_URL = ''
    WEB_ORIGIN = 'http://localhost:3005'
    WEB_ORIGINS = 'http://127.0.0.1:3005'
    VITE_API_BASE_URL = 'http://localhost:8005/api/v1'
}
$taskSaved = @{}
foreach ($key in $taskVariables.Keys) {
    $taskSaved[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
    [Environment]::SetEnvironmentVariable($key, $taskVariables[$key], 'Process')
}
$taskCompose = @(
    '-p', 'hanh-chinh-g5',
    '-f', 'compose.yaml',
    '-f', 'compose.g3.local.yaml',
    '-f', 'compose.g4.local.yaml',
    '-f', 'compose.g4.docker.yaml',
    '-f', 'compose.g5.yaml',
    '--profile', 'full'
)
Push-Location $taskRepo
try {
    if ($Action -eq 'Start') {
        & docker compose @taskCompose up --detach --build --wait --wait-timeout 240
        if ($LASTEXITCODE -ne 0) { throw 'G5 failed to start.' }
        Write-Host 'G5: http://localhost:3005'
        Write-Host 'Source MCP: http://localhost:8096/mcp'
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
