# Cage Dispatch (et les autres chaines d'actu) : monte sur ce PC les videos preparees par Claude.
# Tout s'installe la premiere fois DANS CE DOSSIER (Python, Git, moteur YouTube) : rien a faire a la main.
# Ensuite : recupere le projet sur GitHub, telecharge les extraits, monte, envoie sur Gofile,
# SUPPRIME les clips, et renvoie a Claude le lien + les captures de controle.
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}

$Root = $PSScriptRoot
$Rt = Join-Path $Root 'runtime'
$PyDir = Join-Path $Rt 'python'
$Py = Join-Path $PyDir 'python.exe'
$GitDir = Join-Path $Rt 'git'
$Repo = Join-Path $Root 'studio'
$RepoUrl = 'https://github.com/drylow/studio.git'
$PyVer = '3.12.10'
$GitFallback = 'https://github.com/git-for-windows/git/releases/download/v2.51.0.windows.1/PortableGit-2.51.0-64-bit.7z.exe'

function Fail($msg) {
  Write-Host ''
  Write-Host "  PROBLEME : $msg" -ForegroundColor Red
  Write-Host '  Verifie ta connexion internet puis relance. Si ca recommence, envoie une capture de cette fenetre a Claude.'
  exit 1
}
function Step($msg) { Write-Host "  $msg" -ForegroundColor Cyan }

Write-Host ''
Write-Host '  DRYLOW // MONTAGE DES VIDEOS D''ACTU' -ForegroundColor Red
Write-Host '  Ne ferme pas cette fenetre avant la fin.' -ForegroundColor Yellow
Write-Host ''
New-Item -ItemType Directory -Force -Path $Rt | Out-Null

# 1) Python (embarque, dans runtime\python)
if (-not (Test-Path $Py)) {
  Step '[1/5] Installation de Python (une seule fois)...'
  New-Item -ItemType Directory -Force -Path $PyDir | Out-Null
  $zip = Join-Path $Rt 'python.zip'
  try {
    Invoke-WebRequest "https://www.python.org/ftp/python/$PyVer/python-$PyVer-embed-amd64.zip" -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $PyDir -Force
    Remove-Item $zip -Force
  } catch { Remove-Item $PyDir -Recurse -Force -ErrorAction SilentlyContinue; Fail "telechargement de Python impossible ($($_.Exception.Message))" }
  # modules pip actives + dossiers du projet (le Python embarque n'ajoute pas le dossier du script)
  $pth = Get-ChildItem $PyDir -Filter 'python*._pth' | Select-Object -First 1
  $lines = (Get-Content $pth.FullName) -replace '^#\s*import site', 'import site'
  $lines += '..\..\studio'
  $lines += '..\..\studio\production'
  Set-Content $pth.FullName -Value $lines -Encoding ASCII
  $gp = Join-Path $Rt 'get-pip.py'
  try { Invoke-WebRequest 'https://bootstrap.pypa.io/get-pip.py' -OutFile $gp -UseBasicParsing }
  catch { Remove-Item $PyDir -Recurse -Force -ErrorAction SilentlyContinue; Fail "telechargement de pip impossible ($($_.Exception.Message))" }
  & $Py $gp --no-warn-script-location --disable-pip-version-check -q
  if ($LASTEXITCODE -ne 0) { Remove-Item $PyDir -Recurse -Force -ErrorAction SilentlyContinue; Fail 'installation de pip' }
  Remove-Item $gp -Force -ErrorAction SilentlyContinue
} else { Step '[1/5] Python : ok' }

# 2) Git (celui du PC s'il existe, sinon Git portable dans runtime\git)
$Git = $null
$sys = Get-Command git -ErrorAction SilentlyContinue
if ($sys) { $Git = $sys.Source }
elseif (Test-Path (Join-Path $GitDir 'cmd\git.exe')) { $Git = Join-Path $GitDir 'cmd\git.exe' }
else {
  Step '[2/5] Installation de Git (une seule fois)...'
  $url = $GitFallback
  try {
    $rel = Invoke-RestMethod 'https://api.github.com/repos/git-for-windows/git/releases/latest' -UseBasicParsing
    $a = $rel.assets | Where-Object { $_.name -like 'PortableGit-*-64-bit.7z.exe' } | Select-Object -First 1
    if ($a) { $url = $a.browser_download_url }
  } catch {}
  $exe = Join-Path $Rt 'PortableGit.7z.exe'
  try { Invoke-WebRequest $url -OutFile $exe -UseBasicParsing }
  catch { Fail "telechargement de Git impossible ($($_.Exception.Message))" }
  Start-Process -FilePath $exe -ArgumentList @("-o`"$GitDir`"", '-y') -Wait -WindowStyle Hidden
  Remove-Item $exe -Force -ErrorAction SilentlyContinue
  if (-not (Test-Path (Join-Path $GitDir 'cmd\git.exe'))) { Fail 'installation de Git' }
  $Git = Join-Path $GitDir 'cmd\git.exe'
}
if ($Git) { $env:PATH = (Split-Path $Git) + ';' + $env:PATH; Step '[2/5] Git : ok' }

# 3) Le projet (copie GitHub dans .\studio) : les videos a monter, preparees par Claude
if (-not (Test-Path (Join-Path $Repo '.git'))) {
  Step '[3/5] Recuperation du projet sur GitHub (une seule fois, quelques minutes)...'
  & git clone -q --depth 1 $RepoUrl $Repo
  if ($LASTEXITCODE -ne 0) { Fail 'recuperation du projet sur GitHub' }
} else {
  Step '[3/5] Mise a jour du projet...'
  & git -C $Repo pull -q --ff-only
}
& git -C $Repo config user.name 'Drylow PC'
& git -C $Repo config user.email 'pc@drylow.studio'

# Connexion GitHub maintenant (pas au bout d'une heure de montage) : sert a renvoyer le lien et les captures.
Write-Host ''
Write-Host '  Connexion a GitHub : si une fenetre s''ouvre, clique "Sign in with your browser"' -ForegroundColor Yellow
Write-Host '  et connecte-toi avec le compte GitHub du projet (une seule fois).' -ForegroundColor Yellow
& git -C $Repo push --dry-run -q origin HEAD 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host '  !! GitHub refuse l''envoi : le montage se fait quand meme, tu donneras le lien a Claude a la main.' -ForegroundColor Red
} else { Write-Host '  GitHub : ok' -ForegroundColor Green }
Write-Host ''

# 4) Moteur JavaScript pour YouTube (deno, dans studio\tools\deno) + modules Python
$Deno = Join-Path $Repo 'tools\deno\deno.exe'
if (-not (Test-Path $Deno)) {
  Step '[4/5] Installation du moteur YouTube (une seule fois)...'
  $dd = Join-Path $Repo 'tools\deno'
  New-Item -ItemType Directory -Force -Path $dd | Out-Null
  $zip = Join-Path $dd 'deno.zip'
  try {
    Invoke-WebRequest 'https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip' -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $dd -Force
  } catch { Write-Host "  (moteur YouTube non installe : $($_.Exception.Message))" -ForegroundColor Yellow }
  Remove-Item $zip -Force -ErrorAction SilentlyContinue
}
if (Test-Path $Deno) { $env:PATH = (Split-Path $Deno) + ';' + $env:PATH }
Step '[4/5] Modules (yt-dlp, ffmpeg, images) : verification...'
& $Py -m pip install --no-warn-script-location --disable-pip-version-check -q -U 'yt-dlp[default]' imageio-ffmpeg Pillow python-dotenv requests
if ($LASTEXITCODE -ne 0) { Fail 'installation des modules' }

# 5) Montage de toutes les videos pretes (lien Gofile affiche a la fin, clips supprimes)
Write-Host ''
Step '[5/5] Montage (30 min a 1 h par video : telechargement des extraits, montage, envoi)...'
Write-Host ''
Push-Location $Repo
& $Py (Join-Path $Repo 'production\news.py') pc
Pop-Location
