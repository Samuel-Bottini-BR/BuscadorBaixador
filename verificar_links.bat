@echo off
chcp 65001 >nul
echo Instalando dependencias (so na primeira vez)...
python -m pip install --quiet requests openpyxl
echo.
echo Verificando os links... isso leva alguns minutos.
python "%~dp0verificar_links.py" %*
echo.
pause
