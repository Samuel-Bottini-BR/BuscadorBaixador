@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist logs mkdir logs
echo Atualizando o programa (baixando a versao mais nova do GitHub)...
echo ===== %date% %time% >> logs\atualizacao.log
git pull --ff-only >> logs\atualizacao.log 2>&1
if errorlevel 1 (echo   Nao consegui atualizar agora - sigo com a versao que ja esta no PC. Detalhes em logs\atualizacao.log) else (echo   Programa atualizado.)
rem O resto fica em outro arquivo: este app.bat muda pouco, e o Windows le .bat aos
rem pedacos -- se ele mudasse no meio do git pull, poderia rodar comandos misturados.
call "%~dp0scripts\iniciar_app.bat"
