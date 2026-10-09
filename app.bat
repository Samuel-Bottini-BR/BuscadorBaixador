@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist logs mkdir logs
echo Atualizando o programa (baixando a versao mais nova do GitHub)...
echo ===== %date% %time% >> logs\atualizacao.log
git pull --ff-only >> logs\atualizacao.log 2>&1
if errorlevel 1 (echo   Nao consegui atualizar agora - sigo com a versao que ja esta no PC. Detalhes em logs\atualizacao.log) else (echo   Programa atualizado.)
echo Conferindo as bibliotecas (so na primeira vez demora)...
".venv\Scripts\python.exe" -m pip install -e . --quiet >> logs\instalacao.log 2>&1
if errorlevel 1 echo   Problema ao instalar bibliotecas - detalhes em logs\instalacao.log
echo.
echo Abrindo o aplicativo no navegador... (para fechar o app, feche esta janela)
".venv\Scripts\python.exe" -m streamlit run src\buscador\app\principal.py --server.headless false --browser.gatherUsageStats false 2>> logs\streamlit.log
pause
