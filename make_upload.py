"""Собирает папку «ЗАГРУЗИТЬ_НА_GITHUB»: всё, что нужно загрузить, разложено по двум папкам."""
import os
import shutil

from game.config import VERSION

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "ЗАГРУЗИТЬ_НА_GITHUB")
CODE = os.path.join(OUT, "1_КОД - перетащить в репозиторий")
REL = os.path.join(OUT, "2_РЕЛИЗ - один файл в Releases")

FILES = ["main.py", "launcher.py", "setup.py", "online.py", "make_icon.py", "make_upload.py", "build.bat",
         "publish.bat", "requirements.txt", "README.md", "ГАЙД.md", ".gitignore", "VyzhivalkaOnline.exe"]

INFO = """ЧТО ЗАГРУЖАТЬ НА GITHUB  (версия {v})
==========================================

ПАПКА «1_КОД - перетащить в репозиторий»
  1. Откройте https://github.com/KIRILLTAN/vyzhivalka/upload/main
  2. Зайдите в эту папку, выделите ВСЁ (Ctrl+A) и перетащите в окно браузера.
  3. Дождитесь загрузки и нажмите зелёную кнопку «Commit changes».
  (Это нужно один раз и потом при каждом обновлении кода.)

ПАПКА «2_РЕЛИЗ - один файл в Releases»
  1. Откройте https://github.com/KIRILLTAN/vyzhivalka/releases/new
  2. Choose a tag -> впишите  v{v}  -> Create new tag.
  3. Release title:  Выживалка {v}
  4. В описании напишите, что нового (это увидят в лаунчере).
  5. Перетащите файл VyzhivalkaSetup.exe из этой папки.
  6. Publish release.

ССЫЛКА ДЛЯ ДРУЗЕЙ (всегда последняя версия):
  https://github.com/KIRILLTAN/vyzhivalka/raw/main/VyzhivalkaOnline.exe

Подробный гайд с нуля - файл ГАЙД.md.
Папку пересоздаёт build.bat при каждой сборке.
"""


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(CODE)
    os.makedirs(REL)
    missing = []
    for f in FILES:
        src = os.path.join(ROOT, f)
        if os.path.isfile(src):
            shutil.copy2(src, CODE)
        else:
            missing.append(f)
    shutil.copytree(os.path.join(ROOT, "game"), os.path.join(CODE, "game"),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    setup = os.path.join(ROOT, "dist", "VyzhivalkaSetup.exe")
    if os.path.isfile(setup):
        shutil.copy2(setup, REL)
    else:
        missing.append("dist\\VyzhivalkaSetup.exe")
    with open(os.path.join(OUT, "ЧТО ДЕЛАТЬ.txt"), "w", encoding="utf-8-sig") as fh:
        fh.write(INFO.format(v=VERSION))
    print("Папка готова:", OUT)
    if missing:
        print("Не найдены (сначала запустите build.bat):", ", ".join(missing))


if __name__ == "__main__":
    main()
