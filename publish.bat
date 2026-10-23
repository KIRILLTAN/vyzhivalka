@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Загрузка кода игры на GitHub: https://github.com/KIRILLTAN/vyzhivalka ===
echo.
where git >nul 2>nul
if errorlevel 1 (
    echo Git не установлен. Скачайте: https://git-scm.com/download/win
    pause
    exit /b 1
)
for /f "delims=" %%i in ('git config --global user.name') do set GN=%%i
if "%GN%"=="" git config --global user.name "KIRILLTAN"
for /f "delims=" %%i in ('git config --global user.email') do set GE=%%i
if "%GE%"=="" (
    set /p GE=Введите email от GitHub:
    call git config --global user.email "%%GE%%"
)
if not exist ".git" (
    git init
    git branch -M main
    git remote add origin https://github.com/KIRILLTAN/vyzhivalka.git
)
git add .
git commit -m "Выживалка %date% %time%"
git push -u origin main
echo.
echo Готово! Теперь создайте релиз: https://github.com/KIRILLTAN/vyzhivalka/releases/new
echo и прикрепите ОДИН файл: dist\VyzhivalkaSetup.exe
pause
