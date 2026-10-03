# Drylow // montage automatique des videos d'actu sur ce PC. A lancer UNE fois (Installer.bat).
# Installe dans CE dossier : Python, les modules (yt-dlp, ffmpeg...), le moteur YouTube (deno).
# Puis, avec ton accord, une tache Windows "Drylow Actu" qui lance pc_agent.py toutes les 15 min, sans fenetre :
# s'il y a une video preparee par Claude, elle est montee ici puis effacee. Desinstaller.bat enleve la tache.
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Root = $PSScriptRoot
$Rt = Join-Path $Root 'runtime'
$PyDir = Join-Path $Rt 'python'
$Py = Join-Path $PyDir 'python.exe'
$PyW = Join-Path $PyDir 'pythonw.exe'
$PyVer = '3.12.10'
$Task = 'Drylow Actu'

function Fail($msg) {
  Write-Host ''
  Write-Host "  PROBLEME : $msg" -ForegroundColor Red
  Write-Host '  Verifie ta connexion internet puis relance. Si ca recommence, envoie une capture a Claude.'
  exit 1
}

Write-Host ''
Write-Host '  DRYLOW // MONTAGE AUTOMATIQUE DES VIDEOS D''ACTU' -ForegroundColor Red
Write-Host '  Installation unique, 3 a 8 minutes. Ne ferme pas cette fenetre.' -ForegroundColor Yellow
Write-Host ''
New-Item -ItemType Directory -Force -Path $Rt | Out-Null

if (-not (Test-Path $Py)) {
  Write-Host '  [1/4] Python...' -ForegroundColor Cyan
  New-Item -ItemType Directory -Force -Path $PyDir | Out-Null
  $zip = Join-Path $Rt 'python.zip'
  try {
    Invoke-WebRequest "https://www.python.org/ftp/python/$PyVer/python-$PyVer-embed-amd64.zip" -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $PyDir -Force
    Remove-Item $zip -Force
  } catch { Remove-Item $PyDir -Recurse -Force -ErrorAction SilentlyContinue; Fail "telechargement de Python ($($_.Exception.Message))" }
  $pth = Get-ChildItem $PyDir -Filter 'python*._pth' | Select-Object -First 1
  (Get-Content $pth.FullName) -replace '^#\s*import site', 'import site' | Set-Content $pth.FullName -Encoding ASCII
  $gp = Join-Path $Rt 'get-pip.py'
  try { Invoke-WebRequest 'https://bootstrap.pypa.io/get-pip.py' -OutFile $gp -UseBasicParsing }
  catch { Remove-Item $PyDir -Recurse -Force -ErrorAction SilentlyContinue; Fail "telechargement de pip ($($_.Exception.Message))" }
  & $Py $gp --no-warn-script-location --disable-pip-version-check -q
  if ($LASTEXITCODE -ne 0) { Remove-Item $PyDir -Recurse -Force -ErrorAction SilentlyContinue; Fail 'installation de pip' }
  Remove-Item $gp -Force -ErrorAction SilentlyContinue
} else { Write-Host '  [1/4] Python : ok' -ForegroundColor Cyan }

Write-Host '  [2/4] Modules (yt-dlp, ffmpeg, images)...' -ForegroundColor Cyan
& $Py -m pip install --no-warn-script-location --disable-pip-version-check -q -U 'yt-dlp[default]' imageio-ffmpeg Pillow python-dotenv requests
if ($LASTEXITCODE -ne 0) { Fail 'installation des modules' }

Write-Host '  [3/4] Moteur YouTube et connexion au relais...' -ForegroundColor Cyan
$Deno = Join-Path $Root 'tools\deno\deno.exe'
if (-not (Test-Path $Deno)) {
  $dd = Join-Path $Root 'tools\deno'
  New-Item -ItemType Directory -Force -Path $dd | Out-Null
  $zip = Join-Path $dd 'deno.zip'
  try {
    Invoke-WebRequest 'https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip' -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $dd -Force
  } catch { Write-Host "  (moteur YouTube : nouvel essai au premier montage)" -ForegroundColor Yellow }
  Remove-Item $zip -Force -ErrorAction SilentlyContinue
}
$cfg = Get-Content (Join-Path $Root 'config.json') -Raw | ConvertFrom-Json
try {
  Invoke-RestMethod -Uri ($cfg.url.TrimEnd('/') + '/pc/state?name=test') -Headers @{ 'X-Worker-Token' = $cfg.token } -UseBasicParsing | Out-Null
  Write-Host '  Relais : ok' -ForegroundColor Green
} catch {
  if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 404) { Write-Host '  Relais : ok' -ForegroundColor Green }
  else { Write-Host "  !! Relais injoignable pour l'instant ($($_.Exception.Message)) : le PC reessaiera tout seul." -ForegroundColor Yellow }
}

Write-Host ''
Write-Host '  [4/4] Montage automatique' -ForegroundColor Cyan
Write-Host '  Une tache Windows "Drylow Actu" va verifier toutes les 15 minutes (quand le PC est allume)'
Write-Host '  si Claude a prepare une video. Si oui, elle la monte en arriere-plan, sans fenetre, puis efface les clips.'
Write-Host '  Pour l''enlever un jour : double-clic sur "Desinstaller".'
$ans = Read-Host '  Activer le montage automatique ? (O/N)'
if ($ans -notmatch '^[oOyY]') {
  Write-Host '  Pas active. Tu peux relancer Installer quand tu veux.' -ForegroundColor Yellow
  exit 0
}
try {
  $act = New-ScheduledTaskAction -Execute $PyW -Argument ('"' + (Join-Path $Root 'pc_agent.py') + '"') -WorkingDirectory $Root
  $t1 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 3650)
  $t2 = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
  $set = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 6) -MultipleInstances IgnoreNew
  Register-ScheduledTask -TaskName $Task -Action $act -Trigger @($t1, $t2) -Settings $set -Description 'Drylow : monte les videos d''actu preparees par Claude (pc_agent.py). Enlever : Desinstaller.bat' -Force | Out-Null
  Start-ScheduledTask -TaskName $Task
} catch { Fail "activation de la tache Windows ($($_.Exception.Message))" }
Write-Host ''
Write-Host '  C''EST INSTALLE. Tu n''as plus rien a faire.' -ForegroundColor Green
Write-Host '  Ton PC monte maintenant tout seul les videos que Claude prepare (quand il est allume).'
Write-Host '  Journal : agent.log dans ce dossier.'
