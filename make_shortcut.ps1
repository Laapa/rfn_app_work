# Creates the desktop shortcut "Монитор ВЧ2" that starts run_monitor.bat from this folder.
$folder = $PSScriptRoot
$desktop = [Environment]::GetFolderPath("Desktop")
$link = Join-Path $desktop "Монитор ВЧ2.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = Join-Path $folder "run_monitor.bat"
$shortcut.WorkingDirectory = $folder
$shortcut.WindowStyle = 7            # start minimized: the short check window is not in the way
$shortcut.Description = "Монитор ВЧ2"
$shortcut.Save()

Write-Host "Ярлык создан: $link"
