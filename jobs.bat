@echo off
chcp 65001 >nul
echo Preparando o ambiente (so na primeira vez pode demorar um pouco)...
rem O ponto depois de %~dp0 na linha do pip e de proposito: %~dp0 termina em barra
rem invertida e, sem o ponto, essa barra escaparia a aspa final e o pip receberia um
rem argumento quebrado (engolindo o --quiet).
"%~dp0.venv\Scripts\python.exe" -m pip install -e "%~dp0." --quiet
"%~dp0.venv\Scripts\python.exe" -m buscador.jobs_cli %*
echo.
pause
