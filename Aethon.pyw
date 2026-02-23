"""Aethon — No-console GUI launcher (double-click to run)."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
venv_python = HERE / "venv" / "Scripts" / "python.exe"
gui_main = HERE / "gui_main.py"

# Launch python.exe (not pythonw — CTranslate2 needs real stdout).
# STARTUPINFO hides the console window.
si = subprocess.STARTUPINFO()
si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
si.wShowWindow = 0  # SW_HIDE

target = str(venv_python) if venv_python.exists() else sys.executable

subprocess.Popen(
    [target, str(gui_main)],
    cwd=str(HERE),
    startupinfo=si,
)
