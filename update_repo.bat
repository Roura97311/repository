@echo off
setlocal EnableExtensions

REM ============================================================
REM AEON MIRO NOX - UPDATE REPOSITORY
REM Sources: D:\Roura97311\aeon.miro.nox\skins-addons
REM Output : D:\Roura97311\aeon.miro.nox\repository
REM ============================================================

set "BASE=D:\Roura97311\aeon.miro.nox"
set "SRC=%BASE%\skins-addons"
set "REPO=%BASE%\repository"

cd /d "%REPO%" || (
    echo ERREUR : impossible d'acceder a %REPO%
    pause
    exit /b 1
)

echo.
echo ============================================================
echo     AEON MIRO NOX - MISE A JOUR DU REPOSITORY
echo ============================================================
echo.

REM ------------------------------------------------------------
REM 1. Verification de Python
REM ------------------------------------------------------------
echo [1/9] Verification de Python 3...
py -3 --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR : Python 3 n'est pas disponible via "py -3".
    echo Installe Python 3 puis relance ce fichier.
    pause
    exit /b 1
)

REM ------------------------------------------------------------
REM 2. Verification de Git
REM ------------------------------------------------------------
echo [2/9] Verification de Git...
git --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR : Git n'est pas disponible.
    pause
    exit /b 1
)

REM ------------------------------------------------------------
REM 3. Synchronisation du repository local
REM ------------------------------------------------------------
echo [3/9] Recuperation des modifications GitHub...
git pull --ff-only origin main
if errorlevel 1 (
    echo.
    echo ERREUR : git pull impossible.
    echo Verifie qu'il n'y a pas de modifications locales non commit.
    pause
    exit /b 1
)

REM ------------------------------------------------------------
REM 4. Verification des sources
REM ------------------------------------------------------------
echo [4/9] Verification des sources...

for %%A in (
    repository.aeon.miro.nox
    resource.images.miro.nox
    script.aeon.miro.nox
	script.skin.helper.colorpicker
    skin.aeon.miro.nox.matrix
    skin.aeon.miro.nox.nexus
    skin.aeon.miro.nox.omega
) do (
    if not exist "%SRC%\%%A\addon.xml" (
        echo ERREUR : source manquante : %SRC%\%%A
        pause
        exit /b 1
    )
)

REM ------------------------------------------------------------
REM 5. Controle de la version du repository addon
REM ------------------------------------------------------------
echo [5/9] Verification repository.aeon.miro.nox...

findstr /C:"1.0.22" "%SRC%\repository.aeon.miro.nox\addon.xml" >nul
if errorlevel 1 (
    echo ATTENTION :
    echo Le source repository.aeon.miro.nox n'est pas encore en version 1.0.22.
    echo Mets a jour :
    echo %SRC%\repository.aeon.miro.nox\addon.xml
    echo avec la version 1.0.22 et les nouvelles balises Matrix/Nexus/Omega.
    pause
    exit /b 1
)

REM ------------------------------------------------------------
REM 6. Preparation des sorties generees
REM ------------------------------------------------------------
echo [6/9] Preparation des catalogues sans suppression de l'historique...

REM IMPORTANT : ne jamais supprimer matrix/nexus/omega.
REM Les anciennes versions des addons et des skins doivent rester
REM disponibles dans le repository.
if not exist "%REPO%\matrix" mkdir "%REPO%\matrix"
if not exist "%REPO%\nexus"  mkdir "%REPO%\nexus"
if not exist "%REPO%\omega"  mkdir "%REPO%\omega"

REM Aucun paquet genere n'est supprime ici.
REM update_repo.py ajoute la nouvelle version et conserve les anciennes.

REM ------------------------------------------------------------
REM 7. Generation des catalogues
REM ------------------------------------------------------------
echo.
echo [7/9] Generation MATRIX 19.x...

py -3 "%REPO%\update_repo.py" ^
    --datadir "%REPO%\matrix" ^
    --info "%REPO%\matrix\addons.xml" ^
    --checksum "%REPO%\matrix\addons.xml.md5" ^
    "%SRC%\repository.aeon.miro.nox" ^
    "%SRC%\resource.images.miro.nox" ^
    "%SRC%\script.aeon.miro.nox" ^
    "%SRC%\skin.aeon.miro.nox.matrix"

if errorlevel 1 (
    echo ERREUR lors de la generation MATRIX.
    pause
    exit /b 1
)

echo.
echo [7/9] Generation NEXUS 20.x...

py -3 "%REPO%\update_repo.py" ^
    --datadir "%REPO%\nexus" ^
    --info "%REPO%\nexus\addons.xml" ^
    --checksum "%REPO%\nexus\addons.xml.md5" ^
    "%SRC%\repository.aeon.miro.nox" ^
    "%SRC%\resource.images.miro.nox" ^
	"%SRC%\script.skin.helper.colorpicker" ^
    "%SRC%\script.aeon.miro.nox" ^
    "%SRC%\skin.aeon.miro.nox.nexus"

if errorlevel 1 (
    echo ERREUR lors de la generation NEXUS.
    pause
    exit /b 1
)

echo.
echo [7/9] Generation OMEGA 21.x...

py -3 "%REPO%\update_repo.py" ^
    --datadir "%REPO%\omega" ^
    --info "%REPO%\omega\addons.xml" ^
    --checksum "%REPO%\omega\addons.xml.md5" ^
    "%SRC%\repository.aeon.miro.nox" ^
    "%SRC%\resource.images.miro.nox" ^
	"%SRC%\script.skin.helper.colorpicker" ^
    "%SRC%\script.aeon.miro.nox" ^
    "%SRC%\skin.aeon.miro.nox.omega"

if errorlevel 1 (
    echo ERREUR lors de la generation OMEGA.
    pause
    exit /b 1
)

REM Aucun catalogue racine n'est genere.
REM Les catalogues officiels sont separes par version Kodi :
REM Matrix, Nexus et Omega.
REM ------------------------------------------------------------
REM 8. Verification
REM ------------------------------------------------------------
echo.
echo [8/9] Verification des fichiers...

echo.
echo -------- MATRIX --------
dir /b "%REPO%\matrix"

echo.
echo -------- NEXUS ---------
dir /b "%REPO%\nexus"

echo.
echo -------- OMEGA ---------
dir /b "%REPO%\omega"

REM ------------------------------------------------------------
REM 9. Commit + Push
REM ------------------------------------------------------------
echo.
echo [9/9] Commit et push GitHub...

git add -A
git status

git diff --cached --quiet
if not errorlevel 1 (
    echo.
    echo Aucune modification a committer.
    echo.
) else (
    git commit -m "Mise a jour repository Matrix Nexus Omega"
    if errorlevel 1 (
        echo ERREUR : commit impossible.
        pause
        exit /b 1
    )
)

git push origin main
if errorlevel 1 (
    echo ERREUR : git push impossible.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo              MISE A JOUR TERMINEE
echo ============================================================
echo.
echo Matrix : OK
echo Nexus  : OK
echo Omega  : OK
echo MD5    : OK
echo GitHub : OK
echo.
pause
