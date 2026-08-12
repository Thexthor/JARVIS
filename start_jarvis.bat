@echo off
setlocal EnableDelayedExpansion

title START JARVIS

set "JARVIS_DIR=C:\Users\Gabo\Desktop\JARVIS"
set "DOCKER_EXE=C:\Program Files\Docker\Docker\Docker Desktop.exe"
set "BOOT_FILE=%TEMP%\jarvis_last_boot.txt"

echo ========================================
echo            INICIANDO JARVIS
echo ========================================
echo.


:: ==================================================
:: IDENTIFICAR EL ARRANQUE ACTUAL DE WINDOWS
:: ==================================================

for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('yyyyMMddHHmmss')"`) do (
    set "CURRENT_BOOT=%%A"
)

set "LAST_BOOT="

if exist "%BOOT_FILE%" (
    set /p LAST_BOOT=<"%BOOT_FILE%"
)


:: ==================================================
:: DOCKER DESKTOP - OCULTO
:: ==================================================

echo [1] Comprobando Docker...

tasklist /FI "IMAGENAME eq Docker Desktop.exe" 2>nul | find /I "Docker Desktop.exe" >nul

if errorlevel 1 (

    echo Iniciando Docker en segundo plano...

    powershell -NoProfile -WindowStyle Hidden -Command ^
    "Start-Process '%DOCKER_EXE%' -WindowStyle Hidden"

    echo Esperando que Docker arranque...

    timeout /t 12 /nobreak >nul

) else (

    echo Docker ya estaba iniciado.

)


:: ==================================================
:: SEARXNG
:: ==================================================

echo [2] Comprobando SearXNG...

powershell -NoProfile -WindowStyle Hidden -Command ^
"$p = Start-Process 'docker' -ArgumentList 'start jarvis-searxng' -WindowStyle Hidden -PassThru; if(-not $p.WaitForExit(15000)){ try{$p.Kill()}catch{} }"

timeout /t 2 /nobreak >nul

echo SearXNG comprobado.


:: ==================================================
:: OLLAMA PERSISTENTE / CPU ESTABLE
:: ==================================================

echo [3] Comprobando Ollama...

powershell -NoProfile -Command ^
"try { $r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags -TimeoutSec 2; if($r.StatusCode -eq 200){ exit 0 } else { exit 1 } } catch { exit 1 }"

if errorlevel 1 (

    echo Ollama no responde correctamente.
    echo Cerrando instancia anterior si existe...

    taskkill /IM ollama.exe /F >nul 2>&1

    timeout /t 2 /nobreak >nul

    echo Iniciando Ollama forzado a CPU...

    start "JARVIS OLLAMA CPU" /min cmd /c ^
    "set OLLAMA_VULKAN=0 && set OLLAMA_LLM_LIBRARY=cpu_avx2 && ollama serve"

    echo Esperando Ollama...

    timeout /t 5 /nobreak >nul

    powershell -NoProfile -Command ^
    "try { $r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags -TimeoutSec 3; if($r.StatusCode -eq 200){ exit 0 } else { exit 1 } } catch { exit 1 }"

    if errorlevel 1 (
        echo ERROR: Ollama no pudo iniciarse correctamente.
    ) else (
        echo Ollama CPU listo.
    )

) else (

    echo Ollama ya esta funcionando correctamente.

)

:: ==================================================
:: INTERNET SERVER - PUERTO 5000
:: VISIBLE EN LA BARRA DE TAREAS
:: ==================================================

echo [4] Comprobando Internet Server...

netstat -ano | findstr ":5000" | findstr "LISTENING" >nul

if errorlevel 1 (

    start "JARVIS INTERNET" cmd /k ^
    "cd /d %JARVIS_DIR% && python internet_server.py"

) else (

    echo Internet Server ya estaba activo.

)


:: ==================================================
:: MEMORY SERVER - PUERTO 5070
:: ==================================================

echo [5] Comprobando Memory Server...

netstat -ano | findstr ":5070" | findstr "LISTENING" >nul

if errorlevel 1 (

    start "JARVIS MEMORY" cmd /k ^
    "cd /d %JARVIS_DIR% && python memory_server.py"

) else (

    echo Memory Server ya estaba activo.

)


:: ==================================================
:: APP OPENER SERVER - PUERTO 5050
:: ==================================================

echo [6] Comprobando App Opener...

netstat -ano | findstr ":5050" | findstr "LISTENING" >nul

if errorlevel 1 (

    start "JARVIS APP OPENER" cmd /k ^
    "cd /d %JARVIS_DIR% && python app_opener_server.py"

) else (

    echo App Opener ya estaba activo.

)


:: ==================================================
:: VOICE SERVER - PUERTO 5090
:: ==================================================

echo [7] Comprobando Voice Server...

netstat -ano | findstr ":5090" | findstr "LISTENING" >nul

if errorlevel 1 (

    start "JARVIS VOICE" cmd /k ^
    "cd /d %JARVIS_DIR% && python voice_server.py"

) else (

    echo Voice Server ya estaba activo.

)


:: ==================================================
:: VISION SERVER - PUERTO 5080
:: ==================================================

echo [8] Comprobando Vision Server...

netstat -ano | findstr ":5080" | findstr "LISTENING" >nul

if errorlevel 1 (

    start "JARVIS VISION" cmd /k ^
    "cd /d %JARVIS_DIR% && python vision_server.py"

) else (

    echo Vision Server ya estaba activo.

)


:: ==================================================
:: FRONTEND VITE - PUERTO 5173
:: ==================================================

echo [9] Comprobando Frontend...

netstat -ano | findstr ":5173" | findstr "LISTENING" >nul

if errorlevel 1 (

    start "JARVIS FRONTEND" cmd /k ^
    "cd /d %JARVIS_DIR%\JarvisApp && npm run dev"

    timeout /t 5 /nobreak >nul

) else (

    echo Frontend ya estaba activo.

)


:: ==================================================
:: ABRIR JARVIS
:: ==================================================

echo [10] Abriendo Jarvis...

start "" chrome "http://localhost:5173"


echo.
echo ========================================
echo              JARVIS LISTO
echo ========================================
echo.
echo Docker ........ SEGUNDO PLANO
echo SearXNG ....... SEGUNDO PLANO
echo Ollama ........ CPU / SEGUNDO PLANO
echo Internet ...... ACTIVO
echo Memoria ....... ACTIVA
echo Apps .......... ACTIVAS
echo Voz ........... ACTIVA
echo Vision ........ ACTIVA
echo Frontend ...... ACTIVO
echo.
echo ========================================

timeout /t 2 /nobreak >nul

exit