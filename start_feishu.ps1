param(
    [string]$Session = "feishu-demo",
    [int]$Port = 8787,
    [string]$HostName = "0.0.0.0",
    [string]$WebhookUrl = "",
    [switch]$Live,
    [switch]$Help
)

if ($Help) {
    Write-Host ""
    Write-Host "Polyglot Feishu one-command launcher"
    Write-Host ""
    Write-Host "Local dry-run:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\start_feishu.ps1"
    Write-Host ""
    Write-Host "Live Feishu replies:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\start_feishu.ps1 -Live -WebhookUrl `"https://open.feishu.cn/open-apis/bot/v2/hook/...`""
    Write-Host ""
    Write-Host "Expose callback with ngrok in another terminal:"
    Write-Host "  ngrok http $Port"
    Write-Host ""
    Write-Host "Feishu event callback URL:"
    Write-Host "  https://<your-ngrok-domain>"
    Write-Host ""
    exit 0
}

$ErrorActionPreference = "Stop"
$Workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Workspace

$env:POLYGLOT_WORKSPACE = $Workspace
$env:POLYGLOT_SESSION = $Session
if ($WebhookUrl) {
    $env:FEISHU_WEBHOOK_URL = $WebhookUrl
}

Write-Host ""
Write-Host "Polyglot Feishu launcher"
Write-Host "  workspace: $Workspace"
Write-Host "  session:   $Session"
Write-Host "  listener:  http://127.0.0.1:$Port/"
if ($Live) {
    if (-not $env:FEISHU_WEBHOOK_URL) {
        Write-Host ""
        Write-Host "[ERROR] -Live needs -WebhookUrl or FEISHU_WEBHOOK_URL."
        Write-Host "Example:"
        Write-Host "  powershell -ExecutionPolicy Bypass -File .\start_feishu.ps1 -Live -WebhookUrl `"https://open.feishu.cn/open-apis/bot/v2/hook/...`""
        exit 1
    }
    Write-Host "  mode:      live replies to Feishu webhook"
} else {
    Write-Host "  mode:      dry-run, replies print in this terminal"
}

Write-Host ""
Write-Host "Quick local test from another terminal:"
Write-Host "  Invoke-RestMethod -Method Post -Uri http://127.0.0.1:$Port -ContentType `"application/json`" -Body '{`"text`":`"/status`"}'"
Write-Host ""
Write-Host "For real Feishu incoming events, expose this port:"
Write-Host "  ngrok http $Port"
Write-Host "Then put the HTTPS ngrok URL into Feishu Event Subscription callback."
Write-Host ""
Write-Host "Useful Feishu messages: /status, /run <goal>, /steer <text>, /board, /timeline, /report"
Write-Host ""

$argsList = @(".\feishu_listener.py", "--host", $HostName, "--port", "$Port", "--session", $Session)
if ($Live) {
    $argsList += @("--webhook-url", $env:FEISHU_WEBHOOK_URL)
} else {
    $argsList += "--dry-run"
}

python @argsList
