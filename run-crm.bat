@echo off
cd /d "%~dp0"
python crm_desktop.py
if errorlevel 1 (
  echo.
  echo Не вдалося запустити CRM. Перевірте, що Python 3 встановлено та додано в PATH.
  pause
)
