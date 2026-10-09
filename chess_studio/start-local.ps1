param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Installer Node.js 22.12 ou plus récent.' }
if (-not (Test-Path -LiteralPath 'node_modules')) {
    & npm.cmd ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Installation des dépendances impossible.' }
}
& node.exe scripts/setup.mjs
if ($LASTEXITCODE -ne 0) { throw 'Préparation des sons impossible.' }
$taskUrl = 'http://127.0.0.1:4317'
$alreadyRunning = $false
try { $health = Invoke-RestMethod -Uri "$taskUrl/api/health" -TimeoutSec 3; $alreadyRunning = $health.application -eq 'drylow-chess-studio' } catch {}
if (-not $alreadyRunning) {
    New-Item -ItemType Directory -Force -Path '.local' | Out-Null
    Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList @('"' + (Join-Path $PSScriptRoot 'server.mjs') + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot '.local/server.log') -RedirectStandardError (Join-Path $PSScriptRoot '.local/server-error.log')
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        try { $health = Invoke-RestMethod -Uri "$taskUrl/api/health" -TimeoutSec 2; if ($health.application -eq 'drylow-chess-studio') { break } } catch {}
    }
    if ($health.application -ne 'drylow-chess-studio') { throw 'Le serveur ne démarre pas ou le port 4317 est occupé. Voir .local/server-error.log.' }
}
if (-not $NoBrowser) { Start-Process $taskUrl }
