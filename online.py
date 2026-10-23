"""VyzhivalkaOnline.exe - онлайн-установщик. Берёт с GitHub последний VyzhivalkaSetup.exe и запускает его.
Его не нужно обновлять: он всегда качает самую новую версию."""
import json
import os
import subprocess
import tempfile
import threading
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser
from tkinter import ttk

from game.config import SETUP_NAME, TITLE, github_repo

BG, FG, ACC = "#1c1e24", "#e8e8e8", "#c8463a"
UA = {"User-Agent": "Vyzhivalka-online-installer"}


class Online:
    def __init__(self):
        self.repo = github_repo()
        self.root = tk.Tk()
        self.root.title("%s - онлайн-установщик" % TITLE)
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        w, h = 520, 270
        self.root.geometry("%dx%d+%d+%d" % (w, h, (self.root.winfo_screenwidth() - w) // 2,
                                            (self.root.winfo_screenheight() - h) // 2))
        tk.Label(self.root, text=TITLE.upper(), font=("Segoe UI", 28, "bold"), fg=ACC, bg=BG).pack(pady=(18, 0))
        tk.Label(self.root, text="онлайн-установщик", font=("Segoe UI", 11), fg="#b8b0b0", bg=BG).pack()
        style = ttk.Style()
        style.theme_use("default")
        style.configure("g.Horizontal.TProgressbar", troughcolor="#2c2f38", background="#4caf50", thickness=14)
        self.bar = ttk.Progressbar(self.root, style="g.Horizontal.TProgressbar", length=440, maximum=1.0)
        self.bar.pack(pady=(22, 6))
        self.status = tk.Label(self.root, text="", font=("Segoe UI", 10), fg="#f0c860", bg=BG, wraplength=480)
        self.status.pack()
        row = tk.Frame(self.root, bg=BG)
        row.pack(pady=12)
        self.retry = tk.Button(row, text="Повторить", font=("Segoe UI", 11), bg="#2f7a3c", fg="white", relief="flat",
                               width=14, command=self.start)
        self.page = tk.Button(row, text="Открыть GitHub", font=("Segoe UI", 11), bg="#3a3f4a", fg="white",
                              relief="flat", width=14,
                              command=lambda: webbrowser.open("https://github.com/%s/releases" % self.repo))
        self._status, self._progress, self._state, self._path = "", 0.0, "", None
        self.root.after(200, self.start)
        self.root.after(100, self.poll)

    def start(self):
        self.retry.pack_forget()
        self.page.pack_forget()
        self._state = "work"
        threading.Thread(target=self.work, daemon=True).start()

    def work(self):
        try:
            self._status, self._progress = "Ищу последнюю версию на GitHub...", 0.0
            req = urllib.request.Request("https://api.github.com/repos/%s/releases/latest" % self.repo,
                                         headers=dict(UA, Accept="application/vnd.github+json"))
            with urllib.request.urlopen(req, timeout=15) as r:
                rel = json.loads(r.read().decode("utf-8"))
            asset = next((a for a in rel.get("assets", []) if a.get("name") == SETUP_NAME), None)
            if not asset:
                raise RuntimeError("В последнем релизе нет файла %s" % SETUP_NAME)
            tag = rel.get("tag_name", "")
            path = os.path.join(tempfile.gettempdir(), SETUP_NAME)
            req = urllib.request.Request(asset["browser_download_url"], headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r, open(path + ".part", "wb") as f:
                total = int(r.headers.get("Content-Length") or asset.get("size") or 0)
                done = 0
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        self._progress = done / total
                        self._status = "Скачиваю %s: %.1f / %.1f МБ" % (tag, done / 1048576, total / 1048576)
            os.replace(path + ".part", path)
            self._path = path
            self._status, self._progress, self._state = "Запускаю установщик...", 1.0, "done"
        except urllib.error.HTTPError as e:
            self._status = ("Релизов пока нет (репозиторий %s)" % self.repo) if e.code == 404 else \
                "Ошибка GitHub: %d" % e.code
            self._state = "error"
        except Exception as e:
            self._status = "Ошибка: %s" % (str(e)[:120] or "нет подключения к интернету")
            self._state = "error"

    def poll(self):
        self.status.config(text=self._status, fg="#ff7a6a" if self._state == "error" else "#f0c860")
        self.bar["value"] = self._progress
        if self._state == "error":
            self.retry.pack(side="left", padx=6)
            self.page.pack(side="left", padx=6)
            self._state = "shown"
        elif self._state == "done":
            subprocess.Popen([self._path], close_fds=True, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
            self.root.after(700, self.root.destroy)
            return
        self.root.after(100, self.poll)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Online().run()
