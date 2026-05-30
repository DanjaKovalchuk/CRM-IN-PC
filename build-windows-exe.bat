@echo off
cd /d "%~dp0"
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --name CRM-in-PC crm_desktop.py
if errorlevel 1 (
  echo.
  echo Збірка не вдалася. Перевірте Python, pip та доступ до інтернету для встановлення PyInstaller.
  pause
  exit /b 1
)
echo.
echo Готово: dist\CRM-in-PC.exe
pause
