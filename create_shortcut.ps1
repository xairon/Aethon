$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Jarvis Web.lnk")
$Shortcut.TargetPath = "E:\TTS\start_jarvis_web.bat"
$Shortcut.WorkingDirectory = "E:\TTS"
$Shortcut.Description = "Lance Jarvis Web (Backend + Frontend)"
$Shortcut.WindowStyle = 1
$Shortcut.Save()
Write-Host "Raccourci cree sur le bureau!"
