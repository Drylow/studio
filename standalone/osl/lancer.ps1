# Oddly Specific Lives Studio : installe tout la premiere fois (dans ce dossier), puis lance le studio.
# Rien n'est installe sur le reste du PC : Python et les modules vivent dans app\runtime.
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$App = $PSScriptRoot
$Rt = Join-Path $App 'runtime'
$PyDir = Join-Path $Rt 'python'
$Py = Join-Path $PyDir 'python.exe'
$Port = 5057
$Url = "http://127.0.0.1:$Port"
$PyVer = '3.12.10'

function Test-Studio {
  try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', $Port); $c.Close(); return $true }
  catch { return $false }
}
function Fail($msg) {
  Write-Host ''
  Write-Host "  PROBLEME : $msg" -ForegroundColor Red
  Write-Host '  Verifie ta connexion internet puis relance. Si ca recommence, envoie une capture de cette fenetre.'
  exit 1
}

Write-Host ''
Write-Host '  ODDLY SPECIFIC LIVES // STUDIO' -ForegroundColor Magenta
Write-Host ''

if (Test-Studio) {
  Write-Host '  Le studio tourne deja : ouverture de la page.'
  Start-Process $Url
  exit 0
}

if (-not (Test-Path $Py)) {
  Write-Host '  Premiere installation : une seule fois, 3 a 6 minutes. Ne ferme pas cette fenetre.' -ForegroundColor Yellow
  New-Item -ItemType Directory -Force -Path $PyDir | Out-Null
  $zip = Join-Path $Rt 'python.zip'
  Write-Host '  [1/3] Telechargement de Python...'
  try {
    Invoke-WebRequest "https://www.python.org/ftp/python/$PyVer/python-$PyVer-embed-amd64.zip" -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $PyDir -Force
    Remove-Item $zip -Force
  } catch { Remove-Item $PyDir -Recurse -Force -ErrorAction SilentlyContinue; Fail "telechargement de Python impossible ($($_.Exception.Message))" }
  # active les modules installes par pip (site-packages) dans le Python embarque
  $pth = Get-ChildItem $PyDir -Filter 'python*._pth' | Select-Object -First 1
  (Get-Content $pth.FullName) -replace '^#\s*import site', 'import site' | Set-Content $pth.FullName -Encoding ASCII
  Write-Host '  [2/3] Installation de pip...'
  $gp = Join-Path $Rt 'get-pip.py'
  try { Invoke-WebRequest 'https://bootstrap.pypa.io/get-pip.py' -OutFile $gp -UseBasicParsing }
  catch { Remove-Item $PyDir -Recurse -Force -ErrorAction SilentlyContinue; Fail "telechargement de pip impossible ($($_.Exception.Message))" }
  & $Py $gp --no-warn-script-location --disable-pip-version-check -q
  if ($LASTEXITCODE -ne 0) { Remove-Item $PyDir -Recurse -Force -ErrorAction SilentlyContinue; Fail 'installation de pip' }
  Remove-Item $gp -Force -ErrorAction SilentlyContinue
}

& $Py -c "import flask, dotenv, PIL, edge_tts, imageio_ffmpeg, youtube_transcript_api" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host '  [3/3] Installation des modules (Flask, Pillow, ffmpeg...), environ 40 Mo...'
  & $Py -m pip install --no-warn-script-location --disable-pip-version-check -q -r (Join-Path $App 'requirements.txt')
  if ($LASTEXITCODE -ne 0) { Fail 'installation des modules' }
}

Write-Host ''
Write-Host "  Studio pret : $Url" -ForegroundColor Green
Write-Host '  La page s''ouvre dans ton navigateur.'
Write-Host '  Laisse cette fenetre ouverte pendant que tu travailles : la fermer eteint le studio.'
Write-Host ''
Start-Process -WindowStyle Hidden -FilePath $Py -ArgumentList @("`"$(Join-Path $App 'open_browser.py')`"", $Port)
& $Py (Join-Path $App 'studio_app.py') $Port
