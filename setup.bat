@echo off
echo ==========================================
echo   JARVIS - Installation des dependances
echo ==========================================
echo.

:: Vérifier Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python non trouve. Installe Python 3.10+ depuis python.org
    pause
    exit /b 1
)

:: Vérifier Ollama
ollama --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Ollama non trouve. Installe depuis ollama.com
    pause
    exit /b 1
)

:: Créer venv si pas déjà fait
if not exist "venv" (
    echo [1/5] Creation de l'environnement virtuel...
    python -m venv venv
)

:: Activer venv
call venv\Scripts\activate.bat

:: Installer PyTorch avec CUDA
echo [2/5] Installation de PyTorch avec CUDA...
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124 --quiet

:: Installer les dépendances
echo [3/5] Installation des dependances...
pip install -r requirements.txt --quiet

:: Vérifier espeak-ng (requis par Kokoro)
where espeak-ng >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ATTENTION] espeak-ng non trouve dans le PATH.
    echo Kokoro TTS a besoin de espeak-ng pour fonctionner.
    echo.
    echo Telecharge-le depuis:
    echo   https://github.com/espeak-ng/espeak-ng/releases
    echo.
    echo Installe le .msi et ajoute le dossier d'installation au PATH.
    echo.
)

:: Télécharger le modèle Ollama si pas présent
echo [4/5] Verification du modele Ollama...
ollama list | findstr "qwen3:14b" >nul 2>&1
if errorlevel 1 (
    echo Telechargement de qwen3:14b (peut prendre du temps)...
    ollama pull qwen3:14b
) else (
    echo qwen3:14b deja installe.
)

echo.
echo [5/5] Verification du modele faster-whisper...
echo Le modele STT sera telecharge au premier lancement.

echo.
echo ==========================================
echo   Installation terminee !
echo.
echo   Pour lancer Jarvis:
echo     venv\Scripts\activate
echo     python main.py --no-wake-word
echo.
echo   Avec wake word:
echo     python main.py
echo.
echo   Options:
echo     --model qwen3:30b-a3b   (plus intelligent, plus de VRAM)
echo     --model qwen3:8b        (plus rapide, moins de VRAM)
echo     --language en            (anglais)
echo     --no-memory              (sans memoire longue)
echo     -v                       (mode debug)
echo ==========================================
pause
