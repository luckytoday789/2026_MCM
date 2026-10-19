param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$SafeInvestRuntime = Join-Path $PSScriptRoot '.runtime'
New-Item -ItemType Directory -Force -Path $SafeInvestRuntime | Out-Null
if (Test-Path -LiteralPath (Join-Path $SafeInvestRuntime 'STOP')) {
    throw 'Local STOP is present. Inspect existing processes and recovery notes before resuming.'
}
if (Test-Path -LiteralPath (Join-Path $SafeInvestRuntime 'chief-budget-drain.json')) {
    throw 'User-requested local quota stop is latched. A fresh explicit user instruction is required before resuming.'
}
$SafeInvestInterpreter = (Get-Command $Python -ErrorAction Stop).Source
$SafeInvestProcess = Start-Process -FilePath $SafeInvestInterpreter -ArgumentList @('-X','utf8','scripts/supervise_chief.py') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $SafeInvestRuntime 'chief-supervisor.stdout.log') -RedirectStandardError (Join-Path $SafeInvestRuntime 'chief-supervisor.stderr.log') -PassThru
$SafeInvestProcess.Id | Set-Content -LiteralPath (Join-Path $SafeInvestRuntime 'chief-supervisor-launcher.pid')
Write-Host "Started supervisor launcher PID $($SafeInvestProcess.Id). Verify .runtime/chief-health.json and the actual worker PID."
