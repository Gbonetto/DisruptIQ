@echo off
REM ========================================================
REM SCRIPT D'EXECUTION TESTS EXHAUSTIFS DISRUPTIQ
REM ========================================================

echo.
echo ========================================================
echo        TESTS EXHAUSTIFS DISRUPTIQ
echo ========================================================
echo.

REM Verification que Python est installe
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERREUR] Python n'est pas installe ou pas dans le PATH
    echo Installez Python 3.11+ depuis https://www.python.org/
    pause
    exit /b 1
)

echo [OK] Python detecte
echo.

REM Verification backend disponible
echo [INFO] Verification backend sur http://localhost:8000 ...
curl -s http://localhost:8000/health >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERREUR] Backend non accessible sur http://localhost:8000
    echo.
    echo Demarrez le backend avant de lancer les tests:
    echo   cd backend
    echo   python -m uvicorn app.main:app --reload
    echo.
    echo Ou via Docker:
    echo   docker-compose up backend
    echo.
    pause
    exit /b 1
)

echo [OK] Backend accessible
echo.

REM Menu de selection
echo ========================================================
echo MENU - Quelle suite de tests voulez-vous executer ?
echo ========================================================
echo.
echo 1. TOUS LES TESTS (Recommande - 20 minutes)
echo 2. Tests Conditions Reelles Syndic uniquement (10 minutes)
echo 3. Tests Memoire et Conversations Longues (5 minutes)
echo 4. Tests API Ultra-Exhaustifs (5 minutes)
echo 5. Quitter
echo.

set /p choice="Votre choix (1-5): "

if "%choice%"=="1" goto all_tests
if "%choice%"=="2" goto real_world
if "%choice%"=="3" goto memory
if "%choice%"=="4" goto ultra
if "%choice%"=="5" goto end

echo [ERREUR] Choix invalide
pause
exit /b 1

:all_tests
echo.
echo ========================================================
echo EXECUTION: TOUS LES TESTS
echo ========================================================
echo.
python run_all_comprehensive_tests.py
goto show_results

:real_world
echo.
echo ========================================================
echo EXECUTION: Tests Conditions Reelles Syndic
echo ========================================================
echo.
python test_runner_real_world_exhaustive.py
goto show_results

:memory
echo.
echo ========================================================
echo EXECUTION: Tests Memoire et Conversations Longues
echo ========================================================
echo.
python test_long_conversation_memory.py
goto show_results

:ultra
echo.
echo ========================================================
echo EXECUTION: Tests API Ultra-Exhaustifs
echo ========================================================
echo.
python test_runner_ultra_exhaustive.py
goto show_results

:show_results
echo.
echo ========================================================
echo TESTS TERMINES
echo ========================================================
echo.

REM Afficher fichiers JSON generes
echo Fichiers de resultats generes:
echo.
if exist test_results_comprehensive_all.json (
    echo   - test_results_comprehensive_all.json [TOUS LES TESTS]
)
if exist test_results_real_world_exhaustive.json (
    echo   - test_results_real_world_exhaustive.json [Conditions Reelles]
)
if exist test_results_long_conversation_memory.json (
    echo   - test_results_long_conversation_memory.json [Memoire]
)
if exist test_results_ultra_exhaustive.json (
    echo   - test_results_ultra_exhaustive.json [API Ultra]
)
echo.

REM Proposer d'ouvrir le rapport
echo ========================================================
echo Voulez-vous ouvrir le rapport JSON ? (O/N)
set /p open_report="Votre choix: "

if /i "%open_report%"=="O" (
    if exist test_results_comprehensive_all.json (
        start test_results_comprehensive_all.json
    ) else if exist test_results_real_world_exhaustive.json (
        start test_results_real_world_exhaustive.json
    ) else if exist test_results_long_conversation_memory.json (
        start test_results_long_conversation_memory.json
    ) else if exist test_results_ultra_exhaustive.json (
        start test_results_ultra_exhaustive.json
    )
)

echo.
echo ========================================================
echo Pour plus d'informations, consultez:
echo   - COMPREHENSIVE_TESTING_GUIDE.md (anglais)
echo   - TESTS_EXHAUSTIFS_RESUME.md (francais)
echo ========================================================
echo.

:end
pause
