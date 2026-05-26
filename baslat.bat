@echo off
chcp 65001 >nul
cd /d "%~dp0"

if "%PORT%"=="" set PORT=8080
set "PROJ_DIR=%~dp0"
set "PROJ_DIR=%PROJ_DIR:~0,-1%"

echo.
echo  PatiRota baslatiliyor...
echo  (Eski sunucu/port/teminal otomatik temizlenir - durdur.bat gerekmez)
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo HATA: Python bulunamadi. https://www.python.org adresinden Python 3.11+ kurun.
    pause
    exit /b 1
)

python -c "import nicegui" >nul 2>&1
if errorlevel 1 (
    echo Bagimliliklar kuruluyor, lutfen bekleyin...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo HATA: Paket kurulumu basarisiz. Python 3.11 veya 3.12 onerilir.
        pause
        exit /b 1
    )
)

if not exist "patirota.db" (
    echo Veritabani olusturuluyor...
    python database.py
)

call :temizle
if errorlevel 1 exit /b 1

echo  Sunucu baslatiliyor...
title PatiRota [%PORT%]
echo  Tarayici: http://localhost:%PORT%  (127.0.0.1 degil - konum izni icin onemli)
echo  Kapatmak icin bu pencerede Ctrl+C
echo.

if exist "%~dp0.env.local" (
  for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%~dp0.env.local") do (
    if /i "%%a"=="GOOGLE_MAPS_API_KEY" if not defined GOOGLE_MAPS_API_KEY set "GOOGLE_MAPS_API_KEY=%%b"
  )
)
if not defined GOOGLE_MAPS_API_KEY (
  echo  UYARI: GOOGLE_MAPS_API_KEY yok. .env.local dosyasina ekleyin ^(.env.example^).
)

set LOCAL_DEV=1
set OPEN_BROWSER=1
set RELOAD=1
python main.py

pause
exit /b 0

:temizle
echo  [Temizlik] Eski PatiRota pencereleri, surecleri ve port %PORT%...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = '%PROJ_DIR%'; $port = %PORT%;" ^
  "$callerCmd = (Get-CimInstance Win32_Process -Filter ('ProcessId=' + $PID)).ParentProcessId;" ^
  "Get-Process cmd -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $callerCmd -and $_.MainWindowTitle -like 'PatiRota*' } | Stop-Process -Force -ErrorAction SilentlyContinue;" ^
  "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -like ('*' + $root + '*')) -and ($_.CommandLine -match 'main\.py|baslat\.bat|nicegui') } | Where-Object { $_.ProcessId -ne $callerCmd -and $_.ParentProcessId -ne $callerCmd } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue };" ^
  "Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

set CLEAN_PASS=0

:clean_ports_again
set FOUND=0
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    set FOUND=1
    echo   - PID %%p sonlandiriliyor...
    taskkill /PID %%p /F >nul 2>&1
)

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "TIME_WAIT CLOSE_WAIT"') do (
    taskkill /PID %%p /F >nul 2>&1
)

if "%FOUND%"=="1" (
    set /a CLEAN_PASS+=1
    echo   %CLEAN_PASS%. port temizlik turu, 2 sn bekleniyor...
    timeout /t 2 /nobreak >nul
    if %CLEAN_PASS% LSS 5 goto clean_ports_again
)

netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo.
    echo  UYARI: %PORT% portu hala dolu. Baska bir program kullaniyor olabilir.
    pause
    exit /b 1
)

echo   Port %PORT% hazir.
exit /b 0
