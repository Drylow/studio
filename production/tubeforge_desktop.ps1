param([int]$Port = 8766, [switch]$Local)
$ErrorActionPreference = 'Stop'
$hosting = Join-Path (Split-Path $PSScriptRoot -Parent) 'work/tubeforge-host.json'
if (-not $Local -and (Test-Path -LiteralPath $hosting)) {
    $url = (Get-Content -LiteralPath $hosting -Raw | ConvertFrom-Json).url
    $address = [Uri]$url
    if ($address.Scheme -ne 'https' -or $address.UserInfo) { throw 'Invalid hosted TubeForge URL' }
    Start-Process $url
    return
}
& (Join-Path $PSScriptRoot 'tubeforge.ps1') -Action Start -Port $Port
# The desktop shortcut is an explicit interactive launch: show the browser.
Start-Process "http://127.0.0.1:$Port/"
