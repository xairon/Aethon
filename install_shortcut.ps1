# Jarvis — Create desktop shortcut
# Run: powershell -ExecutionPolicy Bypass -File install_shortcut.ps1

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $pythonw) {
    $pythonw = (Get-Command python -ErrorAction SilentlyContinue).Source
}

$WshShell = New-Object -ComObject WScript.Shell
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "Jarvis.lnk"

$shortcut = $WshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = "`"$projectDir\jarvis.pyw`""
$shortcut.WorkingDirectory = $projectDir
$shortcut.Description = "Jarvis Voice Assistant"
$shortcut.Save()

Write-Host "Shortcut created: $shortcutPath" -ForegroundColor Green
Write-Host "Double-click 'Jarvis' on your desktop to launch!" -ForegroundColor Cyan
