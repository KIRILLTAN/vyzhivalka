"""Установка и удаление игры: папка, ярлыки, запись в «Программы и компоненты».
Только стандартная библиотека - используется и установщиком, и самой игрой."""
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time

from .config import EXE_NAME, VERSION, TITLE

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Vyzhivalka"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0)


def install_dir():
    base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Programs", "Vyzhivalka")


def installed_exe():
    return os.path.join(install_dir(), EXE_NAME)


def _ps(script, env_extra):
    env = dict(os.environ)
    env.update(env_extra)
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], env=env,
                       creationflags=NO_WINDOW, timeout=40, capture_output=True)
    except Exception:
        pass


_SHORTCUTS = r"""
$sh = New-Object -ComObject WScript.Shell
$places = @([Environment]::GetFolderPath('Programs'))
if ($env:VZ_DESK -eq '1') { $places += [Environment]::GetFolderPath('Desktop') }
foreach ($p in $places) {
  $s = $sh.CreateShortcut((Join-Path $p ($env:VZ_NAME + '.lnk')))
  $s.TargetPath = $env:VZ_TGT
  $s.WorkingDirectory = $env:VZ_DIR
  $s.IconLocation = $env:VZ_TGT + ',0'
  $s.Description = $env:VZ_NAME
  $s.Save()
}
"""
_REMOVE_SHORTCUTS = r"""
foreach ($p in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) {
  $f = Join-Path $p ($env:VZ_NAME + '.lnk')
  if (Test-Path -LiteralPath $f) { Remove-Item -LiteralPath $f -Force }
}
"""


def make_shortcuts(exe, desktop=True):
    _ps(_SHORTCUTS, {"VZ_TGT": exe, "VZ_DIR": os.path.dirname(exe), "VZ_NAME": TITLE, "VZ_DESK": "1" if desktop else "0"})


def register(exe):
    try:
        import winreg
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY)
        for name, val in (("DisplayName", TITLE), ("DisplayVersion", VERSION), ("Publisher", "KIRILLTAN"),
                          ("InstallLocation", os.path.dirname(exe)), ("DisplayIcon", exe),
                          ("UninstallString", '"%s" --uninstall' % exe)):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(k)
    except Exception:
        pass


def install(src, desktop=True, status=None, progress=None):
    """Копирует exe игры в папку установки (ждёт, если игра запущена), делает ярлыки и запись в реестре."""
    status = status or (lambda s: None)
    progress = progress or (lambda f: None)
    d = install_dir()
    os.makedirs(d, exist_ok=True)
    dst = installed_exe()
    tmp = dst + ".new"
    total = os.path.getsize(src)
    done = 0
    status("Копирование файлов...")
    with open(src, "rb") as fi, open(tmp, "wb") as fo:
        while True:
            chunk = fi.read(1 << 20)
            if not chunk:
                break
            fo.write(chunk)
            done += len(chunk)
            progress(0.85 * done / total)
    for i in range(120):
        try:
            os.replace(tmp, dst)
            break
        except PermissionError:
            status("Закройте игру - установка продолжится сама...")
            time.sleep(0.5)
    else:
        raise RuntimeError("Не удалось заменить файл игры - закройте игру и запустите установку снова")
    status("Создание ярлыков...")
    progress(0.9)
    make_shortcuts(dst, desktop)
    register(dst)
    progress(1.0)
    status("Готово!")
    return dst


def _ask(text):
    return ctypes.windll.user32.MessageBoxW(0, text, TITLE, 0x04 | 0x20) == 6


def _info(text):
    ctypes.windll.user32.MessageBoxW(0, text, TITLE, 0x40)


def uninstall(argv):
    """--uninstall: копирует себя во временную папку и удаляет игру оттуда (свой exe удалить нельзя)."""
    if "--uninstall-run" not in argv:
        if not _ask("Удалить %s с компьютера?\n\nСохранения миров останутся в %%APPDATA%%\\Vyzhivalka." % TITLE):
            return
        tmp = os.path.join(tempfile.gettempdir(), "vyzhivalka_uninstall.exe")
        try:
            shutil.copy2(sys.executable, tmp)
            subprocess.Popen([tmp, "--uninstall", "--uninstall-run"], close_fds=True, creationflags=DETACHED)
            return
        except OSError:
            pass
    time.sleep(1.5)
    for _ in range(2):  # OneDrive иногда держит рабочий стол - пробуем дважды
        _ps(_REMOVE_SHORTCUTS, {"VZ_NAME": TITLE})
        time.sleep(0.5)
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_KEY)
    except Exception:
        pass
    for _ in range(20):
        try:
            shutil.rmtree(install_dir())
            break
        except FileNotFoundError:
            break
        except OSError:
            time.sleep(0.5)
    _info("%s удалена." % TITLE)
