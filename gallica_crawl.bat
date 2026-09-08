@echo off
chcp 65001 >nul
echo Preparando o ambiente (so na primeira vez pode demorar um pouco)...
"%~dp0.venv\Scripts\python.exe" -m pip install -e "%~dp0" --quiet
echo.
echo Coletando a Gallica inteira (Etapa 1)... isso leva MUITAS horas.
echo Pode fechar essa janela a qualquer momento -- rodar de novo continua de onde parou.
"%~dp0.venv\Scripts\python.exe" -m buscador.gallica_crawl %*
echo.
pause
