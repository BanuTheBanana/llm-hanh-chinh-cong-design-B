param(
    [ValidateSet('Start', 'Stop', 'Status')][string]$Action = 'Start',
    [string]$DatasetPath = '',
    [string]$GenerationModelPath = '',
    [string]$GenerationAdapterPath = '',
    [string]$EmbeddingModelPath = '',
    [string]$IntentModelPath = '',
    [string]$IntentAdapterPath = '',
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')]
    [string]$GenerationModelName = 'Qwen3-1.7B-FullCorpus-r16',
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')]
    [string]$IntentModelName = 'Qwen3-4B-Intent-full38-v1-r16',
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')]
    [string]$DatasetVersion = 'company-tthc-9c38dde8-v1-adjudicated-v1',
    [ValidateRange(1, 1000000)][int]$ExpectedRows = 42,
    [ValidatePattern('^[A-Fa-f0-9]{64}$')]
    [string]$CorpusSha256 = '72e6a79ebaa16471dc6070b414ff004096d9f34fbfecd668fd19fd567b7dc340',
    [ValidatePattern('^$|^[A-Fa-f0-9]{64}$')][string]$GenerationModelSha256 = '',
    [ValidatePattern('^$|^[A-Fa-f0-9]{64}$')][string]$GenerationAdapterSha256 = '',
    [ValidatePattern('^$|^[A-Fa-f0-9]{64}$')][string]$EmbeddingModelSha256 = '',
    [ValidatePattern('^$|^[A-Fa-f0-9]{64}$')][string]$IntentModelSha256 = '',
    [ValidatePattern('^$|^[A-Fa-f0-9]{64}$')][string]$IntentAdapterSha256 = '',
    [string]$ComposeOverlayPath = '',
    [ValidatePattern('^[a-z0-9][a-z0-9_-]{1,62}$')][string]$ComposeProject = 'hanh-chinh-g5',
    [ValidateRange(1, 65535)][int]$WebPort = 3005,
    [ValidateRange(1, 65535)][int]$BackendPort = 8005,
    [ValidateRange(1, 65535)][int]$AiServicePort = 8105,
    [ValidateRange(1, 65535)][int]$LlamaServerPort = 8085,
    [ValidateRange(1, 65535)][int]$EmbeddingServerPort = 8095,
    [ValidateRange(1, 65535)][int]$SourceServicePort = 8096,
    [ValidateRange(1, 65535)][int]$IntentServerPort = 8087,
    [ValidateRange(1, 65535)][int]$PostgresPort = 55435,
    [ValidatePattern('^[A-Za-z0-9_]{1,63}$')][string]$DatabaseName = 'g5_demo',
    [string]$ReviewToken = ''
)

$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
if (-not $DatasetPath) {
    $DatasetPath = Join-Path $taskRepo '../tu_full_data_preprocessed/company-tthc-9c38dde8-v1-adjudicated-v1'
}
if (-not $GenerationModelPath) {
    $GenerationModelPath = Join-Path $taskRepo '../LLM/models/Qwen3-1.7B-Q8_0.gguf'
}
if (-not $GenerationAdapterPath) {
    $GenerationAdapterPath = Join-Path $taskRepo 'training/output/qwen3-1.7b-full-corpus-r16-seed42/adapter-f16.gguf'
}
if (-not $EmbeddingModelPath) {
    $EmbeddingModelPath = Join-Path $taskRepo '../LLM/models/Qwen3-Embedding-0.6B-Q8_0.gguf'
}
if (-not $IntentModelPath) {
    $IntentModelPath = Join-Path $taskRepo '../LLM/models/qwen3-4b-instruct-2507-q8_0.gguf'
}
if (-not $IntentAdapterPath) {
    $IntentAdapterPath = Join-Path $taskRepo 'training/output/qwen3-4b-intent-full38-v1-r16/adapter-f16.gguf'
}
foreach ($taskPath in @(
    $DatasetPath,
    $GenerationModelPath,
    $GenerationAdapterPath,
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
$taskReleaseManifestPath = Join-Path $DatasetPath 'release-manifest.json'
if (-not (Test-Path -LiteralPath $taskReleaseManifestPath -PathType Leaf)) {
    throw 'The controlled full-corpus release manifest is missing.'
}
$taskReleaseManifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $taskReleaseManifestPath |
    ConvertFrom-Json
if ($taskReleaseManifest.status -ne 'READY_FOR_CONTROLLED_RAG') {
    throw 'The full corpus is not READY_FOR_CONTROLLED_RAG.'
}
if ($taskReleaseManifest.dataset_version -ne $DatasetVersion) {
    throw 'DatasetVersion does not match the controlled release manifest.'
}
$taskSourceManifestPath = Join-Path $DatasetPath 'source_manifest.jsonl'
if (-not (Test-Path -LiteralPath $taskSourceManifestPath -PathType Leaf)) {
    throw 'The controlled source manifest is missing.'
}
$taskRowReferences = [Collections.Generic.HashSet[string]]::new()
foreach ($taskLine in Get-Content -Encoding UTF8 -LiteralPath $taskSourceManifestPath) {
    if (-not $taskLine.Trim()) { continue }
    $taskSource = $taskLine | ConvertFrom-Json
    foreach ($taskRowNumber in $taskSource.raw_locator.row_numbers) {
        [void]$taskRowReferences.Add(
            "$($taskSource.raw_locator.workbook_sha256):$($taskSource.raw_locator.sheet):$taskRowNumber"
        )
    }
}
if ($taskRowReferences.Count -ne $ExpectedRows) {
    throw 'ExpectedRows does not match the controlled source row accounting.'
}
foreach ($taskModelPath in @(
    $GenerationModelPath,
    $GenerationAdapterPath,
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
    @($GenerationAdapterPath, $GenerationAdapterSha256),
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
    G5_GENERATION_MODEL_NAME = $GenerationModelName
    G5_GENERATION_ADAPTER_HOST_PATH = (Resolve-Path -LiteralPath $GenerationAdapterPath).Path
    G5_EMBEDDING_MODEL_HOST_PATH = (Resolve-Path -LiteralPath $EmbeddingModelPath).Path
    G5_INTENT_MODEL_HOST_PATH = (Resolve-Path -LiteralPath $IntentModelPath).Path
    G5_INTENT_ADAPTER_HOST_PATH = (Resolve-Path -LiteralPath $IntentAdapterPath).Path
    G5_INTENT_MODEL_NAME = $IntentModelName
    G5_SOURCE_REVIEW_TOKEN = $ReviewToken
    G3_DATASET_VERSION = $DatasetVersion
    G3_EXPECTED_ROWS = $ExpectedRows.ToString()
    G3_CORPUS_SHA256 = $CorpusSha256.ToLowerInvariant()
    WEB_PORT = $WebPort.ToString()
    BACKEND_PORT = $BackendPort.ToString()
    AI_SERVICE_PORT = $AiServicePort.ToString()
    LLAMA_SERVER_PORT = $LlamaServerPort.ToString()
    EMBEDDING_SERVER_PORT = $EmbeddingServerPort.ToString()
    SOURCE_SERVICE_PORT = $SourceServicePort.ToString()
    INTENT_SERVER_PORT = $IntentServerPort.ToString()
    POSTGRES_PORT = $PostgresPort.ToString()
    POSTGRES_DB = $DatabaseName
    DATABASE_URL = ''
    WEB_ORIGIN = "http://localhost:$WebPort"
    WEB_ORIGINS = "http://127.0.0.1:$WebPort"
    VITE_API_BASE_URL = "http://localhost:$BackendPort/api/v1"
}
$taskSaved = @{}
foreach ($key in $taskVariables.Keys) {
    $taskSaved[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
    [Environment]::SetEnvironmentVariable($key, $taskVariables[$key], 'Process')
}
$taskCompose = @(
    '-p', $ComposeProject,
    '-f', 'compose.yaml',
    '-f', 'compose.g3.local.yaml',
    '-f', 'compose.g4.local.yaml',
    '-f', 'compose.g4.docker.yaml',
    '-f', 'compose.g5.yaml'
)
if ($ComposeOverlayPath) {
    if (-not (Test-Path -LiteralPath $ComposeOverlayPath -PathType Leaf)) {
        throw "Missing compose overlay: $ComposeOverlayPath"
    }
    $taskCompose += @('-f', (Resolve-Path -LiteralPath $ComposeOverlayPath).Path)
}
$taskCompose += @('--profile', 'full')
Push-Location $taskRepo
try {
    if ($Action -eq 'Start') {
        & docker compose @taskCompose up --detach --build --wait --wait-timeout 240
        if ($LASTEXITCODE -ne 0) { throw 'G5 failed to start.' }
        Write-Host "$ComposeProject`: http://localhost:$WebPort"
        Write-Host "Source MCP: http://localhost:$SourceServicePort/mcp"
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
