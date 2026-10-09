@echo off
chcp 65001 >nul
echo Preparando o ambiente (so na primeira vez pode demorar um pouco)...
"%~dp0.venv\Scripts\python.exe" -m pip install -e "%~dp0." --quiet
echo.
echo Abrindo o aplicativo no navegador... (para fechar, feche esta janela)
"%~dp0.venv\Scripts\python.exe" -m streamlit run "%~dp0src\buscador\app\principal.py" --server.headless false --browser.gatherUsageStats false
pause
