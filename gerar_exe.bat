@echo off
REM ============================================================
REM Script para gerar AutomacaoPedidos.exe
REM Requer: Python e pip instalados
REM ============================================================

echo.
echo ========================================================
echo  GERANDO EXECUTAVEL - AutomacaoPedidos.exe
echo ========================================================
echo.

REM 1. Instalar dependências
echo 1/3 Instalando dependências Python...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERRO: Falha ao instalar dependências
    pause
    exit /b 1
)

echo OK - Dependências instaladas
echo.

REM 2. Gerar executável
echo 2/3 Gerando executável com PyInstaller...
pyinstaller --onefile --windowed --name "AutomacaoPedidos" --distpath "." --build-temp-folder "build" app.py
if %errorlevel% neq 0 (
    echo ERRO: Falha ao gerar executável
    pause
    exit /b 1
)

echo OK - Executável gerado
echo.

REM 3. Limpeza
echo 3/3 Finalizando...
rmdir /s /q build dist
del AutomacaoPedidos.spec

echo.
echo ========================================================
echo  SUCESSO!
echo ========================================================
echo.
echo O arquivo "AutomacaoPedidos.exe" foi criado
echo Você pode agora distribuir o programa
echo.
echo Certifique-se de que estes arquivos estão presentes:
echo   - mapeamento_teknisa.xlsx
echo   - Relatorio potes.xlsx
echo   - README.txt
echo.
pause
