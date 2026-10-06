@echo off
chcp 65001 >nul
mode con: cols=120 lines=60
echo ============================================================
echo  Login proprio do tdl por QR code
echo.
echo  No CELULAR: Telegram ^> Configuracoes ^> Dispositivos ^>
echo  "Conectar dispositivo" (ou "Vincular dispositivo de desktop")
echo  e aponte a camera para o QR code que vai aparecer abaixo.
echo.
echo  Se o Telegram pedir a sua senha de verificacao em duas etapas,
echo  digite aqui nesta janela e aperte ENTER (ela nao aparece
echo  enquanto voce digita - e normal).
echo ============================================================
echo.
"D:\programas\ferramentas\tdl\tdl.exe" login -T qr
echo.
if errorlevel 1 (
  echo === DEU ERRO - tire um print desta janela e mande ao Claude ===
) else (
  echo === PRONTO: pode fechar esta janela e voltar ao Claude ===
)
pause
