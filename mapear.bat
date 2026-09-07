@echo off
chcp 65001 >nul
echo Preparando o ambiente (so na primeira vez pode demorar um pouco)...
"%~dp0.venv\Scripts\python.exe" -m pip install -e "%~dp0" --quiet
echo.
echo Mapeando o site... isso pode levar alguns minutos.
"%~dp0.venv\Scripts\python.exe" -m buscador.cli %*
echo.
pause
