@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo   Calculadora HCM 2010 - Intersecciones semaforizadas
echo ============================================================

if not exist ".venv\" (
    echo Creando entorno virtual .venv ...
    py -m venv .venv
)

call ".venv\Scripts\activate.bat"

echo Instalando/actualizando dependencias ...
pip install -r requirements.txt

echo.
echo Iniciando la aplicacion. Se abrira en el navegador.
echo Para cerrarla: pulsa Ctrl+C en esta ventana.
echo.
streamlit run app.py

pause
