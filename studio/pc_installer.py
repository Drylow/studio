"""Small auditable installer for our local Windows companion; no remote script."""
import base64
import hashlib
import io
import re
import unicodedata
import zipfile
from studio.store import ROOT

SOURCE = ROOT / "standalone/pc_bridge/EdgerunnersPC.cs"
ASSEMBLIES = "@('System.dll','System.Core.dll','System.Web.dll','System.Windows.Forms.dll','System.Drawing.dll','System.Net.Http.dll','System.Web.Extensions.dll')"


def installer_zip(uri):
    if not re.fullmatch(r"edgerunners-studio://connect/pc-local-[a-f0-9]{32}\?token=[a-f0-9]{64}", uri):
        raise ValueError("Lien d’installation invalide.")
    source = SOURCE.read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    # The footer avoids the cmd.exe 8191-character argument limit. Only our
    # bundled, hash-checked source is compiled; no ExecutionPolicy bypass.
    ps = (
        "$ErrorActionPreference='Stop';try{"
        "$raw=[IO.File]::ReadAllText($env:EDG_INSTALL_FILE);"
        r"$encoded=($raw -split '::EDGERUNNERS_SOURCE_BEGIN\r?\n',2)[1].Trim();"
        "$bytes=[Convert]::FromBase64String($encoded);"
        "$hash=[BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($bytes)).Replace('-','').ToLower();"
        f"if($hash -ne '{digest}'){{throw 'Fichier d’installation incomplet'}};"
        "$root=Join-Path $env:LOCALAPPDATA 'EdgerunnersStudio';"
        "$app=Join-Path $root 'app';"
        f"$version=Join-Path $app '{digest[:16]}';"
        "foreach($p in @($root,$app,$version)){"
        "if(Test-Path -LiteralPath $p){if(([IO.File]::GetAttributes($p) -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Dossier non autorisé'}}"
        "else{[IO.Directory]::CreateDirectory($p)|Out-Null}};"
        "$exe=Join-Path $version 'EdgerunnersStudio.exe';"
        "if(!(Test-Path -LiteralPath $exe)){"
        "Write-Host 'Installation de l’assistant Edgerunners...';"
        "$source=[Text.Encoding]::UTF8.GetString($bytes);"
        f"Add-Type -TypeDefinition $source -OutputAssembly $exe -OutputType WindowsApplication -ReferencedAssemblies {ASSEMBLIES}}};"
        "if(([IO.File]::GetAttributes($exe) -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Programme non autorisé'};"
        r"$key='HKCU:\Software\Classes\edgerunners-studio';"
        "New-Item -Path $key -Force|Out-Null;"
        "Set-Item -Path $key -Value 'Edgerunners Studio';"
        "New-ItemProperty -Path $key -Name 'URL Protocol' -Value '' -PropertyType String -Force|Out-Null;"
        r"New-Item -Path ($key+'\shell\open\command') -Force|Out-Null;"
        r"Set-Item -Path ($key+'\shell\open\command') -Value ([char]34+$exe+[char]34+' '+[char]34+'%1'+[char]34);"
        "Write-Host 'Assistant installé. Ouverture de la connexion sur ce PC...';"
        f"Start-Process -FilePath $exe -ArgumentList '{uri}';exit 0"
        "}catch{Write-Host 'Installation interrompue. Aucun envoi de vidéo.';Write-Host $_.Exception.Message;exit 1}"
    )
    cmd = (
        '@echo off\r\nsetlocal\r\nset "EDG_INSTALL_FILE=%~f0"\r\n'
        'powershell.exe -NoProfile -Command "' + unicodedata.normalize("NFKD", ps).encode("ascii", "ignore").decode().replace("%", "%%") + '"\r\n'
        'if errorlevel 1 (\r\n echo Retournez dans le studio pour relancer ou signaler cette erreur.\r\n pause\r\n)\r\n'
        'goto :eof\r\n::EDGERUNNERS_SOURCE_BEGIN\r\n' + base64.b64encode(source).decode() + '\r\n'
    )
    if len(cmd.splitlines()[3]) > 8000:
        raise ValueError("Commande d’installation trop longue.")
    readme = (
        "EDGERUNNERS STUDIO — connexion depuis ce PC (Windows + Chrome)\r\n\r\n"
        "1. Extrais le ZIP dans un dossier.\r\n2. Double-clique sur Installer.cmd.\r\n"
        "3. Dans la nouvelle fenêtre Chrome, connecte-toi à YouTube et choisis la chaîne indiquée.\r\n\r\n"
        "Installation personnelle, sans droits administrateur ni logiciel externe.\r\n"
        "Le programme est construit depuis le code EdgerunnersPC.cs inclus.\r\n"
        "Aucun mot de passe, cookie Google ou secret du serveur n’est envoyé au studio.\r\n"
        "Le lien initial expire après 20 minutes. Ensuite, relance depuis edgerunners.fr.\r\n"
        "L’assistant ne publie pas encore de vidéo. Il vérifie seulement la bonne chaîne.\r\n"
        "Si Windows bloque l’installation, ne désactive aucune protection : indique l’erreur dans le studio.\r\n"
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Installer.cmd", cmd.encode("utf-8"))
        archive.writestr("EdgerunnersPC.cs", source)
        archive.writestr("LISEZ-MOI.txt", readme.encode("utf-8-sig"))
    return out.getvalue()
