[CmdletBinding()]
param(
    [ValidateSet('Doctor','Validate','Prepare','Render')][string]$Mode = 'Doctor',
    [string]$Source,
    [string]$Timeline,
    [string]$Out,
    [switch]$Preview
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if (!$Out) { $Out = Join-Path $repo 'work/conversation-chess/current' }
$Out = [IO.Path]::GetFullPath($Out)
if (!$env:CHESS_KDENLIVE) {
    $installed = Get-Command kdenlive -ErrorAction SilentlyContinue
    $portable = Get-ChildItem (Join-Path $repo 'work/conversation-chess/runtime/kdenlive*/bin/kdenlive.exe') -ErrorAction SilentlyContinue | Select-Object -Last 1
    if ($installed) { $env:CHESS_KDENLIVE = $installed.Source }
    elseif ($portable) { $env:CHESS_KDENLIVE = $portable.FullName }
    elseif (Test-Path 'C:/Program Files/kdenlive/bin/kdenlive.exe') { $env:CHESS_KDENLIVE = 'C:/Program Files/kdenlive/bin/kdenlive.exe' }
}
if ($Mode -eq 'Doctor') {
    foreach ($name in 'node','python','ffmpeg','ffprobe') {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if (!$command) { throw "$name manque sur ce PC." }
        Write-Output "$name : $($command.Source)"
    }
    & node (Join-Path $PSScriptRoot 'doctor.mjs')
    if ($LASTEXITCODE) { throw 'Navigateur absent : npm ci puis npm run setup-browser dans ce dossier.' }
    if ($env:CHESS_KDENLIVE) { Write-Output "Kdenlive : $env:CHESS_KDENLIVE" }
    else { throw 'Kdenlive manque : installer la version officielle Windows ou renseigner CHESS_KDENLIVE.' }
    return
}
if (!$Source -or !$Timeline) { throw 'Renseigner -Source et -Timeline.' }
$mediaArgs = @((Join-Path $PSScriptRoot 'render-clip.mjs'), '--source', $Source, '--timeline', $Timeline, '--out', (Join-Path $Out 'prepared'))
if ($Mode -eq 'Validate') { $mediaArgs += '--validate-only' }
else { $mediaArgs += '--prepare-project' }
if ($Preview) { $mediaArgs += '--allow-low-res-preview' }
& node @mediaArgs
if ($LASTEXITCODE) { throw 'Preparation refusee : lire le message ci-dessus.' }
if ($Mode -eq 'Validate') { return }
$bundle = Join-Path $Out 'kdenlive'
$exportArgs = @((Join-Path $PSScriptRoot 'export-kdenlive.py'), '--manifest', (Join-Path $Out 'prepared/project-manifest.json'), '--bundle', $bundle)
if ($Mode -eq 'Render') {
    if (!$env:CHESS_KDENLIVE) { throw 'Configurer CHESS_KDENLIVE pour exporter.' }
    $filename = if ($Preview) { 'APERCU-TECHNIQUE.mp4' } else { 'video.mp4' }
    if (Test-Path (Join-Path $bundle $filename)) {
        $filename = [IO.Path]::GetFileNameWithoutExtension($filename) + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.mp4'
    }
    $exportArgs += @('--render', (Join-Path $bundle $filename))
}
& python @exportArgs
if ($LASTEXITCODE) { throw 'Export Kdenlive interrompu : consulter son journal.' }
Write-Output "Projet : $(Join-Path $bundle 'project.kdenlive')"
