"""Лаунчер «Выживалки» (открывается при запуске Vyzhivalka.exe): новости с GitHub, ник, кнопка «Играть».
Обновление: скачивает последний VyzhivalkaSetup.exe из релиза и запускает его с --update."""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import webbrowser

import pygame

from game import ui
from game.app import make_icon
from game.config import SETUP_NAME, VERSION, github_repo, load_prefs, save_prefs
from game.updater import parse_ver

W, H = 900, 560
DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0)


def here():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def game_cmd():
    if getattr(sys, "frozen", False):
        return [sys.executable, "--game", "--launcher"]
    return [sys.executable, os.path.join(here(), "main.py"), "--launcher"]


def _clean_md(text):
    text = re.sub(r"[#*`>]+", "", text or "")
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.replace("\r", "")


class Releases:
    """Фоновая загрузка списка релизов с GitHub."""

    def __init__(self):
        self.state = "loading"
        self.error = ""
        self.latest = ""
        self.asset = None
        self.size = 0
        self.url = ""
        self.news = []
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        repo = github_repo()
        self.url = "https://github.com/%s/releases" % repo
        try:
            req = urllib.request.Request("https://api.github.com/repos/%s/releases?per_page=6" % repo,
                                         headers={"User-Agent": "Vyzhivalka-launcher",
                                                  "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            self.state, self.error = "error", ("репозиторий не найден" if e.code == 404 else "GitHub %d" % e.code)
            return
        except Exception:
            self.state, self.error = "error", "нет подключения к интернету"
            return
        rels = [r for r in data if not r.get("draft") and not r.get("prerelease")]
        for r in rels:
            self.news.append((r.get("tag_name", ""), r.get("name") or r.get("tag_name", ""),
                              (r.get("published_at") or "")[:10], _clean_md(r.get("body"))))
        if rels:
            top = rels[0]
            self.latest = top.get("tag_name", "")
            for a in top.get("assets", []):
                if a.get("name") == SETUP_NAME:
                    self.asset, self.size = a.get("browser_download_url"), a.get("size", 0)
        self.state = "ok" if rels else "empty"


class Launcher:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Выживалка - лаунчер")
        pygame.display.set_icon(make_icon())
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.prefs = load_prefs()
        self.nick = ui.TextInput((570, 158, 300, 40), self.prefs.get("name", ""), 16, "Ваш ник", 22)
        self.close_after = self.prefs.get("launcher_close", True)
        self.rel = Releases()
        self.dl = None          # None / "run" / "done" / "error"
        self.progress = 0.0
        self.msg = ""
        self.scroll = 0
        self.running = True
        self.t = 0.0
        self.bg = self._make_bg()

    @staticmethod
    def _make_bg():
        s = pygame.Surface((W, H))
        for y in range(H):
            k = y / H
            s.fill((int(34 - 18 * k), int(18 + 4 * k), int(22 + 2 * k)), (0, y, W, 1))
        x = 0
        import random
        rnd = random.Random(7)
        while x < W:
            w, h = rnd.randint(40, 110), rnd.randint(80, 220)
            pygame.draw.rect(s, (14, 12, 16), (x, H - h, w, h))
            for wy in range(H - h + 10, H - 8, 22):
                for wx in range(x + 6, x + w - 10, 16):
                    if rnd.random() < 0.12:
                        pygame.draw.rect(s, (150, 120, 60), (wx, wy, 7, 9))
            x += w + rnd.randint(0, 16)
        return s

    # --- действия ---
    def need_update(self):
        return bool(self.rel.asset) and parse_ver(self.rel.latest) > parse_ver(VERSION)

    def main_action(self):
        if self.dl == "run":
            return
        if self.need_update():
            self.dl = "run"
            self.progress = 0.0
            threading.Thread(target=self._download, daemon=True).start()
        else:
            self.play()

    def _download(self):
        """Качает последний установщик и запускает его в режиме обновления; лаунчер закрывается."""
        dst = os.path.join(tempfile.gettempdir(), SETUP_NAME)
        try:
            req = urllib.request.Request(self.rel.asset, headers={"User-Agent": "Vyzhivalka-launcher"})
            with urllib.request.urlopen(req, timeout=30) as r, open(dst + ".part", "wb") as f:
                total = int(r.headers.get("Content-Length") or self.rel.size or 0)
                done = 0
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        self.progress = done / total
            os.replace(dst + ".part", dst)
            self.save()
            subprocess.Popen([dst, "--update"], close_fds=True, creationflags=DETACHED)
            self.msg = "Устанавливается %s..." % self.rel.latest
            self.dl = "done"
            self.running = False
        except Exception as e:
            self.msg = "Ошибка загрузки: %s" % str(e)[:60]
            self.dl = "error"

    def save(self):
        self.prefs = load_prefs()
        if self.nick.value.strip():
            self.prefs["name"] = self.nick.value.strip()
        self.prefs["launcher_close"] = self.close_after
        save_prefs(self.prefs)

    def play(self):
        if not self.nick.value.strip():
            self.msg = "Введите ник"
            self.nick.active = True
            return
        self.save()
        subprocess.Popen(game_cmd(), cwd=here(), close_fds=True, creationflags=DETACHED)
        self.msg = "Игра запускается..."
        if self.close_after:
            self.running = False

    def open_folder(self):
        try:
            os.startfile(here())
        except Exception:
            pass

    # --- интерфейс ---
    def main_label(self):
        if self.dl == "run":
            return "Загрузка %d%%" % int(self.progress * 100)
        if self.need_update():
            return "ОБНОВИТЬ"
        return "ИГРАТЬ"

    def buttons(self):
        return [
            (pygame.Rect(570, 300, 300, 70), self.main_label(), self.main_action, (50, 120, 60), 32),
            (pygame.Rect(570, 420, 145, 40), "Папка игры", self.open_folder, (55, 60, 70), 17),
            (pygame.Rect(725, 420, 145, 40), "GitHub", lambda: webbrowser.open(self.rel.url or
                                                                                "https://github.com/" + github_repo()),
             (55, 60, 70), 17),
            (pygame.Rect(570, 470, 300, 40), "Выход", self.quit, (90, 40, 40), 17),
        ]

    def quit(self):
        self.save()
        self.running = False

    def handle(self, e):
        if e.type == pygame.QUIT:
            self.quit()
            return
        if self.nick.handle(e):
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN:
            self.main_action()
        if e.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, self.scroll - e.y * 30)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for r, label, fn, col, size in self.buttons():
                if r.collidepoint(e.pos):
                    fn()
                    return
            if pygame.Rect(570, 385, 300, 26).collidepoint(e.pos):
                self.close_after = not self.close_after

    def _wrap(self, text, width, size):
        lines = []
        for para in text.split("\n"):
            words = para.split()
            if not words:
                lines.append("")
                continue
            line = ""
            for w in words:
                test = (line + " " + w).strip()
                if ui.render(test, size).get_width() > width:
                    lines.append(line)
                    line = w
                else:
                    line = test
            lines.append(line)
        return lines

    def draw_news(self, s):
        box = pygame.Rect(30, 130, 510, 400)
        ui.panel(s, box, alpha=225)
        ui.text(s, "Новости и обновления", (box.x + 16, box.y + 10), 22, (255, 220, 150), bold=True)
        clip = pygame.Rect(box.x + 10, box.y + 46, box.w - 20, box.h - 56)
        s.set_clip(clip)
        y = clip.y - self.scroll
        if self.rel.state == "loading":
            ui.text(s, "Загрузка новостей...", (clip.x + 6, y), 17, (190, 190, 190))
        elif self.rel.state == "error":
            ui.text(s, "Не удалось загрузить: %s" % self.rel.error, (clip.x + 6, y), 17, (240, 150, 100))
            y += 28
            for line in self._wrap("Можно играть в уже установленную версию. Когда появится интернет и релиз на "
                                   "GitHub, лаунчер сам предложит обновиться.", clip.w - 12, 16):
                ui.text(s, line, (clip.x + 6, y), 16, (190, 190, 190))
                y += 22
        elif not self.rel.news:
            ui.text(s, "Пока нет ни одного релиза", (clip.x + 6, y), 17, (190, 190, 190))
        for tag, name, date, body in self.rel.news:
            ui.text(s, name, (clip.x + 6, y), 20, (255, 255, 255), bold=True)
            ui.text(s, date, (clip.right - 6, y + 4), 14, (160, 160, 160), right=True)
            y += 30
            for line in self._wrap(body or "Без описания", clip.w - 12, 16):
                ui.text(s, line, (clip.x + 6, y), 16, (205, 205, 210))
                y += 21
            y += 14
        total = y + self.scroll - clip.y
        self.scroll = min(self.scroll, max(0, total - clip.h))
        s.set_clip(None)

    def draw(self):
        s = self.screen
        s.blit(self.bg, (0, 0))
        ui.text(s, "ВЫЖИВАЛКА", (W // 2, 50), 56, (230, 70, 55), bold=True, center=True)
        ui.text(s, "лаунчер", (W // 2, 92), 18, (200, 190, 190), center=True)
        self.draw_news(s)
        ui.panel(s, (555, 130, 330, 400), alpha=225)
        ui.text(s, "Ник:", (570, 125 + 6), 17, (200, 200, 200))
        ui.text(s, "Установлена: v%s" % VERSION, (570, 208), 16)
        latest = self.rel.latest or {"loading": "проверка...", "error": "нет связи", "empty": "нет релизов"}.get(
            self.rel.state, "-")
        ui.text(s, "На GitHub: %s" % latest, (570, 230), 16)
        if self.need_update() and self.dl != "run":
            ui.text(s, "Доступно обновление!", (570, 256), 17, (120, 230, 120), bold=True)
        if self.msg:
            ui.text(s, self.msg, (720, 278), 15, (255, 210, 120), center=True)
        for r, label, fn, col, size in self.buttons():
            ui.Button(r, label, size=size, color=col).draw(s)
        if self.dl == "run":
            ui.bar(s, (570, 374, 300, 8), self.progress, (90, 200, 110))
        box = pygame.Rect(572, 389, 18, 18)
        pygame.draw.rect(s, (20, 22, 26), box, border_radius=3)
        pygame.draw.rect(s, (120, 120, 130), box, 2, border_radius=3)
        if self.close_after:
            pygame.draw.line(s, (120, 230, 120), (575, 398), (580, 403), 3)
            pygame.draw.line(s, (120, 230, 120), (580, 403), (587, 392), 3)
        ui.text(s, "Закрыть лаунчер после запуска", (598, 388), 15, (200, 200, 200))
        ui.text(s, "v%s  |  github.com/%s" % (VERSION, github_repo()), (W // 2, H - 18), 13,
                (140, 140, 150), center=True)

    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self.t += dt
            for e in pygame.event.get():
                self.handle(e)
            if not self.running:
                break
            self.draw()
            self.nick.draw(self.screen, dt)
            pygame.display.flip()
        pygame.quit()


if __name__ == "__main__":
    Launcher().run()
