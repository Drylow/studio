param([ValidateSet('Start', 'Stop', 'Status')][string]$Action = 'Start', [int]$Port = 8766)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$root = Join-Path $repo 'work/TubeForge'
$python = [IO.Path]::GetFullPath((Join-Path $root '.venv/Scripts/python.exe'))
$url = "http://127.0.0.1:$Port"
$pidFile = Join-Path $root 'server-pid.json'
if ($Action -eq 'Status') {
    Invoke-RestMethod "$url/api/state"
    return
}
if ($Action -eq 'Stop') {
    if (-not (Test-Path -LiteralPath $pidFile)) { return }
    $record = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($record.pid)"
    if ($process -and $process.ExecutablePath -eq $python -and $process.CommandLine -like '*app serve*') {
        Stop-Process -Id $record.pid
    }
    return
}
try {
    $health = Invoke-RestMethod "$url/openapi.json" -TimeoutSec 2
    if ($health.info.title -ne 'TubeForge') { throw 'Port occupied by another application' }
    Write-Output "TubeForge already running at $url"
    return
} catch {}
if (-not (Test-Path -LiteralPath $python)) { throw 'TubeForge has not been installed' }
$env:PYTHONIOENCODING = 'utf-8'
$process = Start-Process -FilePath $python -ArgumentList "-m app serve --host 127.0.0.1 --port $Port" `
    -WorkingDirectory $root -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $root 'server.log') -RedirectStandardError (Join-Path $root 'server-errors.log')
$process | Select-Object @{Name='pid'; Expression={$_.Id}} | ConvertTo-Json | Set-Content -LiteralPath $pidFile -Encoding utf8
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 300
    if ($process.HasExited) { throw 'TubeForge exited; inspect server-errors.log' }
    try {
        Invoke-RestMethod "$url/api/state" -TimeoutSec 1 | Out-Null
        Write-Output "TubeForge ready at $url"
        return
    } catch {}
}
throw 'TubeForge did not answer before the startup timeout'
