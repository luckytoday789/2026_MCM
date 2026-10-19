param(
    [ValidateSet('chief','sol','hy3')][string]$Role,
    [string]$Python = 'python',
    [switch]$Background
)
$ErrorActionPreference = 'Stop'
if (-not $Role) { throw 'Specify -Role chief, sol or hy3.' }
Set-Location -LiteralPath $PSScriptRoot
$SafeInvestRuntime = Join-Path $PSScriptRoot '.runtime'
New-Item -ItemType Directory -Force -Path $SafeInvestRuntime | Out-Null
$SafeInvestInterpreter = (Get-Command $Python -ErrorAction Stop).Source
$SafeInvestBackend = if ($Role -eq 'hy3') { 'commands' } else { 'codex' }
$SafeInvestArguments = @('-X','utf8','scripts/coop.py','watch','--role',$Role,'--backend',$SafeInvestBackend)
if ($Background) {
    $SafeInvestProcess = Start-Process -FilePath $SafeInvestInterpreter -ArgumentList $SafeInvestArguments -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $SafeInvestRuntime "$Role.stdout.log") -RedirectStandardError (Join-Path $SafeInvestRuntime "$Role.stderr.log") -PassThru
    $SafeInvestProcess.Id | Set-Content -LiteralPath (Join-Path $SafeInvestRuntime "$Role.pid")
    Write-Host "Started $Role worker PID $($SafeInvestProcess.Id). Verify scripts/coop.py status and local logs."
} else {
    & $SafeInvestInterpreter @SafeInvestArguments
}
