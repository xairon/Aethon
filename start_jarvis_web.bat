@echo off
setlocal enabledelayedexpansion
title Jarvis Web

set "ROOT=E:\TTS"
set "VENV=%ROOT%\venv\Scripts"
set "WEB=%ROOT%\web"

echo.
echo  ========================================
echo       JARVIS WEB - Lancement
echo  ========================================
echo.

:: Verifier le venv Python
if not exist "%VENV%\python.exe" (
    echo  [ERREUR] venv Python introuvable : %VENV%
    echo  Lance setup.bat d'abord.
    pause
    exit /b 1
)

:: Verifier node_modules
if not exist "%WEB%\node_modules" (
    echo  [INFO] Installation des dependances npm...
    cd /d "%WEB%"
    call npm install
    if errorlevel 1 (
        echo  [ERREUR] npm install a echoue.
        pause
        exit /b 1
    )
)

:: Ajouter espeak-ng au PATH (requis par Kokoro TTS)
if exist "C:\Program Files\eSpeak NG" set "PATH=C:\Program Files\eSpeak NG;%PATH%"

:: --- Nettoyer les anciens processus sur les ports 8765 et 5173 ---
echo  [0/2] Nettoyage des anciens processus...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\_cleanup_ports.ps1" >nul 2>&1
:: Laisser le temps aux ports de se liberer
timeout /t 2 /nobreak >nul

:: --- Lancer le backend FastAPI ---
echo  [1/2] Demarrage du backend (FastAPI :8765)...
start "Jarvis Backend" /min "%VENV%\python.exe" "%ROOT%\server\main.py"

:: Attendre que le backend soit pret (max 30s)
echo        Attente du serveur...
set /a attempts=0
:wait_backend
timeout /t 1 /nobreak >nul
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8765/api/config' -UseBasicParsing -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel!==0 goto backend_ready
set /a attempts+=1
if !attempts! lss 30 goto wait_backend
echo  [WARN] Le backend n'a pas repondu apres 30s, on continue...

:backend_ready
echo        Backend OK!
echo.

:: --- Lancer le frontend Vite (--strictPort pour eviter port auto-increment) ---
echo  [2/2] Demarrage du frontend (Vite :5173)...
cd /d "%WEB%"
start "Jarvis Frontend" /min npx vite --host 127.0.0.1 --port 5173 --strictPort

:: Attendre que Vite soit pret (max 15s)
echo        Attente de Vite...
set /a attempts=0
:wait_frontend
timeout /t 1 /nobreak >nul
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel!==0 goto frontend_ready
set /a attempts+=1
if !attempts! lss 15 goto wait_frontend
echo  [WARN] Vite n'a pas repondu apres 15s, on continue...

:frontend_ready
echo        Frontend OK!
echo.

:: --- Ouvrir le navigateur ---
echo  ========================================
echo    Ouverture de http://localhost:5173
echo  ========================================
echo.
start "" "http://localhost:5173"

echo  Jarvis est pret!
echo.
echo  Backend  : http://localhost:8765 (minimise)
echo  Frontend : http://localhost:5173 (minimise)
echo.
echo  Pour arreter : fermez cette fenetre.
echo.
pause
