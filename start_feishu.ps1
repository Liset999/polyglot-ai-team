param(
    [string]$Session = "feishu-demo",
    [int]$Port = 8787,
    [string]$HostName = "0.0.0.0",
    [string]$WebhookUrl = "",
    [string]$Token = "",
    [switch]$Live,
    [switch]$AllowUnlock,
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
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\start_feishu.ps1 -Live -Token `"long-random-secret`" -WebhookUrl `"https://open.feishu.cn/open-apis/bot/v2/hook/...`""
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
if ($Token) {
    $env:POLYGLOT_HTTP_TOKEN = $Token
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
if ($env:POLYGLOT_HTTP_TOKEN) {
    Write-Host "  auth:      X-Polyglot-Token required"
} else {
    Write-Host "  auth:      disabled; use -Token before exposing with ngrok"
}
if ($AllowUnlock) {
    Write-Host "  unlock:    remote /unlock allowed"
} else {
    Write-Host "  unlock:    remote /unlock disabled"
}

Write-Host ""
Write-Host "Quick local test from another terminal:"
if ($env:POLYGLOT_HTTP_TOKEN) {
    Write-Host "  Invoke-RestMethod -Method Post -Uri http://127.0.0.1:$Port -Headers @{`"X-Polyglot-Token`"=`"$env:POLYGLOT_HTTP_TOKEN`"} -ContentType `"application/json`" -Body '{`"text`":`"/status`"}'"
} else {
    Write-Host "  Invoke-RestMethod -Method Post -Uri http://127.0.0.1:$Port -ContentType `"application/json`" -Body '{`"text`":`"/status`"}'"
}
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
if ($env:POLYGLOT_HTTP_TOKEN) {
    $argsList += @("--token", $env:POLYGLOT_HTTP_TOKEN)
}
if ($AllowUnlock) {
    $argsList += "--allow-unlock"
}

python @argsList
