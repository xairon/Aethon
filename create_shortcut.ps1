$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Aethon Web.lnk")
$Shortcut.TargetPath = "E:\TTS\start_aethon_web.bat"
$Shortcut.WorkingDirectory = "E:\TTS"
$Shortcut.Description = "Lance Aethon Web (Backend + Frontend)"
$Shortcut.WindowStyle = 1
$Shortcut.Save()
Write-Host "Raccourci cree sur le bureau!"
