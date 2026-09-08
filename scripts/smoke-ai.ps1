[CmdletBinding()]
param(
    [string]$BaseUrl = "http://localhost:8001",
    [ValidateRange(1, 120)]
    [int]$TimeoutSeconds = 10
)

$ErrorActionPreference = "Stop"
$base = $BaseUrl.TrimEnd("/")

function Assert-Condition {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw "Smoke assertion failed: $Message"
    }
}

try {
    Write-Host "[1/2] Checking AI health at $base/health"
    $health = Invoke-RestMethod `
        -Method Get `
        -Uri "$base/health" `
        -TimeoutSec $TimeoutSeconds

    Assert-Condition ($null -ne $health) "health response is empty"
    if ($null -ne $health.status) {
        Assert-Condition ($health.status -in @("ok", "healthy")) "unexpected health status '$($health.status)'"
    }

    Write-Host "[2/2] Calling Mock AI generate endpoint"
    $requestId = [guid]::NewGuid().ToString()
    $payload = @{
        request_id = $requestId
        messages = @(
            @{
                role = "user"
                content = "Xin chao, day la du lieu gia dung cho G1 smoke test."
            }
        )
        max_output_tokens = 300
    } | ConvertTo-Json -Depth 5

    $response = Invoke-RestMethod `
        -Method Post `
        -Uri "$base/internal/v1/generate" `
        -ContentType "application/json; charset=utf-8" `
        -Body $payload `
        -TimeoutSec $TimeoutSeconds

    Assert-Condition ($response.request_id -eq $requestId) "request_id was not preserved"
    Assert-Condition ($response.provider -eq "mock") "provider must be 'mock'"
    Assert-Condition ($response.model -eq "mock-v1") "model must be 'mock-v1'"
    Assert-Condition (-not [string]::IsNullOrWhiteSpace([string]$response.text)) "text must not be empty"
    Assert-Condition ($null -ne $response.usage) "usage is missing"
    Assert-Condition ($null -ne $response.latency_ms) "latency_ms is missing"

    Write-Host "PASS - AI Service matches the G1 success contract." -ForegroundColor Green
    Write-Host "request_id=$($response.request_id) provider=$($response.provider) model=$($response.model) latency_ms=$($response.latency_ms)"
    exit 0
}
catch {
    Write-Error "FAIL - AI Service smoke test: $($_.Exception.Message)"
    exit 1
}
