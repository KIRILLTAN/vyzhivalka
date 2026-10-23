"""VyzhivalkaSetup.exe - установщик. Внутри лежит Vyzhivalka.exe (игра + лаунчер).
Ставит игру в %LOCALAPPDATA%\\Programs\\Vyzhivalka, делает ярлыки и запись для удаления.
Флаг --update: ставит без вопросов и сразу запускает (так обновляются игра и лаунчер)."""
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

from game import install
from game.config import EXE_NAME, TITLE, VERSION

BG, FG, ACC = "#1c1e24", "#e8e8e8", "#c8463a"


def payload():
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "payload", EXE_NAME)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", EXE_NAME)


class Setup:
    def __init__(self):
        self.update_mode = "--update" in sys.argv
        self.root = tk.Tk()
        self.root.title("Установка: %s %s" % (TITLE, VERSION))
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        w, h = 560, 330
        self.root.geometry("%dx%d+%d+%d" % (w, h, (self.root.winfo_screenwidth() - w) // 2,
                                            (self.root.winfo_screenheight() - h) // 2))
        tk.Label(self.root, text=TITLE.upper(), font=("Segoe UI", 30, "bold"), fg=ACC, bg=BG).pack(pady=(18, 0))
        tk.Label(self.root, text=("Обновление до версии %s" if self.update_mode else "Установка версии %s") % VERSION,
                 font=("Segoe UI", 12), fg=FG, bg=BG).pack()
        tk.Label(self.root, text="Папка: " + install.install_dir(), font=("Segoe UI", 9), fg="#9a9aa4",
                 bg=BG).pack(pady=(8, 6))
        self.desk = tk.BooleanVar(value=True)
        self.run_after = tk.BooleanVar(value=True)
        opts = tk.Frame(self.root, bg=BG)
        opts.pack()
        for text, var in (("Ярлык на рабочем столе", self.desk), ("Запустить после установки", self.run_after)):
            tk.Checkbutton(opts, text=text, variable=var, fg=FG, bg=BG, selectcolor="#2c2f38", activebackground=BG,
                           activeforeground=FG, font=("Segoe UI", 10)).pack(anchor="w")
        style = ttk.Style()
        style.theme_use("default")
        style.configure("g.Horizontal.TProgressbar", troughcolor="#2c2f38", background="#4caf50", thickness=14)
        self.bar = ttk.Progressbar(self.root, style="g.Horizontal.TProgressbar", length=480, maximum=1.0)
        self.bar.pack(pady=(14, 4))
        self.status = tk.Label(self.root, text="", font=("Segoe UI", 10), fg="#f0c860", bg=BG)
        self.status.pack()
        self.btn = tk.Button(self.root, text="Установить", font=("Segoe UI", 13, "bold"), bg="#2f7a3c", fg="white",
                             activebackground="#3a9149", relief="flat", width=18, command=self.start)
        self.btn.pack(pady=10)
        self._status, self._progress, self._done, self._error = "", 0.0, False, None
        if self.update_mode:
            self.root.after(300, self.start)
        self.root.after(100, self.poll)

    def start(self):
        if not os.path.isfile(payload()):
            self._error = "Внутри установщика нет файла игры"
            return
        self._error = None
        self.btn.config(state="disabled", text="Установка...")
        threading.Thread(target=self.work, daemon=True).start()

    def work(self):
        try:
            self.exe = install.install(payload(), self.desk.get(), self._set_status, self._set_progress)
            self._done = True
        except Exception as e:
            self._error = str(e)

    def _set_status(self, s):
        self._status = s

    def _set_progress(self, f):
        self._progress = f

    def poll(self):
        self.status.config(text=self._error or self._status, fg="#ff7a6a" if self._error else "#f0c860")
        self.bar["value"] = self._progress
        if self._error and str(self.btn["state"]) == "disabled":
            self.btn.config(state="normal", text="Повторить")
        if self._done:
            if self.run_after.get():
                subprocess.Popen([self.exe], cwd=os.path.dirname(self.exe), close_fds=True,
                                 creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
                self.root.after(600, self.root.destroy)
            else:
                self.btn.config(state="normal", text="Готово - закрыть", command=self.root.destroy)
            self._done = False
            return
        self.root.after(100, self.poll)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Setup().run()
