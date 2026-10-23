"""Проверка обновлений через GitHub Releases; обновление - скачать VyzhivalkaSetup.exe и запустить с --update."""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser

from .config import SETUP_NAME, VERSION, github_repo


def parse_ver(v):
    nums = re.findall(r"\d+", v or "")
    return tuple(int(x) for x in nums[:3]) or (0,)


class Checker:
    """state: checking / latest / update / error / norepo / downloading / ready / failed"""

    def __init__(self):
        self.state = "checking"
        self.latest = ""
        self.url = ""
        self.asset = None
        self.error = ""
        self.progress = 0.0
        self.new_path = None
        self.recheck()

    def recheck(self):
        if self.state in ("downloading",):
            return
        if "--launcher" in sys.argv:
            self.state = "launcher"
            return
        self.state = "checking"
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        repo = github_repo()
        if "YOUR_GITHUB_NAME" in repo:
            self.state = "norepo"
            return
        self.url = "https://github.com/%s/releases" % repo
        try:
            req = urllib.request.Request("https://api.github.com/repos/%s/releases/latest" % repo,
                                         headers={"User-Agent": "Vyzhivalka-updater",
                                                  "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode("utf-8"))
            self.latest = data.get("tag_name", "")
            self.url = data.get("html_url") or self.url
            self.asset = None
            for a in data.get("assets", []):
                if a.get("name") == SETUP_NAME:
                    self.asset = a.get("browser_download_url")
                    break
            self.state = "update" if parse_ver(self.latest) > parse_ver(VERSION) else "latest"
        except urllib.error.HTTPError as e:
            self.state = "error"
            self.error = "в репозитории пока нет релизов" if e.code == 404 else "ошибка GitHub %d" % e.code
        except Exception:
            self.state = "error"
            self.error = "нет подключения к интернету"

    def status_text(self):
        return {
            "checking": "Проверка обновлений...",
            "launcher": "Запущено из лаунчера - он сам следит за обновлениями",
            "latest": "Установлена последняя версия",
            "update": "Доступна новая версия %s!" % self.latest,
            "error": "Не удалось проверить обновления: %s" % self.error,
            "norepo": "Обновления: укажите свой GitHub-репозиторий в config.py",
            "downloading": "Загрузка обновления... %d%%" % int(self.progress * 100),
            "ready": "Обновление загружено, перезапуск...",
            "failed": "Ошибка загрузки: %s" % self.error,
        }.get(self.state, "")

    def can_autoupdate(self):
        return bool(self.asset)

    def start_update(self):
        if not self.can_autoupdate():
            webbrowser.open(self.url)
            return
        self.state = "downloading"
        self.progress = 0.0
        threading.Thread(target=self._download, daemon=True).start()

    def _download(self):
        dst = os.path.join(tempfile.gettempdir(), SETUP_NAME)
        try:
            req = urllib.request.Request(self.asset, headers={"User-Agent": "Vyzhivalka-updater"})
            with urllib.request.urlopen(req, timeout=30) as r, open(dst, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        self.progress = done / total
            self.new_path = dst
            self.state = "ready"
        except Exception as e:
            self.error = str(e)[:80]
            self.state = "failed"

    def apply(self):
        """Запускает скачанный установщик в режиме обновления. Вызывающий должен закрыть игру."""
        flags = getattr(subprocess, "DETACHED_PROCESS", 0)
        subprocess.Popen([self.new_path, "--update"], close_fds=True, creationflags=flags)


def cleanup(argv):
    if "--cleanup" not in argv:
        return
    path = argv[argv.index("--cleanup") + 1]

    def run():
        for _ in range(40):
            try:
                if os.path.exists(path):
                    os.remove(path)
                return
            except OSError:
                time.sleep(0.5)

    threading.Thread(target=run, daemon=True).start()
