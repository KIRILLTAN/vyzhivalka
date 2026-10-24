"""Главное меню, выбор сложности, создание/поиск комнаты, лобби."""
import math
import random
import time

import pygame

from . import saves, ui
from .config import (SCREEN_W, SCREEN_H, VERSION, TITLE, PORT, DIFF_ORDER, DIFFICULTIES, MP_OPTIONS,
                     default_settings, load_prefs, save_prefs)
from .net import NetClient, code_to_ip, net_label
from .session import HostSession, LocalLink, HOST_ID

CX = SCREEN_W // 2
_bg = None


def _background():
    global _bg
    if _bg is None:
        s = pygame.Surface((SCREEN_W, SCREEN_H))
        for y in range(SCREEN_H):
            k = y / SCREEN_H
            s.fill((int(35 - 20 * k), int(18 + 4 * k), int(22 + 2 * k)), (0, y, SCREEN_W, 1))
        rnd = random.Random(3)
        x = 0
        while x < SCREEN_W:
            w = rnd.randint(50, 130)
            h = rnd.randint(120, 330)
            pygame.draw.rect(s, (14, 12, 16), (x, SCREEN_H - h, w, h))
            for wy in range(SCREEN_H - h + 12, SCREEN_H - 10, 24):
                for wx in range(x + 8, x + w - 12, 18):
                    if rnd.random() < 0.12:
                        pygame.draw.rect(s, (150, 120, 60), (wx, wy, 8, 10))
            x += w + rnd.randint(0, 20)
        pygame.draw.circle(s, (170, 60, 50), (1040, 140), 60)
        pygame.draw.circle(s, (120, 40, 40), (1040, 140), 60, 4)
        _bg = s
    return _bg


class MenuBase:
    def __init__(self, app):
        self.app = app
        self.buttons = []
        self.t = 0.0
        self.ash = [[random.uniform(0, SCREEN_W), random.uniform(0, SCREEN_H), random.uniform(10, 30)]
                    for _ in range(70)]

    def handle(self, e):
        for b in self.buttons:
            if b.handle(e):
                return True
        return False

    def update(self, dt):
        self.t += dt
        for a in self.ash:
            a[1] += a[2] * dt
            a[0] += math.sin(self.t + a[2]) * 8 * dt
            if a[1] > SCREEN_H:
                a[1] = -5
                a[0] = random.uniform(0, SCREEN_W)

    def draw_bg(self, screen, title=None):
        screen.blit(_background(), (0, 0))
        for x, y, s in self.ash:
            pygame.draw.circle(screen, (120, 110, 110), (int(x), int(y)), 1 if s < 20 else 2)
        if title:
            ui.text(screen, title, (CX, 70), 46, (230, 70, 55), bold=True, center=True)

    def draw(self, screen):
        self.draw_bg(screen)
        for b in self.buttons:
            b.draw(screen)


class MainMenu(MenuBase):
    def __init__(self, app):
        super().__init__(app)
        self.name = ui.TextInput((CX - 180, 230, 360, 50), load_prefs().get("name", ""), 16, "Введите ник")
        self.err = ""
        y = 310
        self.buttons = [
            ui.Button((CX - 180, y, 360, 56), "Одиночная игра", lambda: self._go("single")),
            ui.Button((CX - 180, y + 70, 360, 56), "Мультиплеер", lambda: self._go("multi")),
            ui.Button((CX - 180, y + 140, 360, 56), "Управление", lambda: setattr(app, "show_help", True)),
            ui.Button((CX - 180, y + 210, 360, 56), "Выход", app.quit, color=(90, 40, 40)),
        ]
        self.upd_btn = ui.Button((24, SCREEN_H - 100, 260, 40), "Обновить", self._update, size=20,
                                 color=(50, 110, 60))
        self.recheck_btn = ui.Button((24, SCREEN_H - 100, 260, 40), "Проверить снова",
                                     self.app.updater.recheck, size=18)

    def nick(self):
        n = self.name.value.strip()
        if not n:
            return None
        p = load_prefs()
        p["name"] = n
        save_prefs(p)
        return n

    def _go(self, mode):
        n = self.nick()
        if not n:
            self.err = "Сначала введите ник"
            self.name.active = True
            return
        if mode == "single":
            self.app.switch(DifficultyMenu(self.app, n))
        else:
            self.app.switch(MultiMenu(self.app, n))

    def _update(self):
        self.app.updater.start_update()

    def handle(self, e):
        if self.name.handle(e):
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN:
            self._go("single")
            return
        st = self.app.updater.state
        if st == "update" and self.upd_btn.handle(e):
            return
        if st in ("error", "failed") and self.recheck_btn.handle(e):
            return
        super().handle(e)

    def update(self, dt):
        super().update(dt)
        up = self.app.updater
        if up.state == "ready":
            up.apply()
            self.app.quit()

    def draw(self, screen):
        self.draw_bg(screen)
        ui.text(screen, TITLE.upper(), (CX, 110), 84, (230, 70, 55), bold=True, center=True)
        ui.text(screen, "зомби-выживание с друзьями", (CX, 168), 22, (200, 190, 190), center=True)
        ui.text(screen, "Ваш ник:", (CX - 180, 204), 18, (200, 200, 200))
        self.name.draw(screen)
        if self.err:
            ui.text(screen, self.err, (CX + 190, 245), 18, (255, 110, 90))
        for b in self.buttons:
            b.draw(screen)
        up = self.app.updater
        col = {"update": (120, 230, 120), "error": (230, 150, 100), "failed": (230, 120, 100)}.get(
            up.state, (190, 190, 190))
        ui.panel(screen, (14, SCREEN_H - 150, 520, 136))
        ui.text(screen, "Версия %s" % VERSION, (24, SCREEN_H - 142), 18, bold=True)
        ui.text(screen, up.status_text(), (24, SCREEN_H - 120), 16, col)
        if up.state == "update":
            self.upd_btn.label = "Обновить до %s" % up.latest if up.can_autoupdate() else "Открыть страницу загрузки"
            self.upd_btn.draw(screen)
        elif up.state in ("error", "failed"):
            self.recheck_btn.draw(screen)
        elif up.state == "downloading":
            ui.bar(screen, (24, SCREEN_H - 90, 260, 18), up.progress, (90, 200, 110))


class DifficultyMenu(MenuBase):
    def __init__(self, app, name):
        super().__init__(app)
        self.name = name
        self.sel = "normal"
        self.buttons = [
            ui.Button((CX - 290, 385, 280, 50), "Новая игра", self._start, color=(50, 110, 60)),
            ui.Button((CX + 10, 385, 280, 50), "Назад", lambda: app.switch(MainMenu(app))),
        ]
        self.saves = saves.list_saves()
        self.save_zones = []
        prefs = load_prefs()
        self.respawn = prefs.get("sp_respawn", False)
        self.keep_inv = prefs.get("sp_keep_inv", False)
        self.buttons += [
            ui.Button((70, 385, 270, 50), "", lambda: self._toggle("respawn"), size=19),
            ui.Button((940, 385, 270, 50), "", lambda: self._toggle("keep_inv"), size=19),
        ]
        self._labels()

    def _labels(self):
        self.buttons[2].label = "Возрождение: %s" % ("ВКЛ" if self.respawn else "ВЫКЛ")
        self.buttons[2].color = (50, 100, 60) if self.respawn else (90, 50, 45)
        self.buttons[3].label = "Сохранять вещи: %s" % ("ВКЛ" if self.keep_inv else "ВЫКЛ")
        self.buttons[3].color = (50, 100, 60) if self.keep_inv else (90, 50, 45)

    def _toggle(self, key):
        setattr(self, key, not getattr(self, key))
        p = load_prefs()
        p["sp_" + key] = getattr(self, key)
        save_prefs(p)
        self._labels()

    def cards(self):
        out = []
        for i, k in enumerate(DIFF_ORDER):
            out.append((pygame.Rect(70 + i * 290, 110, 270, 260), k))
        return out

    def handle(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for r, k in self.cards():
                if r.collidepoint(e.pos):
                    self.sel = k
                    return
            for r, fn in self.save_zones:
                if r.collidepoint(e.pos):
                    fn()
                    return
        super().handle(e)

    def _start(self, slot=None):
        app, diff = self.app, self.sel
        try:
            settings = None
            if not slot:
                settings = default_settings(False)
                settings.update(respawn=self.respawn, keep_inv=self.keep_inv)
            host = HostSession(self.name, diff, settings, multiplayer=False, save_slot=slot)
        except (OSError, ValueError, KeyError) as ex:
            app.switch(MessageScene(app, "Не удалось загрузить сохранение: %s" % ex))
            return

        def make():
            from .play import GameScene
            host.start()
            return GameScene(app, LocalLink(host), HOST_ID, host.seed, host.diff, host.settings, host=host,
                             world=host.sim.world)

        app.switch(LoadingScene(app, "Загрузка мира..." if slot else "Генерация мира...", make))

    def _delete(self, slot):
        saves.delete(slot)
        self.saves = saves.list_saves()

    def draw(self, screen):
        self.draw_bg(screen)
        ui.text(screen, "Одиночная игра", (CX, 50), 40, (230, 70, 55), bold=True, center=True)
        ui.text(screen, "Эти настройки можно менять и в игре (Esc)", (CX, 88), 15, (170, 170, 170), center=True)
        self.save_zones = []
        ui.panel(screen, (70, 450, 1140, 255))
        ui.text(screen, "Сохранения", (90, 458), 22, bold=True)
        if not self.saves:
            ui.text(screen, "Пока нет сохранений. Игра сохраняется автоматически и при выходе в меню.", (90, 500),
                    17, (170, 170, 170))
        for i, m in enumerate(self.saves[:5]):
            y = 492 + i * 42
            date = time.strftime("%d.%m %H:%M", time.localtime(m.get("time", 0)))
            info = "%s  -  день %d, %s, %s%s" % (m["name"], m.get("day", 1),
                                                   DIFFICULTIES.get(m.get("diff"), {}).get("name", "?"), date,
                                                   "  (мультиплеер)" if m.get("mp") else "")
            ui.text(screen, info, (90, y + 6), 18)
            if m.get("version") != VERSION:
                ui.text(screen, "старая версия", (720, y + 8), 14, (230, 160, 90))
            b1 = pygame.Rect(860, y, 170, 34)
            ui.Button(b1, "Продолжить", size=18, color=(50, 110, 60)).draw(screen)
            self.save_zones.append((b1, lambda s=m["slot"]: self._start(s)))
            b2 = pygame.Rect(1040, y, 150, 34)
            ui.Button(b2, "Удалить", size=18, color=(110, 50, 45)).draw(screen)
            self.save_zones.append((b2, lambda s=m["slot"]: self._delete(s)))
        cols = {"easy": (70, 150, 80), "normal": (180, 160, 60), "hard": (200, 110, 50), "hardcore": (190, 40, 40)}
        for r, k in self.cards():
            d = DIFFICULTIES[k]
            sel = k == self.sel
            ui.panel(screen, r, (45, 40, 44) if sel else (25, 25, 30), 235, cols[k] if sel else (70, 70, 80))
            if sel:
                pygame.draw.rect(screen, cols[k], r, 3, border_radius=4)
            ui.text(screen, d["name"], (r.centerx, r.y + 34), 30, cols[k], bold=True, center=True)
            words = d["desc"].split()
            line, y = "", r.y + 72
            for w in words:
                if ui.render(line + " " + w, 17).get_width() > r.w - 30:
                    ui.text(screen, line.strip(), (r.centerx, y), 17, center=True)
                    y += 24
                    line = ""
                line += " " + w
            ui.text(screen, line.strip(), (r.centerx, y), 17, center=True)
            stats = ["Зомби: x%.1f" % d["zmult"], "Урон зомби: x%.1f" % d["zdmg"], "Голод: x%.1f" % d["hunger"],
                     "Лут: x%.1f" % d["loot"]]
            for i, s in enumerate(stats):
                ui.text(screen, s, (r.centerx, r.y + 145 + i * 26), 16, (180, 180, 180), center=True)
        for b in self.buttons:
            b.draw(screen)


class MultiMenu(MenuBase):
    def __init__(self, app, name):
        super().__init__(app)
        self.name = name
        self.buttons = [
            ui.Button((CX - 200, 250, 400, 70), "Найти комнату", lambda: app.switch(FindRoomMenu(app, name)), 30),
            ui.Button((CX - 200, 340, 400, 70), "Создать комнату", lambda: app.switch(CreateRoomMenu(app, name)),
                      30),
            ui.Button((CX - 200, 460, 400, 56), "Назад", lambda: app.switch(MainMenu(app))),
        ]

    def draw(self, screen):
        self.draw_bg(screen, "Мультиплеер (локальная сеть)")
        ui.text(screen, "Игрок: %s" % self.name, (CX, 180), 22, center=True)
        for b in self.buttons:
            b.draw(screen)
        ui.text(screen, "Все игроки должны быть в одной сети (Wi-Fi/LAN) или в одной VPN-сети (Radmin VPN, ZeroTier)",
                (CX, 560), 16, (170, 170, 170), center=True)


class CreateRoomMenu(MenuBase):
    def __init__(self, app, name):
        super().__init__(app)
        self.name = name
        self.diff = "normal"
        self.idx = {k: 0 for k, _, _, _ in MP_OPTIONS}
        self.err = ""
        self.saves = saves.list_saves()
        self.world_i = 0  # 0 - новый мир, иначе сохранение saves[i-1]
        self.world_btn = pygame.Rect(CX + 80, 212, 300, 34)
        self.buttons = [
            ui.Button((CX - 290, 620, 280, 56), "Создать комнату", self._create, color=(50, 110, 60)),
            ui.Button((CX + 10, 620, 280, 56), "Назад", lambda: app.switch(MultiMenu(app, name))),
        ]

    def _rows(self):
        out = []
        for i, k in enumerate(DIFF_ORDER):
            out.append(("diff", k, pygame.Rect(CX - 380 + i * 190, 160, 180, 48)))
        for i, (k, title, vals, labels) in enumerate(MP_OPTIONS):
            out.append(("opt", k, pygame.Rect(CX + 80, 250 + i * 44, 220, 36)))
        return out

    def handle(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3) and self.world_btn.collidepoint(e.pos):
            self.world_i = (self.world_i + (1 if e.button == 1 else -1)) % (len(self.saves) + 1)
            if self.world_i:
                self.diff = self.saves[self.world_i - 1].get("diff") or self.diff
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3):
            for kind, k, r in self._rows():
                if r.collidepoint(e.pos):
                    if kind == "diff":
                        self.diff = k
                    else:
                        n = len(next(o[2] for o in MP_OPTIONS if o[0] == k))
                        self.idx[k] = (self.idx[k] + (1 if e.button == 1 else -1)) % n
                    return
        super().handle(e)

    def settings(self):
        return {k: vals[self.idx[k]] for k, _, vals, _ in MP_OPTIONS}

    def _create(self):
        slot = self.saves[self.world_i - 1]["slot"] if self.world_i else None
        try:
            host = HostSession(self.name, self.diff, self.settings(), multiplayer=True, save_slot=slot)
        except OSError as ex:
            self.err = "Не удалось открыть порт %d или файл сохранения: %s" % (PORT, ex)
            return
        except (ValueError, KeyError) as ex:
            self.err = "Сохранение повреждено: %s" % ex
            return
        self.app.switch(HostLobby(self.app, host))

    def draw(self, screen):
        self.draw_bg(screen, "Создание комнаты")
        ui.text(screen, "Сложность:", (CX, 135), 20, center=True)
        for kind, k, r in self._rows():
            if kind == "diff":
                sel = k == self.diff
                ui.Button(r, DIFFICULTIES[k]["name"], size=20, color=(120, 60, 50) if sel else (50, 52, 60)).draw(
                    screen)
            else:
                opt = next(o for o in MP_OPTIONS if o[0] == k)
                ui.text(screen, opt[1], (CX - 300, r.y + 5), 20)
                ui.Button(r, opt[3][self.idx[k]], size=20).draw(screen)
        ui.text(screen, "Мир", (CX - 300, 217), 20, (255, 220, 120))
        if self.world_i:
            m = self.saves[self.world_i - 1]
            label = "%s (день %d)" % (m["name"], m.get("day", 1))
        else:
            label = "Новый мир"
        ui.Button(self.world_btn, label, size=19, color=(60, 80, 60)).draw(screen)
        ui.text(screen, "ЛКМ/ПКМ по значению - переключить", (CX, 600), 15, (160, 160, 160), center=True)
        if self.err:
            ui.text(screen, self.err, (CX, 578), 16, (255, 110, 90), center=True)
        for b in self.buttons:
            b.draw(screen)


class HostLobby(MenuBase):
    def __init__(self, app, host):
        super().__init__(app)
        self.host = host
        self.copied = 0.0
        self.buttons = [
            ui.Button((CX - 290, 630, 280, 56), "Начать игру", self._start, color=(50, 110, 60)),
            ui.Button((CX + 10, 630, 280, 56), "Закрыть комнату", self._close, color=(110, 50, 45)),
            ui.Button((CX + 250, 108, 150, 36), "Копировать", self._copy, size=18),
        ]
        if len(host.ips) > 1:
            self.buttons.append(ui.Button((CX - 400, 108, 170, 36), "Другая сеть", host.next_network, size=18))
        self.kick_zones = []

    def _copy(self):
        try:
            pygame.scrap.init()
            pygame.scrap.put(pygame.SCRAP_TEXT, self.host.code.encode("utf-8"))
            self.copied = 2.0
        except Exception:
            pass

    def _close(self):
        self.host.close()
        self.app.switch(MultiMenu(self.app, self.host.name))

    def _start(self):
        app, host = self.app, self.host

        def make():
            from .play import GameScene
            host.start()
            host.local_inbox = []
            return GameScene(app, LocalLink(host), HOST_ID, host.seed, host.diff, host.settings, host=host,
                             world=host.sim.world)

        app.switch(LoadingScene(app, "Генерация мира...", make))

    def handle(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for r, pid in self.kick_zones:
                if r.collidepoint(e.pos):
                    self.host.kick(pid)
                    return
        super().handle(e)

    def update(self, dt):
        super().update(dt)
        self.copied = max(0.0, self.copied - dt)
        self.host.update(dt)
        self.host.local_inbox = []

    def draw(self, screen):
        self.draw_bg(screen)
        h = self.host
        ui.panel(screen, (CX - 420, 20, 840, 140))
        ui.text(screen, "КОД КОМНАТЫ", (CX, 44), 22, (200, 200, 200), center=True)
        ui.text(screen, h.code, (CX, 100), 64, (255, 220, 120), bold=True, center=True)
        ui.text(screen, "%s: %s" % (net_label(h.ip), h.ip), (CX - 400, 30), 15, (160, 160, 160))
        if self.copied:
            ui.text(screen, "Скопировано!", (CX + 325, 150), 15, (120, 230, 120), center=True)
        ui.text(screen, "Игроки (%d/%d)" % (len(h.players), h.settings["max_players"]), (CX - 400, 185), 24,
                bold=True)
        self.kick_zones = []
        y = 225
        for pid, name in h.players.items():
            ui.panel(screen, (CX - 400, y, 460, 44), (35, 36, 42))
            ui.text(screen, name + ("  (хост, вы)" if pid == HOST_ID else ""), (CX - 385, y + 9), 22)
            if pid != HOST_ID:
                r = pygame.Rect(CX - 60, y + 6, 110, 32)
                ui.Button(r, "Кикнуть", size=18, color=(110, 50, 45)).draw(screen)
                self.kick_zones.append((r, pid))
            y += 52
        ui.panel(screen, (CX + 90, 185, 330, 420))
        ui.text(screen, "Настройки", (CX + 105, 195), 22, bold=True)
        ui.text(screen, "Сложность: %s" % DIFFICULTIES[h.diff]["name"], (CX + 105, 235), 17)
        for i, (k, title, vals, labels) in enumerate(MP_OPTIONS):
            ui.text(screen, "%s: %s" % (title, labels[vals.index(h.settings[k])]), (CX + 105, 265 + i * 28), 16,
                    (200, 200, 200))
        ui.text(screen, "Друзья: Мультиплеер -> Найти комнату -> ввести код -> Войти", (CX, 600), 16,
                (180, 180, 180), center=True)
        for b in self.buttons:
            b.draw(screen)


class FindRoomMenu(MenuBase):
    def __init__(self, app, name):
        super().__init__(app)
        self.name = name
        self.code = ui.TextInput((CX - 200, 260, 400, 60), "", 15, "XXX-XXXX", 34, upper=True)
        self.code.active = True
        self.client = None
        self.status = ""
        self.wait = 0.0
        self.hello = False
        self.buttons = [
            ui.Button((CX - 200, 345, 400, 60), "Войти", self._join, 28, color=(50, 110, 60)),
            ui.Button((CX - 200, 425, 400, 52), "Назад", self._back),
        ]

    def _back(self):
        if self.client:
            self.client.close()
        self.app.switch(MultiMenu(self.app, self.name))

    def _join(self):
        if self.client:
            return
        try:
            ip = code_to_ip(self.code.value)
        except (ValueError, OSError):
            self.status = "Неверный код комнаты"
            return
        self.client = NetClient(ip, PORT)
        self.status = "Подключение..."
        self.wait = 0.0
        self.hello = False

    def handle(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN:
            self._join()
            return
        if self.code.handle(e):
            return
        super().handle(e)

    def update(self, dt):
        super().update(dt)
        c = self.client
        if not c:
            return
        self.wait += dt
        if c.status == "error":
            self.status = "Комната не найдена. Проверьте код и что вы в одной сети с хостом"
            self.client = None
            return
        if c.status == "ok" and not self.hello:
            c.send({"t": "hello", "name": self.name, "ver": VERSION})
            self.hello = True
        msgs = c.poll()
        for i, m in enumerate(msgs):
            if m.get("t") == "welcome":
                self.app.switch(ClientLobby(self.app, c, m["id"], self.name, self.code.value, msgs[i + 1:]))
                return
            if m.get("t") == "deny":
                self.status = m.get("reason", "Отказано")
                c.close()
                self.client = None
                return
        if c.status == "ok" and not c.alive:
            self.status = "Хост разорвал соединение"
            self.client = None
        elif self.wait > 8:
            self.status = "Хост не отвечает"
            c.close()
            self.client = None

    def draw(self, screen):
        self.draw_bg(screen, "Найти комнату")
        ui.text(screen, "Введите код комнаты (его видит создатель вверху экрана лобби)", (CX, 220), 20, center=True)
        self.code.draw(screen)
        for b in self.buttons:
            b.draw(screen)
        if self.status:
            ui.text(screen, self.status, (CX, 510), 19, (255, 200, 120), center=True)
        ui.text(screen, "Можно ввести и IP-адрес хоста, например 192.168.1.5", (CX, 560), 15, (150, 150, 150),
                center=True)


class ClientLobby(MenuBase):
    def __init__(self, app, client, my_id, name, code, pending):
        super().__init__(app)
        self.client = client
        self.my_id = my_id
        self.name = name
        self.code = code
        self.players = []
        self.diff = None
        self.settings = {}
        self.pending = list(pending)
        self.buttons = [ui.Button((CX - 140, 630, 280, 56), "Выйти", self._leave, color=(110, 50, 45))]

    def _leave(self):
        self.client.close()
        self.app.switch(MultiMenu(self.app, self.name))

    def update(self, dt):
        super().update(dt)
        msgs = self.pending + self.client.poll()
        self.pending = []
        for m in msgs:
            t = m.get("t")
            if t == "lobby":
                self.players = m["players"]
                self.diff = m["diff"]
                self.settings = m["settings"]
                self.code = m.get("code") or self.code
            elif t == "kick":
                self.client.close()
                self.app.switch(MessageScene(self.app, "Хост выгнал вас из комнаты"))
                return
            elif t == "end":
                self.client.close()
                self.app.switch(MessageScene(self.app, "Хост закрыл комнату"))
                return
            elif t == "start":
                app, client, my_id = self.app, self.client, self.my_id

                def make(m=m):
                    from .play import GameScene
                    return GameScene(app, client, my_id, m["seed"], m["diff"], m["settings"],
                                     edits=m.get("edits"))

                app.switch(LoadingScene(app, "Загрузка мира...", make))
                return
        if not self.client.alive:
            self.app.switch(MessageScene(self.app, "Соединение с хостом потеряно"))

    def draw(self, screen):
        self.draw_bg(screen)
        ui.panel(screen, (CX - 420, 20, 840, 120))
        ui.text(screen, "КОД КОМНАТЫ", (CX, 44), 22, (200, 200, 200), center=True)
        ui.text(screen, self.code, (CX, 96), 56, (255, 220, 120), bold=True, center=True)
        ui.text(screen, "Игроки", (CX - 400, 170), 24, bold=True)
        y = 210
        for pid, name in self.players:
            ui.panel(screen, (CX - 400, y, 460, 44), (35, 36, 42))
            tag = "  (хост)" if pid == HOST_ID else ("  (вы)" if pid == self.my_id else "")
            ui.text(screen, name + tag, (CX - 385, y + 9), 22)
            y += 52
        if self.diff:
            ui.panel(screen, (CX + 90, 170, 330, 400))
            ui.text(screen, "Сложность: %s" % DIFFICULTIES[self.diff]["name"], (CX + 105, 185), 18, bold=True)
            for i, (k, title, vals, labels) in enumerate(MP_OPTIONS):
                if k in self.settings and self.settings[k] in vals:
                    ui.text(screen, "%s: %s" % (title, labels[vals.index(self.settings[k])]),
                            (CX + 105, 220 + i * 28), 16, (200, 200, 200))
        dots = "." * (int(self.t * 2) % 4)
        ui.text(screen, "Ожидание, пока хост начнёт игру" + dots, (CX, 595), 20, (200, 200, 200), center=True)
        for b in self.buttons:
            b.draw(screen)


class MessageScene(MenuBase):
    def __init__(self, app, text):
        super().__init__(app)
        self.msg = text
        self.buttons = [ui.Button((CX - 120, 400, 240, 56), "OK", lambda: app.switch(MainMenu(app)))]

    def handle(self, e):
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_ESCAPE):
            self.app.switch(MainMenu(self.app))
            return
        super().handle(e)

    def draw(self, screen):
        self.draw_bg(screen)
        ui.text(screen, self.msg, (CX, 320), 28, center=True)
        for b in self.buttons:
            b.draw(screen)


class LoadingScene(MenuBase):
    def __init__(self, app, text, factory):
        super().__init__(app)
        self.msg = text
        self.factory = factory
        self.frames = 0

    def update(self, dt):
        self.frames += 1
        if self.frames == 3:
            try:
                self.app.switch(self.factory())
            except Exception as ex:
                import traceback
                traceback.print_exc()
                self.app.switch(MessageScene(self.app, "Ошибка: %s" % ex))

    def draw(self, screen):
        self.draw_bg(screen)
        ui.text(screen, self.msg, (CX, SCREEN_H // 2), 36, center=True)


HELP = [
    ("WASD", "движение,  Shift - бег"),
    ("Мышь / ЛКМ", "прицел и атака (выстрел / удар)"),
    ("R", "перезарядка"),
    ("Q / колесо / 1 / 2", "сменить оружие (огнестрел / ближний бой)"),
    ("E", "обыскать, торговать, лестница, верстак, бензоколонка"),
    ("F", "сесть / выйти из машины"),
    ("В машине", "W/S - газ/тормоз, A/D - руль, Space - ручник"),
    ("Tab", "инвентарь (ЛКМ - использовать, ПКМ - выбросить)"),
    ("H", "быстрое лечение (бинт / аптечка)"),
    ("B / X", "строительство и крафт / разобрать свою постройку"),
    ("M", "карта,  T - чат,  Esc - меню,  F11 - полный экран"),
]
TIPS = [
    "Следите за температурой тела: в снегах нужна тёплая одежда и костёр, в пустыне - лёгкая одежда и вода.",
    "Охотьтесь на оленей, жарьте мясо у костра (E), из шкур шейте шубу. Укусы зомби заражают - нужны антибиотики.",
    "Каждую ночь в 21:00 приходит орда, в полдень - сброс груза. M - карта: колесо - масштаб, ПКМ - метка.",
    "Старт - за городом. Рубите деревья, бейте камни, собирайте ягоды и стройте дом (B).",
    "Вход в здание - жёлтый навес со стрелкой на крыше и дорожка к двери.",
    "Торговцы (жёлтые) и выжившие (зелёные) - E чтобы торговать. Бандиты (красные) нападают сразу.",
    "Еда и вода - холодильники, шкафчики, магазины, АЗС. Без них вы начнёте терять здоровье.",
    "Оружие и броня - полиция, военная база, иногда шкафы и столы в домах.",
    "Детали для машин и Инструменты - гаражи и склады. Тюнинг - на верстаке в гараже.",
    "Поднимайтесь по лестницам: на верхних этажах многоэтажек и больниц больше лута.",
    "Ночью зомби быстрее и их больше. Выстрелы шумят - глушитель помогает.",
]


def draw_help(screen):
    ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 200))
    screen.blit(ov, (0, 0))
    ui.panel(screen, (CX - 470, 60, 940, 600), alpha=245)
    ui.text(screen, "Управление", (CX, 90), 34, (230, 70, 55), bold=True, center=True)
    y = 130
    for k, v in HELP:
        ui.text(screen, k, (CX - 430, y), 20, (255, 220, 120), bold=True)
        ui.text(screen, v, (CX - 210, y), 20)
        y += 29
    y += 12
    for t in TIPS:
        ui.text(screen, "- " + t, (CX - 430, y), 16, (190, 190, 200))
        y += 24
    ui.text(screen, "Нажмите Esc или F1, чтобы закрыть", (CX, 640), 16, (160, 160, 160), center=True)
