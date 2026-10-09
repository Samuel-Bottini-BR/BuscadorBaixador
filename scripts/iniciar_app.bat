@echo off
rem Chamado pelo app.bat depois de atualizar. Roda na raiz do projeto.
cd /d "%~dp0.."
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop'); $l=Join-Path $d 'Buscador e Baixador.lnk'; if (-not (Test-Path $l)) { $s=(New-Object -ComObject WScript.Shell).CreateShortcut($l); $s.TargetPath='%CD%\app.bat'; $s.WorkingDirectory='%CD%\'; $s.IconLocation='%CD%\assets\livro.ico'; $s.Description='Buscador e Baixador - Instituto Sao Bento'; $s.Save(); Write-Host '  Atalho com o livrinho criado na Area de Trabalho.' }" 2>> logs\atalho.log
echo Conferindo as bibliotecas (so na primeira vez demora)...
".venv\Scripts\python.exe" -m pip install -e . --quiet >> logs\instalacao.log 2>&1
if errorlevel 1 echo   Problema ao instalar bibliotecas - detalhes em logs\instalacao.log
echo.
echo Abrindo o aplicativo no navegador... (para fechar o app, feche esta janela)
".venv\Scripts\python.exe" -m streamlit run src\buscador\app\principal.py --server.headless false --browser.gatherUsageStats false 2>> logs\streamlit.log
pause
