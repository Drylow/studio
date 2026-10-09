[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
foreach ($name in 'node','python','ffmpeg','ffprobe') {
    if (!(Get-Command $name -ErrorAction SilentlyContinue)) { throw "Installer $name avant de continuer." }
}
& npm.cmd ci --prefix $PSScriptRoot --no-audit --no-fund
if ($LASTEXITCODE) { throw 'Installation des dependances interrompue.' }
& npm.cmd run setup-browser --prefix $PSScriptRoot
if ($LASTEXITCODE) { throw 'Installation du navigateur interrompue.' }
$runtime = Join-Path $repo 'work/conversation-chess/runtime'
$editor = Join-Path $runtime 'kdenlive-26.08.1_standalone/bin/kdenlive.exe'
if (!$env:CHESS_KDENLIVE -and !(Get-Command kdenlive -ErrorAction SilentlyContinue) -and !(Test-Path $editor) -and !(Test-Path 'C:/Program Files/kdenlive/bin/kdenlive.exe')) {
    New-Item -ItemType Directory -Force $runtime | Out-Null
    function Get-VerifiedFile([string]$Url, [string]$Destination, [string]$Sha256) {
        if (!(Test-Path $Destination) -or (Get-FileHash $Destination -Algorithm SHA256).Hash -ne $Sha256) {
            Invoke-WebRequest -Uri $Url -OutFile $Destination
        }
        if ((Get-FileHash $Destination -Algorithm SHA256).Hash -ne $Sha256) { throw 'Empreinte du telechargement incorrecte.' }
    }
    $archive = Join-Path $runtime 'kdenlive-26.08.1_standalone.exe'
    $archiver = Join-Path $runtime '7zr.exe'
    Get-VerifiedFile 'https://download.kde.org/stable/kdenlive/26.08/windows/kdenlive-26.08.1_standalone.exe' $archive '9335B59356A7FD6FB4B836C09A518DB6547AD4189717CAE872474E798B72A67B'
    Get-VerifiedFile 'https://www.7-zip.org/a/7zr.exe' $archiver '256FECA8E274E5DA655E2A284FABAFD9F554365EB164862089DACD4E8276D282'
    & $archiver x $archive "-o$runtime" -y
    if ($LASTEXITCODE -or !(Test-Path $editor)) { throw 'Extraction de Kdenlive interrompue.' }
}
& (Join-Path $PSScriptRoot 'chess.ps1') -Mode Doctor
