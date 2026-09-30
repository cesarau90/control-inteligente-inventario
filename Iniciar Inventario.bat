@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_all.py
) else if exist "C:\Program Files\PostgreSQL\18\pgAdmin 4\python\python.exe" (
    "C:\Program Files\PostgreSQL\18\pgAdmin 4\python\python.exe" run_all.py
) else (
    echo No se encontro Python. Instala Python y sigue el README.md.
)
echo.
echo Pulsa una tecla para cerrar esta ventana.
pause >nul
