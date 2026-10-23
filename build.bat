@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Установка зависимостей ===
python -m pip install -r requirements.txt pyinstaller
echo === Иконка ===
python make_icon.py
echo === 1/3 Игра + лаунчер (Vyzhivalka.exe) ===
python -m PyInstaller --noconfirm --onefile --windowed --name Vyzhivalka --icon icon.ico main.py
echo === 2/3 Установщик (VyzhivalkaSetup.exe) - его загружаете в релиз ===
python -m PyInstaller --noconfirm --onefile --windowed --name VyzhivalkaSetup --icon icon.ico --exclude-module pygame --add-data "dist\Vyzhivalka.exe;payload" setup.py
echo === 3/3 Онлайн-установщик (VyzhivalkaOnline.exe) ===
python -m PyInstaller --noconfirm --onefile --windowed --name VyzhivalkaOnline --icon icon.ico --exclude-module pygame online.py
copy /y dist\VyzhivalkaOnline.exe VyzhivalkaOnline.exe >nul
echo === Папка для загрузки на GitHub ===
python make_upload.py
echo.
echo Готово! Всё для GitHub лежит в папке ЗАГРУЗИТЬ_НА_GITHUB:
echo   1_КОД   - перетащить в репозиторий
echo   2_РЕЛИЗ - один файл VyzhivalkaSetup.exe в Releases
explorer "ЗАГРУЗИТЬ_НА_GITHUB"
pause
