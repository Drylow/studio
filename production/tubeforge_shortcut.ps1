$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$desktop = [Environment]::GetFolderPath('Desktop')
$launcher = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'tubeforge_desktop.ps1'))
if (-not (Test-Path -LiteralPath $launcher)) { throw 'TubeForge desktop launcher missing' }
$target = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
$destination = Join-Path $desktop 'TubeForge.lnk'
$shell = New-Object -ComObject WScript.Shell
if (Test-Path -LiteralPath $destination) {
    $old = $shell.CreateShortcut($destination)
    if ($old.Arguments -notlike '*tubeforge_desktop.ps1*') {
        $destination = Join-Path $desktop 'TubeForge - Studio.lnk'
        if (Test-Path -LiteralPath $destination) { throw 'An unrelated shortcut already occupies the alternate name' }
    }
}
$shortcut = $shell.CreateShortcut($destination)
$shortcut.TargetPath = $target
$shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $launcher + '"'
$shortcut.WorkingDirectory = $repo
$shortcut.Description = 'Demarrer TubeForge et ouvrir le studio local'
$shortcut.IconLocation = (Join-Path $env:SystemRoot 'System32/shell32.dll') + ',14'
$shortcut.WindowStyle = 7
$shortcut.Save()
$verified = $shell.CreateShortcut($destination)
if ($verified.TargetPath -ne $target -or $verified.Arguments -notlike '*tubeforge_desktop.ps1*') { throw 'Shortcut verification failed' }
Write-Output "TubeForge shortcut: $destination"
