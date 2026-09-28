param(
    [Parameter(Mandatory = $true)][ValidateLength(1, 10000)][string]$DirectQuestion,
    [Parameter(Mandatory = $true)][ValidateLength(1, 10000)][string]$FollowUpQuestion,
    [string]$ApiBaseUrl = 'http://127.0.0.1:8005/api/v1'
)

$ErrorActionPreference = 'Stop'
$taskSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession

function Invoke-JsonRequest {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Uri,
        [hashtable]$Body
    )
    $taskArguments = @{
        Method = $Method
        Uri = $Uri
        WebSession = $taskSession
        TimeoutSec = 120
    }
    if ($null -ne $Body) {
        $taskJson = $Body | ConvertTo-Json -Compress -Depth 8
        $taskArguments.ContentType = 'application/json; charset=utf-8'
        $taskArguments.Body = [Text.Encoding]::UTF8.GetBytes($taskJson)
    }
    Invoke-RestMethod @taskArguments
}

function Send-Turn {
    param([Parameter(Mandatory = $true)][string]$ConversationId, [string]$Content)
    $taskWatch = [Diagnostics.Stopwatch]::StartNew()
    $taskResponse = Invoke-JsonRequest -Method Post `
        -Uri "$ApiBaseUrl/conversations/$ConversationId/messages" `
        -Body @{
            client_message_id = [guid]::NewGuid().ToString()
            content = $Content
            retrieval_filters = @{}
        }
    $taskWatch.Stop()
    [pscustomobject]@{ elapsed_ms = $taskWatch.ElapsedMilliseconds; response = $taskResponse }
}

$taskRunId = [guid]::NewGuid().ToString('N')
Invoke-JsonRequest -Method Post -Uri "$ApiBaseUrl/auth/login" `
    -Body @{ display_name = "g5-smoke-$taskRunId" } | Out-Null
$taskConversation = Invoke-JsonRequest -Method Post -Uri "$ApiBaseUrl/conversations" `
    -Body @{ title = "G5 runtime smoke $taskRunId" }

$taskDirect = Send-Turn -ConversationId $taskConversation.id -Content $DirectQuestion
$taskFollowUp = Send-Turn -ConversationId $taskConversation.id -Content $FollowUpQuestion
$taskReset = Send-Turn -ConversationId $taskConversation.id -Content 'Bat dau lai'
$taskAssistant = $taskDirect.response.assistant_message
$taskFeedback = Invoke-JsonRequest -Method Put `
    -Uri "$ApiBaseUrl/messages/$($taskAssistant.id)/feedback" `
    -Body @{
        relevance = 'relevant'
        satisfaction = 'satisfied'
        reason = 'Automated G5 runtime smoke'
    }
$taskFeedbackBeforeDeleteItems = Invoke-JsonRequest -Method Get `
    -Uri "$ApiBaseUrl/conversations/$($taskConversation.id)/feedback"
$taskFeedbackBeforeDelete = if ($null -eq $taskFeedbackBeforeDeleteItems) {
    0
} else {
    @($taskFeedbackBeforeDeleteItems).Count
}
Invoke-JsonRequest -Method Delete `
    -Uri "$ApiBaseUrl/messages/$($taskAssistant.id)/feedback" | Out-Null
$taskFeedbackAfterDeleteItems = Invoke-JsonRequest -Method Get `
    -Uri "$ApiBaseUrl/conversations/$($taskConversation.id)/feedback"
$taskFeedbackAfterDelete = if ($null -eq $taskFeedbackAfterDeleteItems) {
    0
} else {
    @($taskFeedbackAfterDeleteItems).Count
}

$taskDirectGrounding = $taskDirect.response.assistant_message.grounding
$taskFollowUpGrounding = $taskFollowUp.response.assistant_message.grounding
$taskPassed = (
    $taskDirect.response.assistant_message.status -eq 'completed' -and
    $taskFollowUp.response.assistant_message.status -eq 'completed' -and
    $taskReset.response.assistant_message.status -eq 'completed' -and
    $taskDirectGrounding.status -eq 'ANSWER' -and
    $taskDirectGrounding.verification.candidate_passed -and
    -not $taskDirectGrounding.verification.fallback_used -and
    $taskFollowUpGrounding.status -eq 'ANSWER' -and
    $taskFeedbackBeforeDelete -eq 1 -and
    $taskFeedbackAfterDelete -eq 0
)

[pscustomobject]@{
    status = if ($taskPassed) { 'PASS' } else { 'FAIL' }
    conversation_id = $taskConversation.id
    corpus_version = $taskDirectGrounding.corpus_version
    generation_model = $taskDirectGrounding.model
    direct_latency_ms = $taskDirect.elapsed_ms
    direct_candidate_passed = $taskDirectGrounding.verification.candidate_passed
    direct_fallback_used = $taskDirectGrounding.verification.fallback_used
    follow_up_latency_ms = $taskFollowUp.elapsed_ms
    follow_up_status = $taskFollowUpGrounding.status
    reset_latency_ms = $taskReset.elapsed_ms
    feedback_model = $taskFeedback.model
    feedback_saved_count = $taskFeedbackBeforeDelete
    feedback_after_delete_count = $taskFeedbackAfterDelete
} | ConvertTo-Json -Depth 6

if (-not $taskPassed) { exit 1 }
