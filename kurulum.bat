@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo PatiRota - ilk kurulum
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python database.py
echo.
echo Kurulum tamam. Simdi baslat.bat dosyasini calistirin.
pause
