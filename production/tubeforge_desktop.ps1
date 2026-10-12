param([int]$Port = 8766)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'tubeforge.ps1') -Action Start -Port $Port
# The desktop shortcut is an explicit interactive launch: show the browser.
Start-Process "http://127.0.0.1:$Port/"
