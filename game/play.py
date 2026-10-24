"""Игровой экран: управление, предсказание движения, отрисовка, HUD, инвентарь, мастерская."""
import math
import random

import pygame

from . import items as IT
from . import sound
from . import ui
from .config import TILE, SCREEN_W, SCREEN_H, DIFFICULTIES
from .render import Renderer, draw_player, draw_zombie, draw_bag, draw_icon, draw_animal
from .world import area_name
from .world import (World, UP, DOWN, CONTAINER, TILE_NAMES, WORKBENCH, PUMP, CAMPFIRE, KIND_LABEL, CS, BUSH, BED,
                    BUILDS, BUILD_D, PLACEABLE, SOLID, GRASS, DIRT, FIELD, DIRTROAD)

NPC_COLORS = {"trader": (210, 170, 60), "guard": (70, 140, 80), "surv": (100, 170, 110), "bandit": (150, 45, 45)}
NPC_TITLE = {"trader": "Торговец", "guard": "Охранник", "surv": "Выживший", "bandit": "Бандит"}

PLAYER_R = 12
SLOT = 58
GAP = 6
EQ_SLOTS = [("gun", "Огнестрел"), ("melee", "Ближний"), ("vest", "Броня"), ("helmet", "Шлем"),
            ("cloth", "Одежда"), ("hat", "Шапка"), ("bag", "Рюкзак")]
ANIMALS = ("deer", "wolf")
MAP_ZOOMS = [0.75, 1, 1.5, 2, 3, 4, 6]


def _lerp_ang(a, b, k):
    d = (b - a + math.pi) % (2 * math.pi) - math.pi
    return a + d * k


class GameScene:
    def __init__(self, app, link, my_id, seed, diff, settings, host=None, world=None, edits=None):
        self.app = app
        self.link = link
        self.host = host
        self.my_id = my_id
        self.mp = host is None or host.multiplayer
        self.world = world or World(seed)
        if edits and world is None:
            self.world.load_edits(edits)
        self.build_ui = False
        self.build_sel = None
        self.weather = "clear"
        self.drops = []
        self.wparts = []
        self.waypoint = None
        self.map_zoom = 3
        self.map_center = None
        self.map_drag = False
        self.r = Renderer(self.world)
        self.diff = diff
        self.settings = settings
        self.me = None
        self.players, self.zombies, self.cars, self.bags = {}, {}, {}, []
        self.cont = None
        self.px = self.py = 0.0
        self.plv = 0
        self.tpn = -1
        self.ready = False
        self.aim = 0.0
        self.moving = self.sprinting = False
        self.driving = False
        self.dcar = None
        self.send_t = 0.0
        self.atk_cd = 0.0
        self.mouse_was = False
        self.effects = []
        self.parts = []
        self.feed = []
        self.hurt_t = 0.0
        self.inv_open = self.shop_open = self.map_open = self.paused = False
        self.chat = None
        self.chat_skip = False
        self.spec = None
        self.tod, self.day = 8 / 24, 1
        self.over = False
        self.zones = []
        self.tip = None
        self.camx = self.camy = 0.0
        self.vx = self.vy = 0.0
        self.vlv = 0
        self.vbid = None
        self.npcs = {}
        self.trade_ui = False
        self.trade_t = 0.0
        self.groan_t = 4.0
        self.hint = None
        self.dark = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        self.time = 0.0
        self.lost_t = 0.0
        self.add_feed("Выживите как можно дольше. F1 - управление", (240, 200, 70))

    # ---------------- сеть ----------------
    def add_feed(self, text, color=(235, 235, 235)):
        self.feed.append([text, 9.0, color])
        self.feed = self.feed[-8:]

    def _apply(self, s):
        self.me = me = s["me"]
        self.tod, self.day, self.cont = s["tod"], s["day"], s["cont"]
        if me["tpn"] != self.tpn and me["tp"]:
            self.px, self.py, self.plv = me["tp"]
            self.tpn = me["tpn"]
            self.ready = True
            self.driving = False
        seen = set()
        for row in s["P"]:
            pid, name, x, y, lv, a, hp, alive, car, seat, wpn, vest, helm, color = row[:14]
            cloth, hat = (row[14], row[15]) if len(row) > 15 else ("", "")
            d = self.players.get(pid)
            if d is None or abs(d["rx"] - x) > 300 or abs(d["ry"] - y) > 300 or d["lv"] != lv:
                d = {"rx": x, "ry": y, "ra": a}
                self.players[pid] = d
            d.update(id=pid, name=name, x=x, y=y, lv=lv, a=a, hp=hp, alive=alive, car=car, seat=seat, wpn=wpn,
                     vest=vest, helm=helm, color=tuple(color), cloth=cloth, hat=hat)
            seen.add(pid)
        for pid in list(self.players):
            if pid not in seen:
                del self.players[pid]
        seen = set()
        for zid, kind, x, y, lv, a, frac in s["Z"]:
            d = self.zombies.get(zid)
            if d is None or abs(d["rx"] - x) > 200 or abs(d["ry"] - y) > 200:
                d = {"rx": x, "ry": y, "ra": a}
                self.zombies[zid] = d
            d.update(kind=kind, x=x, y=y, lv=lv, a=a, f=frac)
            seen.add(zid)
        for zid in list(self.zombies):
            if zid not in seen:
                del self.zombies[zid]
        seen = set()
        for cid, x, y, ang, spd, hp, mhp, fuel, mfuel, color, up, seats, wreck in s["C"]:
            d = self.cars.get(cid)
            if d is None or abs(d["rx"] - x) > 300 or abs(d["ry"] - y) > 300:
                d = {"rx": x, "ry": y, "rang": ang}
                self.cars[cid] = d
            d.update(id=cid, x=x, y=y, ang=ang, spd=spd, hp=hp, mhp=mhp, fuel=fuel, mfuel=mfuel, color=color,
                     up=up, seats=seats, wreck=wreck)
            seen.add(cid)
        for cid in list(self.cars):
            if cid not in seen:
                del self.cars[cid]
        seen = set()
        for nid, kind, name, x, y, lv, a, frac, wpn, vest, helm, hostile in s.get("N", ()):
            d = self.npcs.get(nid)
            if d is None or abs(d["rx"] - x) > 200 or abs(d["ry"] - y) > 200:
                d = {"rx": x, "ry": y, "ra": a}
                self.npcs[nid] = d
            d.update(id=nid, kind=kind, name=name, x=x, y=y, lv=lv, a=a, f=frac, wpn=wpn, vest=vest, helm=helm,
                     hostile=hostile)
            seen.add(nid)
        for nid in list(self.npcs):
            if nid not in seen:
                del self.npcs[nid]
        self.bags = s["B"]
        self.weather = s.get("W", "clear")
        self.drops = s.get("D", [])
        if s.get("over"):
            self.over = True
        for e in s["ev"]:
            self._event(e)

    def _vol(self, e):
        if "x" not in e:
            return 1.0
        return max(0.0, 1.0 - math.hypot(e["x"] - self.vx, e["y"] - self.vy) / 1200.0)

    def _event(self, e):
        k = e.get("k")
        if k == "tr":
            self.effects.append({"k": "tr", "x1": e["x1"], "y1": e["y1"], "x2": e["x2"], "y2": e["y2"],
                                 "lv": e["lv"], "t": 0.08})
        elif k == "bl":
            for _ in range(6):
                self._part(e["x"], e["y"], e["lv"], (150 + random.randint(0, 60), 10, 10), 90, 0.5)
        elif k == "zd":
            for _ in range(16):
                self._part(e["x"], e["y"], e["lv"], (120 + random.randint(0, 60), 15, 10), 140, 0.9)
            sound.play("zd", self._vol(e) * 0.8)
        elif k == "shot":
            sound.play("silenced" if e.get("s") else sound.SHOT_SOUND.get(e.get("w"), "pistol"), self._vol(e))
            self.effects.append({"k": "flash", "x": e["x"], "y": e["y"], "t": 0.06})
        elif k == "sw":
            sound.play("hit" if e.get("h") else "swing", self._vol(e) * 0.8)
        elif k == "snd":
            sound.play(e["s"], self._vol(e) * (0.7 if e["s"] == "groan" else 1.0))
        elif k == "msg":
            self.add_feed(e["t"])
        elif k == "ed":
            lv, tx, ty, t, o = e["e"]
            self.world.apply_edit(lv, tx, ty, t, o)
            self.r.invalidate(lv, tx, ty)
        elif k == "chop":
            col = (150, 105, 60) if e["w"] == "wood" else (150, 150, 155)
            for _ in range(5):
                self._part(e["x"], e["y"], e["lv"], col, 110, 0.4)
            sound.play("chop", self._vol(e))
        elif k == "chat":
            self.add_feed("%s: %s" % (e["n"], e["t"]), (150, 210, 255))
        elif k == "hurt":
            self.hurt_t = 0.35
            sound.play("hurt", 0.6)
        elif k == "cs":
            if self.driving:
                self.dcar["spd"] *= e["f"]
        elif k == "boom":
            for _ in range(40):
                self._part(e["x"], e["y"], 0, random.choice([(255, 160, 40), (240, 80, 20), (60, 60, 60)]), 260, 1.2)
            self.effects.append({"k": "boom", "x": e["x"], "y": e["y"], "t": 0.5})
            sound.play("boom", self._vol(e))

    def _part(self, x, y, lv, col, spd, life):
        a = random.uniform(0, math.tau)
        v = random.uniform(0.2, 1) * spd
        self.parts.append([x, y, math.cos(a) * v, math.sin(a) * v, life, col, lv])

    # ---------------- обновление ----------------
    def update(self, dt):
        self.time += dt
        self.last_dt = dt
        if self.host:
            self.host.paused = (not self.mp) and self.paused
            self.host.update(dt)
        for m in self.link.poll():
            t = m.get("t")
            if t == "s":
                self._apply(m)
            elif t == "kick":
                return self._leave("Хост выгнал вас из игры")
            elif t == "end":
                return self._leave("Хост закрыл игру")
            elif t == "saved":
                self.add_feed("Игра сохранена", (140, 230, 120))
        if not self.link.alive:
            return self._leave("Соединение с хостом потеряно")
        if not self.ready or not self.me:
            return
        self._local(dt)
        k = min(1.0, dt * 14)
        for d in self.players.values():
            d["rx"] += (d["x"] - d["rx"]) * k
            d["ry"] += (d["y"] - d["ry"]) * k
            d["ra"] = _lerp_ang(d["ra"], d["a"], k)
        for d in list(self.zombies.values()) + list(self.npcs.values()):
            d["rx"] += (d["x"] - d["rx"]) * k
            d["ry"] += (d["y"] - d["ry"]) * k
            d["ra"] = _lerp_ang(d["ra"], d["a"], k)
        # подгрузка чанков вокруг заранее, по одному за кадр
        vcx, vcy = int(self.vx // TILE) >> 5, int(self.vy // TILE) >> 5
        for dy in (0, -1, 1, -2, 2):
            for dx in (0, -1, 1, -2, 2):
                if (vcx + dx, vcy + dy) not in self.world.chunks:
                    self.world.chunk(vcx + dx, vcy + dy)
                    break
            else:
                continue
            break
        if self.trade_ui and not self.me.get("trade") and self.time - self.trade_t > 1.0:
            self.trade_ui = False
        for d in self.cars.values():
            d["rx"] += (d["x"] - d["rx"]) * k
            d["ry"] += (d["y"] - d["ry"]) * k
            d["rang"] = _lerp_ang(d["rang"], d["ang"], k)
        for e in self.effects:
            e["t"] -= dt
        self.effects = [e for e in self.effects if e["t"] > 0]
        for p in self.parts:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[2] *= 0.9
            p[3] *= 0.9
            p[4] -= dt
        self.parts = [p for p in self.parts if p[4] > 0]
        for f in self.feed:
            f[1] -= dt
        self.feed = [f for f in self.feed if f[1] > 0]
        self.hurt_t = max(0.0, self.hurt_t - dt)
        self.groan_t -= dt
        if self.groan_t <= 0:
            self.groan_t = random.uniform(3, 7)
            near = [z for z in self.zombies.values() if z["lv"] == self.vlv and z["kind"] not in ANIMALS and
                    math.hypot(z["rx"] - self.vx, z["ry"] - self.vy) < 500]
            if near:
                z = random.choice(near)
                sound.play("groan", 0.5 * (1 - math.hypot(z["rx"] - self.vx, z["ry"] - self.vy) / 600))
        self.send_t -= dt
        if self.send_t <= 0:
            self.send_t = 1 / 30
            m = {"t": "in", "x": round(self.vx if not self.me["alive"] else self.px, 1),
                 "y": round(self.vy if not self.me["alive"] else self.py, 1),
                 "lv": self.vlv if not self.me["alive"] else self.plv, "a": round(self.aim, 3),
                 "sp": int(self.sprinting), "mv": int(self.moving), "tpn": self.tpn}
            if self.driving:
                d = self.dcar
                m["car"] = [round(d["x"], 1), round(d["y"], 1), round(d["ang"], 3), round(d["spd"], 1)]
            self.link.send(m)

    def _leave(self, text=None):
        from .menus import MessageScene, MainMenu
        if self.host:
            self.host.close()
        self.link.close()
        self.app.switch(MessageScene(self.app, text) if text else MainMenu(self.app))

    def _save_now(self):
        if self.host and self.host.save_game():
            self.add_feed("Игра сохранена: %s" % self.host.world_name, (140, 230, 120))
        else:
            self.add_feed("Не удалось сохранить", (240, 120, 100))

    def _typing(self):
        return self.chat is not None

    def _local(self, dt):
        me = self.me
        keys = pygame.key.get_pressed()
        alive = me["alive"]
        car_id, seat = me["car"], me["seat"]
        self.moving = self.sprinting = False
        if alive and car_id >= 0 and car_id in self.cars:
            c = self.cars[car_id]
            if seat == 0:
                if not self.driving or self.dcar["id"] != car_id:
                    self.driving = True
                    self.dcar = {"id": car_id, "x": c["x"], "y": c["y"], "ang": c["ang"], "spd": 0.0}
                self._drive(dt, None if self._typing() else keys, c)
                self.px, self.py, self.plv = self.dcar["x"], self.dcar["y"], 0
            else:
                self.driving = False
                self.px, self.py, self.plv = c["rx"], c["ry"], 0
        else:
            self.driving = False
            if alive and not self._typing():
                dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
                dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
                if dx or dy:
                    self.moving = True
                    self.sprinting = bool(keys[pygame.K_LSHIFT]) and me["stam"] > 2
                    sp = 195 if self.sprinting else 125
                    vest = me["eq"].get("vest")
                    if vest:
                        sp *= 1 - IT.ITEMS[vest["id"]].get("slow", 0)
                    if me["food"] <= 0 or me["water"] <= 0:
                        sp *= 0.8
                    ln = math.hypot(dx, dy)
                    self.px, self.py, _ = self.world.move(self.plv, self.px, self.py, dx / ln * sp * dt,
                                                          dy / ln * sp * dt, PLAYER_R)
            if alive:
                for z in list(self.zombies.values()) + list(self.npcs.values()):
                    if z["lv"] != self.plv:
                        continue
                    zr = 15 if z["kind"] == "brute" else (12 if z["kind"] in NPC_TITLE else 11)
                    ddx, ddy = self.px - z["rx"], self.py - z["ry"]
                    dd = math.hypot(ddx, ddy)
                    if 0.01 < dd < PLAYER_R + zr:
                        push = (PLAYER_R + zr - dd) * 0.5
                        self.px, self.py, _ = self.world.move(self.plv, self.px, self.py, ddx / dd * push,
                                                              ddy / dd * push, PLAYER_R)
                if self.plv == 0:
                    for c in self.cars.values():
                        ca, sa = math.cos(c["rang"]), math.sin(c["rang"])
                        for off in (-20, 0, 20):
                            cx, cy = c["rx"] + ca * off, c["ry"] + sa * off
                            ddx, ddy = self.px - cx, self.py - cy
                            dd = math.hypot(ddx, ddy)
                            if 0.01 < dd < PLAYER_R + 17:
                                push = PLAYER_R + 17 - dd
                                self.px, self.py, _ = self.world.move(0, self.px, self.py, ddx / dd * push,
                                                                      ddy / dd * push, PLAYER_R)
        # вид / камера
        if alive:
            self.vx, self.vy, self.vlv = self.px, self.py, self.plv
        else:
            tgt = self.players.get(self.spec)
            if not tgt or not tgt["alive"]:
                alive_others = [p for p in self.players.values() if p["alive"] and p["id"] != self.my_id]
                self.spec = alive_others[0]["id"] if alive_others else None
                tgt = self.players.get(self.spec)
            if tgt:
                self.vx, self.vy, self.vlv = tgt["rx"], tgt["ry"], tgt["lv"]
            else:
                self.vx, self.vy, self.vlv = self.px, self.py, self.plv
        self.vbid = self.world.bid_at(self.vx, self.vy)
        mx, my = pygame.mouse.get_pos()
        offx = max(-160, min(160, (mx - SCREEN_W / 2) * 0.22)) if alive else 0
        offy = max(-110, min(110, (my - SCREEN_H / 2) * 0.22)) if alive else 0
        tx, ty = self.vx - SCREEN_W / 2 + offx, self.vy - SCREEN_H / 2 + offy
        self.camx += (tx - self.camx) * min(1.0, dt * 10)
        self.camy += (ty - self.camy) * min(1.0, dt * 10)
        if abs(self.camx - tx) > 600 or abs(self.camy - ty) > 600:
            self.camx, self.camy = tx, ty
        self.aim = math.atan2(my - (self.py - self.camy), mx - (self.px - self.camx))
        # атака
        self.atk_cd -= dt
        blocked = (self.inv_open or self.shop_open or self.map_open or self.paused or self._typing()
                   or self.trade_ui or self.build_ui or self.build_sel)
        held = pygame.mouse.get_pressed()[0] and not blocked
        if alive and held and not (car_id >= 0 and seat == 0) and self.atk_cd <= 0:
            g = me["eq"].get("gun")
            if me["act"] == "gun" and g:
                d = IT.ITEMS[g["id"]]
                if d.get("auto") or not self.mouse_was:
                    if g["ammo"] <= 0:
                        if me["rl"] < 0 and not self.mouse_was:
                            sound.play("click", 0.6)
                            self.link.send({"t": "rel"})
                        self.atk_cd = 0.3
                    elif me["rl"] < 0:
                        self.link.send({"t": "atk", "a": round(self.aim, 3)})
                        self.atk_cd = d["rate"]
            else:
                mel = me["eq"].get("melee")
                d = IT.ITEMS[mel["id"]] if mel else IT.FISTS
                self.link.send({"t": "atk", "a": round(self.aim, 3)})
                self.atk_cd = d["rate"]
        self.mouse_was = held
        self.hint = self._find_interact() if alive else None

    def _car_free(self, x, y, ang, cid):
        ca, sa = math.cos(ang), math.sin(ang)
        for off in (-20, 0, 20):
            if not self.world.circle_free(0, x + ca * off, y + sa * off, 17):
                return False
        for c in self.cars.values():
            if c["id"] != cid and abs(c["rx"] - x) < 70 and abs(c["ry"] - y) < 70:
                oa, osa = math.cos(c["rang"]), math.sin(c["rang"])
                for o1 in (-20, 0, 20):
                    for o2 in (-20, 0, 20):
                        if math.hypot(x + ca * o1 - c["rx"] - oa * o2, y + sa * o1 - c["ry"] - osa * o2) < 30:
                            return False
        return True

    def _drive(self, dt, keys, c):
        d = self.dcar
        up = c["up"]
        th = st = hb = 0
        if keys is not None:
            th = (keys[pygame.K_w] or keys[pygame.K_UP]) - (keys[pygame.K_s] or keys[pygame.K_DOWN])
            st = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
            hb = keys[pygame.K_SPACE]
        if c["fuel"] <= 0 or c["wreck"]:
            th = max(0, th) * 0
        maxv = 330 * (1 + 0.15 * up["engine"])
        acc = 230 * (1 + 0.25 * up["engine"])
        spd = d["spd"]
        if th > 0:
            spd += (acc if spd >= 0 else 520) * dt
        elif th < 0:
            spd -= (520 if spd > 0 else acc * 0.6) * dt
        else:
            drag = 110 * dt
            spd = spd - drag if spd > drag else (spd + drag if spd < -drag else 0.0)
        if hb:
            b = 650 * dt
            spd = spd - b if spd > b else (spd + b if spd < -b else 0.0)
        spd = max(-130.0, min(maxv, spd))
        stuck = not self._car_free(d["x"], d["y"], d["ang"], d["id"])
        grip = 2.5 * (1 + 0.15 * up["tires"])
        na = d["ang"] + st * grip * dt * max(-1.0, min(1.0, spd / 110))
        if stuck or self._car_free(d["x"], d["y"], na, d["id"]):
            d["ang"] = na
        ca, sa = math.cos(d["ang"]), math.sin(d["ang"])
        nx, ny = d["x"] + ca * spd * dt, d["y"] + sa * spd * dt
        if stuck or self._car_free(nx, ny, d["ang"], d["id"]):
            d["x"], d["y"] = nx, ny
        elif self._car_free(nx, d["y"], d["ang"], d["id"]) and abs(spd) < 200:
            d["x"] = nx
            spd *= 0.9
        elif self._car_free(d["x"], ny, d["ang"], d["id"]) and abs(spd) < 200:
            d["y"] = ny
            spd *= 0.9
        else:
            if abs(spd) > 110:
                self.link.send({"t": "crash", "v": round(abs(spd))})
                sound.play("crash", 0.8)
            spd = -spd * 0.25
        d["spd"] = spd

    # ---------------- взаимодействие ----------------
    def _find_interact(self):
        me = self.me
        if me["car"] >= 0:
            return ("F - выйти из машины", None)
        tx, ty = int(self.px // TILE), int(self.py // TILE)
        t = self.world.tile(self.plv, tx, ty)
        if t == UP and self.world.tile(self.plv + 1, tx + 1, ty) == DOWN:
            return ("E - подняться на %d этаж" % (self.plv + 2), lambda: self._stairs(1, tx, ty))
        if t == DOWN and self.plv > 0:
            return ("E - спуститься на %d этаж" % self.plv, lambda: self._stairs(-1, tx, ty))
        best, bd = None, 46
        for bid, bx, by, blv, kind in self.bags:
            if blv == self.plv:
                d = math.hypot(bx - self.px, by - self.py)
                if d < bd:
                    best, bd = ("E - обыскать: %s" % ("тело" if kind == "body" else "вещи на земле"),
                                lambda k="bag:%d" % bid: self._open(k)), d
        if best:
            return best
        nb, nd = None, 70
        for n in self.npcs.values():
            if n["lv"] == self.plv and not n["hostile"]:
                d = math.hypot(n["rx"] - self.px, n["ry"] - self.py)
                if d < nd:
                    nb, nd = n, d
        if nb:
            verb = "поговорить" if nb["kind"] == "guard" else "торговать"
            return ("E - %s: %s %s" % (verb, NPC_TITLE[nb["kind"]].lower(), nb["name"]),
                    lambda nid=nb["id"]: self._open_trade(nid))
        cand, cd = None, 1e9
        for oy in range(-2, 3):
            for ox in range(-2, 3):
                ttx, tty = tx + ox, ty + oy
                tt = self.world.tile(self.plv, ttx, tty)
                if tt in CONTAINER or tt in (WORKBENCH, PUMP, BUSH, BED):
                    cx, cy = ttx * TILE + 16, tty * TILE + 16
                    d = math.hypot(cx - self.px, cy - self.py)
                    if d > 54:
                        continue
                    da = abs((math.atan2(cy - self.py, cx - self.px) - self.aim + math.pi) % math.tau - math.pi)
                    score = d + da * 12
                    if score < cd:
                        cand, cd = (tt, ttx, tty), score
        if cand:
            tt, ttx, tty = cand
            if tt == WORKBENCH:
                return ("E - верстак (тюнинг машины и оружия)", self._open_shop)
            if tt == PUMP:
                return ("E - заправить машину", lambda: self.link.send({"t": "refuel"}))
            if tt == BUSH:
                return ("E - собрать ягоды", lambda: self.link.send({"t": "harvest", "tx": ttx, "ty": tty}))
            if tt == BED:
                return ("E - запомнить кровать (точка возрождения)",
                        lambda: self.link.send({"t": "setspawn", "tx": ttx, "ty": tty}))
            key = "%d,%d,%d" % (self.plv, ttx, tty)
            return ("E - обыскать: %s" % TILE_NAMES.get(tt, ""), lambda: self._open(key))
        if self.me.get("fire") and any(it["id"] == "meat" for it in self.me["inv"]):
            return ("E - пожарить мясо на костре", lambda: self.link.send({"t": "cook"}))
        if self.plv == 0:
            for c in self.cars.values():
                if not c["wreck"] and math.hypot(c["rx"] - self.px, c["ry"] - self.py) < 80:
                    return ("F - сесть в машину", None)
        return None

    def _stairs(self, d, tx, ty):
        nx = tx + d
        self.plv += d
        self.px, self.py = nx * TILE + 16, ty * TILE + 16
        sound.play("door", 0.5)

    def _open(self, key):
        self.link.send({"t": "open", "k": key})
        self.inv_open = True

    def _open_trade(self, nid):
        self.link.send({"t": "tropen", "n": nid})
        self.trade_ui = True
        self.trade_t = self.time
        self.inv_open = self.shop_open = False

    def _close_trade(self):
        self.link.send({"t": "trclose"})
        self.trade_ui = False

    def _area_name(self):
        tx, ty = int(self.vx // TILE), int(self.vy // TILE)
        c = self.world.chunks.get((tx >> 5, ty >> 5))
        return area_name(c.biome, c.climate) if c else "Улица"

    def _open_shop(self):
        self.shop_open = True
        self.inv_open = False

    def _close_inv(self):
        if self.inv_open and self.cont:
            self.link.send({"t": "close"})
        self.inv_open = False

    def handle(self, e):
        if self.chat is not None:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN:
                if self.chat.value.strip():
                    self.link.send({"t": "chat", "x": self.chat.value})
                self.chat = None
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.chat = None
            elif e.type == pygame.TEXTINPUT and self.chat_skip:
                self.chat_skip = False
            else:
                self.chat.handle(e)
            return
        if self.map_open and not self.paused and self._map_event(e):
            return
        if e.type == pygame.MOUSEBUTTONDOWN:
            for rect, btn, fn in reversed(self.zones):
                if btn == e.button and rect.collidepoint(e.pos):
                    fn()
                    return
            if self.build_sel and not self.build_ui and self.me and self.me["alive"]:
                if e.button == 1:
                    tx, ty = self._mouse_tile()
                    self.link.send({"t": "build", "s": self.build_sel, "lv": self.plv, "tx": tx, "ty": ty})
                elif e.button == 3:
                    self.build_sel = None
                return
            if self.me and not self.me["alive"] and e.button == 1 and not self.paused:
                others = [p["id"] for p in self.players.values() if p["alive"] and p["id"] != self.my_id]
                if others:
                    i = others.index(self.spec) + 1 if self.spec in others else 0
                    self.spec = others[i % len(others)]
            return
        if e.type == pygame.MOUSEWHEEL and self.me and not (self.inv_open or self.shop_open or self.map_open):
            self.link.send({"t": "swap"})
            return
        if e.type != pygame.KEYDOWN:
            return
        k = e.key
        if self.trade_ui and k in (pygame.K_ESCAPE, pygame.K_e, pygame.K_TAB):
            self._close_trade()
            return
        if (self.build_ui or self.build_sel) and k == pygame.K_ESCAPE:
            self.build_ui = False
            self.build_sel = None
            return
        if k == pygame.K_b and self.me and self.me["alive"] and not self.paused:
            self.build_ui = not self.build_ui
            self.inv_open = self.shop_open = False
            return
        if k == pygame.K_x and self.me and self.me["alive"] and not self.paused:
            tx, ty = self._mouse_tile()
            self.link.send({"t": "unbuild", "lv": self.plv, "tx": tx, "ty": ty})
            return
        if k == pygame.K_ESCAPE:
            if self.inv_open:
                self._close_inv()
            elif self.shop_open or self.map_open or self.app.show_help:
                self.shop_open = self.map_open = False
                self.app.show_help = False
            else:
                self.paused = not self.paused
            return
        if self.paused or not self.me:
            return
        if k == pygame.K_F1:
            self.app.show_help = not self.app.show_help
        elif k in (pygame.K_t, pygame.K_RETURN):
            self.chat = ui.TextInput((20, SCREEN_H - 250, 420, 36), "", 100, "Сообщение...", 20)
            self.chat.active = True
            self.chat_skip = k == pygame.K_t
        elif k == pygame.K_m:
            self.map_open = not self.map_open
        elif not self.me["alive"]:
            return
        elif k in (pygame.K_TAB, pygame.K_i):
            if self.inv_open:
                self._close_inv()
            else:
                self.inv_open = True
                self.shop_open = False
        elif k == pygame.K_e:
            if self.hint and self.hint[1]:
                self.hint[1]()
        elif k == pygame.K_f:
            self.link.send({"t": "car"})
            self.inv_open = self.shop_open = False
        elif k == pygame.K_r:
            self.link.send({"t": "rel"})
        elif k == pygame.K_q:
            self.link.send({"t": "swap"})
        elif k == pygame.K_1:
            self.link.send({"t": "sel", "s": "gun"})
        elif k == pygame.K_2:
            self.link.send({"t": "sel", "s": "melee"})
        elif k == pygame.K_h:
            self._quick_heal()

    def _quick_heal(self):
        inv = self.me["inv"]
        order = ["bandage", "medkit", "pills"] if self.me["bleed"] else ["pills", "bandage", "medkit"]
        for iid in order:
            for i, it in enumerate(inv):
                if it["id"] == iid:
                    self.link.send({"t": "use", "i": i})
                    return
        self.add_feed("Нет медикаментов", (240, 120, 100))

    # ---------------- отрисовка ----------------
    def w2s(self, x, y):
        return x - self.camx, y - self.camy

    def _visible(self, x, y, lv):
        if lv != self.vlv:
            return False
        bid = self.world.bid_at(x, y)
        if self.vlv == 0:
            return bid is None or bid is self.vbid
        return bid is self.vbid

    def draw(self, screen):
        self.zones = []
        self.tip = None
        if not self.ready or not self.me:
            screen.fill((10, 12, 14))
            ui.text(screen, "Подключение к миру...", (SCREEN_W // 2, SCREEN_H // 2), 32, center=True)
            return
        camx, camy = int(self.camx), int(self.camy)
        self.camx, self.camy = camx, camy
        self.r.draw_ground(screen, camx, camy)
        sw, sh = SCREEN_W, SCREEN_H
        if self.vlv == 0:
            self._draw_entities(screen, 0)
            self._draw_cars(screen)
            self._draw_roofs(screen, exclude=self.vbid)
        else:
            self._draw_cars(screen)
            self._draw_roofs(screen, exclude=self.vbid)
            ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 150))
            screen.blit(ov, (0, 0))
            if self.vbid:
                b = self.vbid
                screen.blit(self.r.upper_surface(b, self.vlv), (b.x * TILE - camx, b.y * TILE - camy))
            self._draw_entities(screen, self.vlv)
        for e in self.effects:
            if e["k"] == "tr" and e["lv"] == self.vlv:
                a = self.w2s(e["x1"], e["y1"])
                b = self.w2s(e["x2"], e["y2"])
                pygame.draw.line(screen, (255, 230, 150), a, b, 2)
            elif e["k"] == "flash":
                x, y = self.w2s(e["x"], e["y"])
                pygame.draw.circle(screen, (255, 220, 120), (int(x), int(y)), 6)
            elif e["k"] == "boom":
                x, y = self.w2s(e["x"], e["y"])
                pygame.draw.circle(screen, (255, 170, 60), (int(x), int(y)), int(110 * (1 - e["t"] / 0.5)) + 10, 6)
        self._draw_darkness(screen)
        self._draw_weather(screen, getattr(self, "last_dt", 1 / 60))
        if self.build_sel and not self.build_ui and self.me["alive"]:
            self._draw_ghost(screen)
        if self.hurt_t > 0:
            ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
            ov.fill((200, 0, 0, int(140 * self.hurt_t)))
            screen.blit(ov, (0, 0))
        self._draw_hud(screen)
        if self.inv_open:
            self._draw_inventory(screen)
        if self.shop_open:
            self._draw_shop(screen)
        if self.trade_ui and self.me.get("trade"):
            self._draw_trade(screen)
        if self.build_ui:
            self._draw_build(screen)
        if self.map_open:
            self._draw_map(screen)
        if not self.me["alive"] or self.over:
            self._draw_dead(screen)
        if self.chat is not None:
            ui.panel(screen, (14, SCREEN_H - 256, 432, 48))
            self.chat.draw(screen)
        if self.paused:
            self._draw_pause(screen)
        if self.tip:
            self._draw_tip(screen, *self.tip)

    def _draw_roofs(self, screen, exclude):
        sw, sh = SCREEN_W, SCREEN_H
        x0, y0 = int(self.camx // TILE), int(self.camy // TILE)
        x1, y1 = int((self.camx + sw) // TILE) + 1, int((self.camy + sh) // TILE) + 1
        for b in self.world.buildings_in(x0, y0, x1, y1):
            if b is not exclude:
                screen.blit(self.r.roof(b), (b.x * TILE - self.camx, b.y * TILE - self.camy))

    def _draw_cars(self, screen):
        for c in self.cars.values():
            if self.driving and c["id"] == self.dcar["id"]:
                x, y, ang = self.dcar["x"], self.dcar["y"], self.dcar["ang"]
            else:
                x, y, ang = c["rx"], c["ry"], c["rang"]
            sx, sy = self.w2s(x, y)
            if -80 < sx < SCREEN_W + 80 and -80 < sy < SCREEN_H + 80:
                self.r.draw_car(screen, sx, sy, ang, c["color"], c["up"], c["wreck"])

    def _draw_entities(self, screen, lv):
        for bid, bx, by, blv, kind in self.bags:
            if self._visible(bx, by, blv):
                sx, sy = self.w2s(bx, by)
                draw_bag(screen, int(sx), int(sy), kind)
        for p in self.parts:
            if p[6] == lv:
                sx, sy = self.w2s(p[0], p[1])
                pygame.draw.circle(screen, p[5], (int(sx), int(sy)), 3 if p[4] > 0.3 else 2)
        for z in self.zombies.values():
            if self._visible(z["rx"], z["ry"], z["lv"]):
                sx, sy = self.w2s(z["rx"], z["ry"])
                if -40 < sx < SCREEN_W + 40 and -40 < sy < SCREEN_H + 40:
                    if z["kind"] in ANIMALS:
                        draw_animal(screen, sx, sy, z["ra"], z["kind"], z["f"])
                    else:
                        draw_zombie(screen, sx, sy, z["ra"], z["kind"], z["f"])
        for n in self.npcs.values():
            if not self._visible(n["rx"], n["ry"], n["lv"]):
                continue
            sx, sy = self.w2s(n["rx"], n["ry"])
            if not (-40 < sx < SCREEN_W + 40 and -40 < sy < SCREEN_H + 40):
                continue
            draw_player(screen, sx, sy, n["ra"], NPC_COLORS[n["kind"]], n["wpn"], n["vest"], n["helm"])
            col = (255, 100, 90) if n["hostile"] else ((255, 215, 100) if n["kind"] == "trader" else (130, 230, 130))
            ui.text(screen, "%s %s" % (NPC_TITLE[n["kind"]], n["name"]), (sx, sy - 30), 14, col, center=True)
            if n["f"] < 0.99:
                pygame.draw.rect(screen, (40, 0, 0), (sx - 16, sy - 21, 32, 4))
                pygame.draw.rect(screen, (220, 60, 50), (sx - 16, sy - 21, int(32 * n["f"]), 4))
        for p in self.players.values():
            if not p["alive"] or p["car"] >= 0:
                continue
            if p["id"] == self.my_id:
                if not self.me["alive"]:
                    continue
                x, y, lv_, a = self.px, self.py, self.plv, self.aim
                w = self._my_weapon()
                vest = (self.me["eq"].get("vest") or {}).get("id", "")
                helm = (self.me["eq"].get("helmet") or {}).get("id", "")
                cloth = (self.me["eq"].get("cloth") or {}).get("id", "")
                hat = (self.me["eq"].get("hat") or {}).get("id", "")
            else:
                x, y, lv_, a, w, vest, helm = p["rx"], p["ry"], p["lv"], p["ra"], p["wpn"], p["vest"], p["helm"]
                cloth, hat = p.get("cloth", ""), p.get("hat", "")
            if not self._visible(x, y, lv_):
                continue
            sx, sy = self.w2s(x, y)
            draw_player(screen, sx, sy, a, p["color"], w, vest, helm, cloth, hat)
            if p["id"] != self.my_id:
                ui.text(screen, p["name"], (sx, sy - 30), 15, center=True)
                pygame.draw.rect(screen, (40, 0, 0), (sx - 16, sy - 21, 32, 4))
                pygame.draw.rect(screen, (80, 220, 90), (sx - 16, sy - 21, int(32 * p["hp"] / 100), 4))

    def _my_weapon(self):
        me = self.me
        if me["act"] == "gun" and me["eq"].get("gun"):
            return me["eq"]["gun"]["id"]
        return me["eq"]["melee"]["id"] if me["eq"].get("melee") else "fists"

    def _darkness(self):
        h = (self.tod * 24) % 24
        if 6 <= h < 19:
            return 0
        if 19 <= h < 21.5:
            return int(215 * (h - 19) / 2.5)
        if 4.5 <= h < 6:
            return int(215 * (6 - h) / 1.5)
        return 215

    def _draw_darkness(self, screen):
        alpha = self._darkness()
        if self.vlv > 0:
            alpha = max(alpha, 40)
        if alpha <= 0:
            return
        self.dark.fill((5, 8, 22, alpha))
        lights = []
        has_fl = any(it["id"] == "flashlight" for it in self.me["inv"])
        for p in self.players.values():
            if not p["alive"] or p["car"] >= 0:
                continue
            if p["id"] == self.my_id:
                if self.me["alive"]:
                    lights.append((self.px, self.py, self.r.light_big if has_fl else self.r.light))
            elif self._visible(p["rx"], p["ry"], p["lv"]):
                lights.append((p["rx"], p["ry"], self.r.light))
        if self.vlv == 0:
            for c in self.cars.values():
                if c["wreck"]:
                    continue
                driven = c["seats"][0] != -1
                x, y, ang = (self.dcar["x"], self.dcar["y"], self.dcar["ang"]) if (
                        self.driving and c["id"] == self.dcar["id"]) else (c["rx"], c["ry"], c["rang"])
                if driven:
                    big = c["up"].get("lights", 0) > 0
                    d = 200 if big else 140
                    lights.append((x + math.cos(ang) * d, y + math.sin(ang) * d,
                                   self.r.light_big if big else self.r.light_car))
                    lights.append((x, y, self.r.light))
        for e in self.effects:
            if e["k"] in ("flash", "boom"):
                lights.append((e["x"], e["y"], self.r.light))
        if self.vlv == 0:
            tx0, ty0 = int(self.camx // TILE) - 3, int(self.camy // TILE) - 3
            for ty in range(ty0, ty0 + SCREEN_H // TILE + 7):
                for tx in range(tx0, tx0 + SCREEN_W // TILE + 7):
                    if self.world.tile(0, tx, ty) == CAMPFIRE:
                        flick = self.r.light_fire if int(self.time * 6) % 3 else self.r.light
                        lights.append((tx * TILE + 16, ty * TILE + 16, flick))
        for x, y, g in lights:
            sx, sy = self.w2s(x, y)
            r = g.get_width() // 2
            self.dark.blit(g, (sx - r, sy - r), special_flags=pygame.BLEND_RGBA_SUB)
        screen.blit(self.dark, (0, 0))

    def _draw_hud(self, screen):
        me = self.me
        W, H = SCREEN_W, SCREEN_H
        # полоски
        ui.panel(screen, (12, H - 160, 270, 148))
        temp = me.get("temp", 36.6)
        tcol = (90, 160, 255) if temp < 35.8 else ((255, 120, 60) if temp > 37.6 else (120, 220, 140))
        bars = [("Здоровье", me["hp"] / 100, (210, 60, 60), "%d" % me["hp"]),
                ("Сытость", me["food"] / 100, (220, 150, 60), "%d" % me["food"]),
                ("Вода", me["water"] / 100, (70, 150, 230), "%d" % me["water"]),
                ("Выносливость", me["stam"] / 100, (230, 210, 80), "%d" % me["stam"]),
                ("Тело", (temp - 33) / 7, tcol, "%.1f°" % temp)]
        for i, (name, v, col, label) in enumerate(bars):
            y = H - 152 + i * 27
            ui.text(screen, name, (22, y), 15)
            ui.bar(screen, (130, y + 3, 140, 14), v, col)
            ui.text(screen, label, (200, y), 13, center=False)
        warn = []
        if me["bleed"]:
            warn.append(("КРОВОТЕЧЕНИЕ! (H - бинт)", (255, 70, 70)))
        if me.get("inf"):
            warn.append(("ЗАРАЖЕНИЕ! Нужны антибиотики", (190, 255, 90)))
        if temp < 35.5:
            warn.append(("Вы замерзаете! Одежда, костёр или укрытие", (120, 180, 255)))
        elif temp > 37.8:
            warn.append(("Перегрев! Тень, лёгкая одежда, вода", (255, 140, 60)))
        if me["food"] < 15 or me["water"] < 15:
            warn.append(("Голод!" if me["food"] < 15 else "Жажда!", (255, 160, 70)))
        if warn and int(self.time * 3) % 3:
            for i, (t, c) in enumerate(warn[:3]):
                ui.text(screen, t, (20, H - 190 - i * 24), 19, c, bold=True)
        # оружие
        ui.panel(screen, (W - 312, H - 132, 300, 120))
        g, mel = me["eq"].get("gun"), me["eq"].get("melee")
        act = me["act"]
        y = H - 124
        if g:
            d = IT.ITEMS[g["id"]]
            col = (255, 230, 120) if act == "gun" else (150, 150, 150)
            ui.text(screen, "1 " + d["name"], (W - 300, y), 18, col, bold=act == "gun")
            reserve = sum(it["n"] for it in me["inv"] if it["id"] == d["ammo"])
            ui.text(screen, "%d / %d" % (g["ammo"], reserve), (W - 24, y), 22, col, bold=True, right=True)
            if g["mods"]:
                ui.text(screen, IT.mod_names(g), (W - 300, y + 22), 13, (170, 170, 170))
        else:
            ui.text(screen, "1 Нет огнестрела", (W - 300, y), 16, (120, 120, 120))
        md = IT.ITEMS[mel["id"]] if mel else IT.FISTS
        col = (255, 230, 120) if act != "gun" or not g else (150, 150, 150)
        ui.text(screen, "2 " + md["name"] + (" + шипы" if mel and "nails" in mel["mods"] else ""), (W - 300, y + 42),
                18, col, bold=col[0] == 255)
        armor = []
        for slot in ("vest", "helmet"):
            it = me["eq"].get(slot)
            if it:
                armor.append("%s %d%%" % (IT.ITEMS[it["id"]]["name"], 100 * it["dur"] / IT.ITEMS[it["id"]]["dur"]))
        ui.text(screen, ", ".join(armor) if armor else "Без брони", (W - 300, y + 68), 14, (170, 200, 170))
        if me["rl"] >= 0:
            ui.text(screen, "Перезарядка...", (W - 300, y + 88), 14, (240, 200, 80))
            ui.bar(screen, (W - 190, y + 92, 170, 10), me["rl"], (240, 200, 80))
        # время
        h = (self.tod * 24) % 24
        night = self._darkness() > 100
        ui.panel(screen, (12, 12, 290, 92))
        ui.text(screen, "День %d   %02d:%02d %s" % (self.day, int(h), int((h % 1) * 60), "Ночь" if night else ""),
                (22, 18), 20, (180, 190, 255) if night else (255, 240, 180), bold=True)
        where = self._area_name() if self.vbid is None else "%s, этаж %d" % (self._bname(self.vbid), self.vlv + 1)
        ui.text(screen, where, (22, 44), 15, (200, 200, 200))
        wname = {"clear": "ясно", "rain": "дождь", "storm": "буря"}.get(self.weather, "")
        clim = self._climate()
        if self.weather == "rain" and clim == "snow":
            wname = "снегопад"
        elif self.weather == "storm":
            wname = {"snow": "метель", "desert": "песчаная буря"}.get(clim, "гроза")
        amb = me.get("amb", 20)
        ui.text(screen, "Воздух %+d°C, %s%s" % (amb, wname, "  |  у костра" if me.get("fire") else ""), (22, 63), 14,
                (150, 200, 255) if amb < 5 else ((255, 170, 90) if amb > 30 else (200, 220, 200)))
        ui.text(screen, "Убито зомби: %d" % me["kills"], (22, 82), 13, (200, 160, 160))
        self._draw_waypoint(screen)
        # машина
        if me["car"] >= 0 and me["car"] in self.cars:
            c = self.cars[me["car"]]
            ui.panel(screen, (W // 2 - 160, H - 92, 320, 80))
            spd = abs(self.dcar["spd"]) if self.driving else abs(c["spd"])
            ui.text(screen, "%d км/ч" % int(spd * 0.36), (W // 2 - 150, H - 86), 24, bold=True)
            ui.text(screen, "Водитель" if me["seat"] == 0 else "Пассажир", (W // 2 + 150, H - 84), 15,
                    (180, 180, 180), right=True)
            ui.text(screen, "Топливо", (W // 2 - 150, H - 56), 14)
            ui.bar(screen, (W // 2 - 80, H - 53, 230, 10), c["fuel"] / c["mfuel"], (230, 170, 40))
            ui.text(screen, "Прочность", (W // 2 - 150, H - 38), 14)
            ui.bar(screen, (W // 2 - 80, H - 35, 230, 10), c["hp"] / c["mhp"], (210, 70, 60))
        # подсказка
        if self.hint and not (self.inv_open or self.shop_open or self.trade_ui):
            ui.text(screen, self.hint[0], (W // 2, H - 120 if me["car"] >= 0 else H - 60), 20, (255, 255, 255),
                    center=True)
        # лента
        y = H - 300
        for text, t, col in self.feed[-6:]:
            ui.text(screen, text, (16, y), 16, col)
            y += 20
        self._draw_minimap(screen)

    def _bname(self, b):
        names = {"house": "Дом", "apartment": "Многоэтажка", "farmhouse": "Фермерский дом", "cabin": "Хижина",
                 "shack": "Палатка"}
        return names.get(b.kind) or KIND_LABEL.get(b.kind, "Здание").capitalize()

    def _draw_minimap(self, screen):
        S = 170
        span = 85
        cx, cy = int(self.vx // TILE), int(self.vy // TILE)
        x0, y0 = cx - span // 2, cy - span // 2
        img = pygame.transform.scale(self.r.area_map(x0, y0, span, span), (S, S))
        X, Y = SCREEN_W - S - 12, 12
        screen.blit(img, (X, Y))
        pygame.draw.rect(screen, (0, 0, 0), (X, Y, S, S), 2)
        k = S / span
        for p in self.players.values():
            if p["id"] != self.my_id and not self.settings.get("map_marks", True):
                continue
            if not p["alive"]:
                continue
            x, y = (self.px, self.py) if p["id"] == self.my_id and self.me["alive"] else (p["rx"], p["ry"])
            mx, my = X + (x / TILE - x0) * k, Y + (y / TILE - y0) * k
            if X <= mx <= X + S and Y <= my <= Y + S:
                pygame.draw.circle(screen, (255, 255, 255), (int(mx), int(my)), 4)
                pygame.draw.circle(screen, p["color"], (int(mx), int(my)), 3)
        for c in self.cars.values():
            mx, my = X + (c["rx"] / TILE - x0) * k, Y + (c["ry"] / TILE - y0) * k
            if X <= mx <= X + S and Y <= my <= Y + S and not c["wreck"]:
                pygame.draw.rect(screen, (230, 230, 230), (int(mx) - 2, int(my) - 1, 4, 3))
        for dx, dy in self.drops:
            mx, my = X + (dx / TILE - x0) * k, Y + (dy / TILE - y0) * k
            self._icon_drop(screen, *self._clamp_marker(mx, my, X, Y, S, S), 6)
        if self.waypoint:
            mx, my = X + (self.waypoint[0] - x0) * k, Y + (self.waypoint[1] - y0) * k
            self._icon_flag(screen, *self._clamp_marker(mx, my, X, Y, S, S), 0.8)
        ui.text(screen, "N", (X + S // 2, Y + 3), 13, (255, 255, 255), center=True)
        ui.text(screen, "M - карта", (X + S // 2, Y + S + 10), 13, (200, 200, 200), center=True)

    @staticmethod
    def _clamp_marker(mx, my, X, Y, W, H):
        return max(X + 6, min(X + W - 6, mx)), max(Y + 6, min(Y + H - 6, my))

    # ---------- значки карты ----------
    @staticmethod
    def _icon_drop(s, x, y, r=8):
        pygame.draw.circle(s, (250, 210, 60), (int(x), int(y) - r // 2), r, draw_top_left=True, draw_top_right=True)
        pygame.draw.line(s, (250, 250, 250), (x - r, y - r // 2), (x, y + r), 1)
        pygame.draw.line(s, (250, 250, 250), (x + r, y - r // 2), (x, y + r), 1)
        pygame.draw.rect(s, (90, 110, 60), (x - 3, y + r - 3, 6, 6))

    @staticmethod
    def _icon_flag(s, x, y, k=1.0):
        pygame.draw.line(s, (30, 30, 30), (x, y), (x, y - 22 * k), 3)
        pygame.draw.polygon(s, (230, 40, 40), [(x, y - 22 * k), (x + 16 * k, y - 16 * k), (x, y - 10 * k)])
        pygame.draw.circle(s, (255, 255, 255), (int(x), int(y)), 3)

    @staticmethod
    def _icon_camp(s, x, y, kind):
        if kind == "trader":
            pygame.draw.circle(s, (30, 30, 30), (int(x), int(y)), 11)
            pygame.draw.circle(s, (240, 200, 60), (int(x), int(y)), 10)
            ui.text(s, "$", (x, y - 1), 15, (60, 40, 0), bold=True, center=True, shadow=False)
        elif kind == "bandits":
            pygame.draw.circle(s, (30, 30, 30), (int(x), int(y)), 11)
            pygame.draw.circle(s, (190, 40, 40), (int(x), int(y)), 10)
            pygame.draw.line(s, (255, 255, 255), (x - 5, y - 5), (x + 5, y + 5), 3)
            pygame.draw.line(s, (255, 255, 255), (x + 5, y - 5), (x - 5, y + 5), 3)
        else:
            pts = [(x + math.cos(a) * (11 if i % 2 == 0 else 5), y + math.sin(a) * (11 if i % 2 == 0 else 5))
                   for i, a in enumerate([-math.pi / 2 + i * math.pi / 5 for i in range(10)])]
            pygame.draw.polygon(s, (30, 30, 30), [(px + 1, py + 1) for px, py in pts])
            pygame.draw.polygon(s, (110, 170, 80), pts)

    def _map_rect(self):
        return pygame.Rect(30, 50, 930, 640)

    def _map_view(self):
        r = self._map_rect()
        z = MAP_ZOOMS[self.map_zoom]
        if self.map_center is None:
            cx, cy = self.vx / TILE, self.vy / TILE
        else:
            cx, cy = self.map_center
        return r, z, cx - r.w / z / 2, cy - r.h / z / 2

    def _map_event(self, e):
        r, z, x0, y0 = self._map_view()
        if e.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if r.collidepoint((mx, my)):
                wx, wy = x0 + (mx - r.x) / z, y0 + (my - r.y) / z
                self.map_zoom = max(0, min(len(MAP_ZOOMS) - 1, self.map_zoom + (1 if e.y > 0 else -1)))
                nz = MAP_ZOOMS[self.map_zoom]
                self.map_center = (wx - (mx - r.x) / nz + r.w / nz / 2, wy - (my - r.y) / nz + r.h / nz / 2)
            return True
        if e.type == pygame.MOUSEBUTTONDOWN and r.collidepoint(e.pos):
            if e.button == 1:
                self.map_drag = True
                if self.map_center is None:
                    self.map_center = (self.vx / TILE, self.vy / TILE)
            elif e.button == 3:
                wx, wy = x0 + (e.pos[0] - r.x) / z, y0 + (e.pos[1] - r.y) / z
                if self.waypoint and math.hypot(self.waypoint[0] - wx, self.waypoint[1] - wy) * z < 14:
                    self.waypoint = None
                else:
                    self.waypoint = (wx, wy)
            return True
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.map_drag = False
            return True
        if e.type == pygame.MOUSEMOTION and self.map_drag:
            cx, cy = self.map_center
            self.map_center = (cx - e.rel[0] / z, cy - e.rel[1] / z)
            return True
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_c, pygame.K_SPACE):
            self.map_center = None
            return True
        if e.type == pygame.KEYDOWN and e.key == pygame.K_DELETE:
            self.waypoint = None
            return True
        return False

    def _draw_map(self, screen):
        r, z, x0, y0 = self._map_view()
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 170))
        screen.blit(ov, (0, 0))
        ui.panel(screen, (r.x - 8, r.y - 38, r.w + 16 + 290, r.h + 46), alpha=250)
        tw, th = int(r.w / z) + 2, int(r.h / z) + 2
        tx0, ty0 = int(math.floor(x0)), int(math.floor(y0))
        img = self.r.area_map(tx0, ty0, tw, th)
        img = pygame.transform.scale(img, (int(tw * z), int(th * z)))
        screen.set_clip(r)
        screen.blit(img, (r.x - (x0 - tx0) * z, r.y - (y0 - ty0) * z))

        def w2m(tx, ty):
            return r.x + (tx - x0) * z, r.y + (ty - y0) * z

        labels = []
        for ccy in range(ty0 >> 5, ((ty0 + th) >> 5) + 1):
            for ccx in range(tx0 >> 5, ((tx0 + tw) >> 5) + 1):
                c = self.world.chunks.get((ccx, ccy))
                if not c:
                    continue
                mx, my = w2m(ccx * CS + 16, ccy * CS + 16)
                if c.biome in ("trader", "bandits", "military"):
                    self._icon_camp(screen, mx, my, c.biome)
                    if z >= 1.5:
                        labels.append((c.label, mx, my + 16, (255, 230, 150)))
                if z >= 2.5:
                    for b in c.buildings:
                        lab = KIND_LABEL.get(b.kind)
                        if lab and b.kind not in ("barracks", "barn"):
                            labels.append((lab, *w2m(b.x + b.w / 2, b.y + b.h / 2), (240, 240, 240)))
        for lab, mx, my, col in labels:
            ui.text(screen, lab, (mx, my), 12 if z < 4 else 14, col, center=True)
        for dx, dy in self.drops:
            self._icon_drop(screen, *w2m(dx / TILE, dy / TILE), 10)
        if self.waypoint:
            mx, my = w2m(*self.waypoint)
            self._icon_flag(screen, mx, my, 1.2)
        for p in self.players.values():
            if not p["alive"] or (p["id"] != self.my_id and not self.settings.get("map_marks", True)):
                continue
            me = p["id"] == self.my_id
            x, y = (self.px, self.py) if me else (p["rx"], p["ry"])
            mx, my = w2m(x / TILE, y / TILE)
            if me:
                a = self.aim
                pts = [(mx + math.cos(a) * 12, my + math.sin(a) * 12), (mx + math.cos(a + 2.5) * 8, my + math.sin(a + 2.5) * 8),
                       (mx + math.cos(a - 2.5) * 8, my + math.sin(a - 2.5) * 8)]
                pygame.draw.polygon(screen, (255, 255, 255), pts)
                pygame.draw.polygon(screen, p["color"], pts, 2)
            else:
                pygame.draw.circle(screen, (255, 255, 255), (int(mx), int(my)), 7)
                pygame.draw.circle(screen, p["color"], (int(mx), int(my)), 6)
            ui.text(screen, p["name"], (mx, my - 18), 13, center=True)
        screen.set_clip(None)
        pygame.draw.rect(screen, (0, 0, 0), r, 2)
        ui.text(screen, "Карта мира", (r.x, r.y - 32), 22, (255, 220, 150), bold=True)
        ui.text(screen, "Колесо - масштаб x%g   ЛКМ - двигать   ПКМ - метка   C - к себе   M - закрыть" % z,
                (r.right, r.y - 28), 14, (200, 200, 200), right=True)
        # легенда
        lx, ly = r.right + 22, r.y + 4
        ui.text(screen, "Легенда", (lx, ly), 19, (255, 220, 150), bold=True)
        ly += 32
        items = [((62, 110, 52), "Луга и леса"), ((30, 75, 35), "Деревья"), ((214, 190, 128), "Пустыня"),
                 ((226, 232, 240), "Снега"), ((40, 90, 160), "Вода / реки"), ((170, 210, 235), "Лёд"),
                 ((58, 58, 62), "Дороги"), ((130, 105, 70), "Грунтовки"), ((130, 120, 55), "Поля"),
                 ((150, 70, 50), "Здания"), ((18, 20, 24), "Не исследовано")]
        for col, name in items:
            pygame.draw.rect(screen, col, (lx, ly + 2, 18, 14))
            pygame.draw.rect(screen, (0, 0, 0), (lx, ly + 2, 18, 14), 1)
            ui.text(screen, name, (lx + 28, ly), 15)
            ly += 23
        ly += 8
        for kind, name in (("trader", "Торговцы"), ("bandits", "Бандиты"), ("military", "Военная база")):
            self._icon_camp(screen, lx + 9, ly + 9, kind)
            ui.text(screen, name, (lx + 28, ly), 15)
            ly += 28
        self._icon_drop(screen, lx + 9, ly + 6, 9)
        ui.text(screen, "Сброс груза", (lx + 28, ly), 15)
        ly += 28
        self._icon_flag(screen, lx + 6, ly + 18, 0.8)
        ui.text(screen, "Ваша метка", (lx + 28, ly), 15)
        ly += 34
        cx, cy = int(self.vx // TILE), int(self.vy // TILE)
        ui.text(screen, "Вы: %d, %d" % (cx, cy), (lx, ly), 15, (200, 200, 200))
        ly += 22
        ui.text(screen, "Сейчас: %s" % self._area_name(), (lx, ly), 15, (200, 200, 200))
        if self.waypoint:
            ly += 22
            d = math.hypot(self.waypoint[0] - self.vx / TILE, self.waypoint[1] - self.vy / TILE)
            ui.text(screen, "До метки: %d м" % d, (lx, ly), 15, (255, 140, 120))

    def _draw_waypoint(self, screen):
        if not self.waypoint or not self.me["alive"]:
            return
        wx, wy = self.waypoint[0] * TILE, self.waypoint[1] * TILE
        d = math.hypot(wx - self.px, wy - self.py) / TILE
        if d < 3:
            self.waypoint = None
            self.add_feed("Вы на месте метки", (140, 230, 120))
            return
        sx, sy = self.w2s(wx, wy)
        if 0 <= sx <= SCREEN_W and 0 <= sy <= SCREEN_H:
            self._icon_flag(screen, sx, sy, 1.2)
            ui.text(screen, "%d м" % d, (sx, sy + 12), 14, (255, 200, 190), center=True)
            return
        a = math.atan2(sy - SCREEN_H / 2, sx - SCREEN_W / 2)
        ex = SCREEN_W / 2 + math.cos(a) * (SCREEN_W / 2 - 50)
        ey = SCREEN_H / 2 + math.sin(a) * (SCREEN_H / 2 - 50)
        ex, ey = max(40, min(SCREEN_W - 40, ex)), max(120, min(SCREEN_H - 180, ey))
        pts = [(ex + math.cos(a) * 18, ey + math.sin(a) * 18), (ex + math.cos(a + 2.4) * 12, ey + math.sin(a + 2.4) * 12),
               (ex + math.cos(a - 2.4) * 12, ey + math.sin(a - 2.4) * 12)]
        pygame.draw.polygon(screen, (230, 40, 40), pts)
        pygame.draw.polygon(screen, (255, 255, 255), pts, 2)
        ui.text(screen, "%d м" % d, (ex - math.cos(a) * 22, ey - math.sin(a) * 22), 14, (255, 220, 210), center=True)

    def _climate(self):
        c = self.world.chunks.get((int(self.vx // TILE) >> 5, int(self.vy // TILE) >> 5))
        return c.climate if c else "temperate"

    def _draw_weather(self, screen, dt):
        """Дождь / снегопад / песчаная буря - только на улице."""
        if self.vlv > 0 or self.vbid is not None:
            self.wparts = []
            return
        clim = self._climate()
        kind = None
        n = 0
        if clim == "snow":
            kind, n = "snow", (6 if self.weather != "clear" else 2)
        elif self.weather in ("rain", "storm"):
            kind = "sand" if clim == "desert" and self.weather == "storm" else ("rain" if clim != "desert" else None)
            n = 9 if self.weather == "storm" else 5
        if kind == "sand" or (kind == "snow" and self.weather == "storm"):
            ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            ov.fill((205, 160, 90, 125) if kind == "sand" else (230, 235, 245, 90))
            screen.blit(ov, (0, 0))
        elif kind == "rain":
            ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            ov.fill((20, 30, 50, 45))
            screen.blit(ov, (0, 0))
        for _ in range(n if kind else 0):
            if kind == "rain":
                self.wparts.append([random.uniform(0, SCREEN_W + 200), -10, -120, 900, kind])
            elif kind == "snow":
                self.wparts.append([random.uniform(0, SCREEN_W), -5, random.uniform(-30, 30), random.uniform(50, 110),
                                    kind])
            else:
                self.wparts.append([-10, random.uniform(0, SCREEN_H), random.uniform(500, 800), random.uniform(-40, 40),
                                    kind])
        alive = []
        for p in self.wparts:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            if -20 <= p[0] <= SCREEN_W + 220 and -20 <= p[1] <= SCREEN_H + 20:
                alive.append(p)
                if p[4] == "rain":
                    pygame.draw.line(screen, (170, 190, 230), (p[0], p[1]), (p[0] - 3, p[1] + 14), 1)
                elif p[4] == "snow":
                    pygame.draw.circle(screen, (255, 255, 255), (int(p[0]), int(p[1])), 2)
                else:
                    pygame.draw.line(screen, (220, 180, 110), (p[0], p[1]), (p[0] - 10, p[1]), 2)
        self.wparts = alive[-700:]

    # ---------- инвентарь ----------
    def _slot(self, screen, rect, it, label=None):
        r = pygame.Rect(rect)
        hover = r.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(screen, (55, 58, 66) if hover else (38, 40, 46), r, border_radius=5)
        pygame.draw.rect(screen, (90, 92, 104), r, 1, border_radius=5)
        if label and not it:
            ui.text(screen, label, r.center, 11, (120, 120, 130), center=True, shadow=False)
        if it:
            draw_icon(screen, r, it["id"])
            if it["n"] > 1:
                ui.text(screen, str(it["n"]), (r.right - 4, r.bottom - 18), 14, right=True)
            d = IT.ITEMS[it["id"]]
            if d["kind"] == "gun":
                ui.text(screen, "%d/%d" % (it["ammo"], IT.max_mag(it)), (r.x + 3, r.bottom - 16), 12,
                        (240, 220, 120))
            if "dur" in it:
                ui.bar(screen, (r.x + 4, r.bottom - 6, r.w - 8, 3), it["dur"] / d["dur"], (90, 200, 110))
            if it.get("mods"):
                pygame.draw.circle(screen, (90, 180, 255), (r.right - 6, r.y + 6), 4)
            if hover:
                self.tip = (it, pygame.mouse.get_pos())

    def _draw_inventory(self, screen):
        me = self.me
        X, Y = 40, 70
        ui.panel(screen, (X, Y, 560, 590), alpha=235)
        ui.text(screen, "Инвентарь  %d/%d" % (len(me["inv"]), me["slots"]), (X + 16, Y + 10), 22, bold=True)
        for i, (slot, label) in enumerate(EQ_SLOTS):
            r = pygame.Rect(X + 16 + i * 76, Y + 52, 70, SLOT)
            it = me["eq"].get(slot)
            ui.text(screen, label, (r.centerx, Y + 44), 12, (170, 170, 180), center=True)
            self._slot(screen, r, it, "пусто")
            if it:
                self.zones.append((r, 1, lambda s=slot: self.link.send({"t": "uneq", "s": s})))
        cols = 8
        gy = Y + 130
        cont_open = self.cont is not None
        for i in range(me["slots"]):
            r = pygame.Rect(X + 16 + (i % cols) * (SLOT + GAP), gy + (i // cols) * (SLOT + GAP), SLOT, SLOT)
            it = me["inv"][i] if i < len(me["inv"]) else None
            self._slot(screen, r, it)
            if it:
                if cont_open and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    self.zones.append((r, 1, lambda i=i: self.link.send({"t": "put", "i": i})))
                else:
                    self.zones.append((r, 1, lambda i=i: self.link.send({"t": "use", "i": i})))
                self.zones.append((r, 3, lambda i=i: self.link.send({"t": "drop", "i": i})))
        help_y = Y + 520
        if cont_open:
            ui.text(screen, "ЛКМ - переложить в контейнер,  Shift+ЛКМ - использовать", (X + 16, help_y), 14,
                    (190, 190, 190))
        else:
            ui.text(screen, "ЛКМ - использовать / надеть,  ПКМ - выбросить", (X + 16, help_y), 14, (190, 190, 190))
        ui.text(screen, "Клик по экипировке - снять.  Tab - закрыть", (X + 16, help_y + 20), 14, (190, 190, 190))
        ui.text(screen, "Модификации оружия ставятся кликом (нужно экипированное оружие)", (X + 16, help_y + 40),
                14, (150, 150, 160))
        if cont_open:
            c = self.cont
            CX = 640
            ui.panel(screen, (CX, Y, 560, 590), alpha=235)
            ui.text(screen, c["n"], (CX + 16, Y + 10), 22, bold=True)
            if not c["items"]:
                ui.text(screen, "Пусто", (CX + 16, Y + 60), 18, (150, 150, 150))
            for i, it in enumerate(c["items"][:56]):
                r = pygame.Rect(CX + 16 + (i % cols) * (SLOT + GAP), Y + 52 + (i // cols) * (SLOT + GAP), SLOT, SLOT)
                self._slot(screen, r, it)
                self.zones.append((r, 1, lambda i=i: self.link.send({"t": "take", "i": i})))
            br = pygame.Rect(CX + 16, Y + 530, 200, 40)
            ui.Button(br, "Взять всё (Space)", size=18).draw(screen)
            self.zones.append((br, 1, lambda: self.link.send({"t": "takeall"})))
            if pygame.key.get_pressed()[pygame.K_SPACE] and self.time - getattr(self, "_ta", 0) > 0.4:
                self._ta = self.time
                self.link.send({"t": "takeall"})

    def _draw_tip(self, screen, it, pos):
        d = IT.ITEMS[it["id"]]
        lines = [(IT.item_label(it), (255, 230, 150))]
        if d.get("desc"):
            lines.append((d["desc"], (210, 210, 210)))
        k = d["kind"]
        if k == "gun":
            lines.append(("Урон %d%s, магазин %d" % (d["dmg"], " x%d" % d["pellets"] if "pellets" in d else "",
                                                     IT.max_mag(it)), (200, 200, 200)))
        elif k == "melee":
            lines.append(("Урон %d" % d["dmg"], (200, 200, 200)))
        if it.get("mods"):
            lines.append(("Модули: " + IT.mod_names(it), (120, 190, 255)))
        for key, name in (("food", "Еда"), ("water", "Вода"), ("hp", "Здоровье")):
            if d.get(key) and k in ("food", "drink", "med"):
                lines.append(("%s %+d" % (name, d[key]), (160, 220, 160)))
        w = max(ui.render(s, 15).get_width() for s, _ in lines) + 20
        h = len(lines) * 20 + 12
        x, y = pos[0] + 16, pos[1] + 16
        x = min(x, SCREEN_W - w - 4)
        y = min(y, SCREEN_H - h - 4)
        ui.panel(screen, (x, y, w, h), (15, 15, 18), 245)
        for i, (s, col) in enumerate(lines):
            ui.text(screen, s, (x + 10, y + 6 + i * 20), 15, col)

    # ---------- строительство ----------
    def _mouse_tile(self):
        mx, my = pygame.mouse.get_pos()
        return int((mx + self.camx) // TILE), int((my + self.camy) // TILE)

    def _count(self, iid):
        return sum(it["n"] for it in self.me["inv"] if it["id"] == iid)

    def _draw_ghost(self, screen):
        name, tile, cost = BUILD_D[self.build_sel]
        tx, ty = self._mouse_tile()
        cur = self.world.tile(self.plv, tx, ty)
        ok = math.hypot(tx * TILE + 16 - self.px, ty * TILE + 16 - self.py) <= 4.6 * TILE and cur in PLACEABLE
        if self.build_sel == "floor" and cur not in (GRASS, DIRT, FIELD, DIRTROAD):
            ok = False
        enough = all(self._count(k) >= n for k, n in cost.items())
        x, y = tx * TILE - self.camx, ty * TILE - self.camy
        g = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        g.fill((80, 220, 90, 110) if ok and enough else (230, 70, 60, 110))
        screen.blit(g, (x, y))
        pygame.draw.rect(screen, (255, 255, 255), (x, y, TILE, TILE), 2)
        pygame.draw.circle(screen, (255, 255, 255), (int(self.px - self.camx), int(self.py - self.camy)),
                           int(4.6 * TILE), 1)
        need = ", ".join("%s %d/%d" % (IT.ITEMS[k]["name"], self._count(k), n) for k, n in cost.items())
        ui.panel(screen, (SCREEN_W // 2 - 300, 90, 600, 54))
        ui.text(screen, "Стройка: %s  (%s)" % (name, need), (SCREEN_W // 2, 104), 17,
                (140, 230, 120) if enough else (240, 130, 100), center=True)
        ui.text(screen, "ЛКМ - построить,  ПКМ/Esc - отмена,  X - разобрать свою постройку,  B - меню", (SCREEN_W // 2, 128),
                14, (200, 200, 200), center=True)

    def _draw_build(self, screen):
        X, Y, W, H = 140, 70, 1000, 580
        ui.panel(screen, (X, Y, W, H), alpha=240)
        ui.text(screen, "Строительство и крафт (B)", (X + 20, Y + 12), 24, bold=True)
        ui.text(screen, "Дерево: %d   Камень: %d   Ягоды: %d" % (self._count("wood"), self._count("stone"),
                                                              self._count("berries")),
                (X + W - 20, Y + 18), 17, (230, 210, 150), right=True)
        y = Y + 60
        ui.text(screen, "Постройки", (X + 20, y), 20, (255, 220, 150), bold=True)
        y += 32
        for key, name, tile, cost in BUILDS:
            enough = all(self._count(k) >= n for k, n in cost.items())
            ui.text(screen, name, (X + 20, y + 6), 17)
            need = ", ".join("%s %d" % (IT.ITEMS[k]["name"], n) for k, n in cost.items())
            ui.text(screen, need, (X + 290, y + 8), 14, (140, 230, 120) if enough else (230, 120, 100))
            br = pygame.Rect(X + 430, y, 90, 30)
            ui.Button(br, "Выбрать", size=15, color=(50, 110, 60) if enough else (70, 60, 60)).draw(screen)
            self.zones.append((br, 1, lambda k=key: self._select_build(k)))
            y += 38
        x0, y = X + 560, Y + 60
        ui.text(screen, "Крафт", (x0, y), 20, (255, 220, 150), bold=True)
        y += 32
        for iid, cost in IT.CRAFTS:
            enough = all(self._count(k) >= n for k, n in cost.items())
            r = pygame.Rect(x0, y, 40, 40)
            pygame.draw.rect(screen, (38, 40, 46), r, border_radius=5)
            draw_icon(screen, r, iid)
            ui.text(screen, IT.ITEMS[iid]["name"], (x0 + 50, y + 2), 16)
            need = ", ".join("%s %d" % (IT.ITEMS[k]["name"], n) for k, n in cost.items())
            ui.text(screen, need, (x0 + 50, y + 22), 13, (140, 230, 120) if enough else (230, 120, 100))
            br = pygame.Rect(x0 + 310, y + 5, 100, 30)
            ui.Button(br, "Создать", size=15, color=(50, 110, 60) if enough else (70, 60, 60)).draw(screen)
            self.zones.append((br, 1, lambda i=iid: self.link.send({"t": "craft", "r": i})))
            y += 50
        tips = ["Дерево - бейте деревья (лучше топором), камень - бейте камни (лучше киркой).",
                "Ягоды - E у ягодного куста, кусты отрастают на следующий день.",
                "Деревянная дверь не пускает зомби. Кровать - точка возрождения. Всё сохраняется."]
        for i, t in enumerate(tips):
            ui.text(screen, t, (X + 20, Y + H - 80 + i * 22), 14, (180, 180, 190))

    def _select_build(self, key):
        self.build_sel = key
        self.build_ui = False

    # ---------- торговля ----------
    def _draw_trade(self, screen):
        me, tr = self.me, self.me["trade"]
        money = sum(it["n"] for it in me["inv"] if it["id"] == "money")
        cols, step = 8, SLOT + 20
        for side in (0, 1):
            X = 40 if side == 0 else 640
            ui.panel(screen, (X, 50, 560, 620), alpha=240)
            if side == 0:
                ui.text(screen, "Ваши вещи - продать", (X + 16, 60), 22, bold=True)
                ui.text(screen, "Деньги: %d" % money, (X + 544, 64), 18, (140, 230, 120), right=True)
                items = me["inv"]
            else:
                ui.text(screen, tr["name"], (X + 16, 60), 22, (255, 215, 100), bold=True)
                ui.text(screen, "Деньги торговца: %d" % tr["money"], (X + 544, 64), 18, (140, 230, 120), right=True)
                items = tr["items"]
            for i, it in enumerate(items[:48]):
                r = pygame.Rect(X + 16 + (i % cols) * (SLOT + GAP), 100 + (i // cols) * step, SLOT, SLOT)
                self._slot(screen, r, it)
                q = IT.trade_qty(it)
                if it["id"] == "money":
                    continue
                if side == 0:
                    pr = IT.sell_price(it["id"]) * q
                    ui.text(screen, "+%d" % pr, (r.centerx, r.bottom + 9), 13, (140, 230, 120), center=True)
                    self.zones.append((r, 1, lambda i=i: self.link.send({"t": "sell", "i": i})))
                else:
                    pr = IT.price(it["id"]) * q
                    ui.text(screen, "%d" % pr, (r.centerx, r.bottom + 9), 13,
                            (240, 220, 120) if pr <= money else (230, 110, 90), center=True)
                    self.zones.append((r, 1, lambda i=i: self.link.send({"t": "buy", "i": i})))
        ui.text(screen, "ЛКМ по своей вещи - продать, по товару торговца - купить (патроны по 10 шт.)",
                (SCREEN_W // 2, 640), 15, (200, 200, 200), center=True)
        ui.text(screen, "Esc / E - закрыть", (SCREEN_W // 2, 660), 14, (160, 160, 160), center=True)

    # ---------- мастерская ----------
    def _draw_shop(self, screen):
        me = self.me
        X, Y, W, H = 90, 60, 1100, 600
        ui.panel(screen, (X, Y, W, H), alpha=240)
        ui.text(screen, "Верстак - тюнинг машины и оружия", (X + 20, Y + 12), 24, bold=True)
        has_tools = any(it["id"] == "tools" for it in me["inv"])
        ui.text(screen, "Инструменты: " + ("есть" if has_tools else "НЕТ (найдите в гаражах и складах)"),
                (X + W - 20, Y + 18), 16, (120, 220, 120) if has_tools else (240, 110, 90), right=True)
        cnt = {}
        for it in me["inv"]:
            cnt[it["id"]] = cnt.get(it["id"], 0) + it["n"]
        car, cd = None, 420
        for c in self.cars.values():
            d = math.hypot(c["rx"] - self.px, c["ry"] - self.py)
            if not c["wreck"] and d < cd and self.plv == 0:
                car, cd = c, d
        x0, y = X + 20, Y + 56
        ui.text(screen, "Машина", (x0, y), 22, (255, 220, 150), bold=True)
        y += 32
        if not car:
            ui.text(screen, "Подгоните машину поближе к верстаку", (x0, y), 17, (180, 180, 180))
        else:
            ui.text(screen, "Прочность %d/%d    Топливо %d/%d" % (car["hp"], car["mhp"], car["fuel"], car["mfuel"]),
                    (x0, y), 16)
            pr = pygame.Rect(x0 + 380, y - 4, 140, 28)
            ui.Button(pr, "Перекрасить", size=16).draw(screen)
            self.zones.append((pr, 1, lambda cid=car["id"]: self.link.send({"t": "paint", "c": cid})))
            y += 36
            for key, name, desc, costs in IT.CAR_UPG:
                lvl = car["up"].get(key, 0)
                ui.text(screen, "%s  [%d/%d]" % (name, lvl, len(costs)), (x0, y), 17, bold=True)
                ui.text(screen, desc, (x0, y + 20), 13, (160, 160, 170))
                if lvl < len(costs):
                    cx = x0 + 215
                    ok = has_tools
                    for iid, n in costs[lvl].items():
                        have = cnt.get(iid, 0)
                        ok = ok and have >= n
                        cx += ui.text(screen, "%s %d/%d  " % (IT.ITEMS[iid]["name"], have, n), (cx, y + 22), 13,
                                      (120, 220, 120) if have >= n else (230, 110, 90))
                    br = pygame.Rect(x0 + 450, y + 2, 100, 30)
                    ui.Button(br, "Улучшить", size=16, color=(50, 110, 60) if ok else (70, 60, 60)).draw(screen)
                    self.zones.append((br, 1, lambda k=key, cid=car["id"]: self.link.send(
                        {"t": "upg", "c": cid, "p": k})))
                else:
                    ui.text(screen, "Максимум", (x0 + 450, y + 8), 15, (240, 200, 70))
                y += 48
            rk = next((i for i, it in enumerate(me["inv"]) if it["id"] == "repair_kit"), None)
            fk = next((i for i, it in enumerate(me["inv"]) if it["id"] == "fuel"), None)
            for label, idx, dx in (("Починить (ремкомплект)", rk, 0), ("Заправить (канистра)", fk, 270)):
                br = pygame.Rect(x0 + dx, y + 6, 250, 32)
                ui.Button(br, label, size=16, enabled=idx is not None).draw(screen)
                if idx is not None:
                    self.zones.append((br, 1, lambda i=idx: self.link.send({"t": "use", "i": i})))
        # оружие
        x0, y = X + 580, Y + 56
        ui.text(screen, "Оружие", (x0, y), 22, (255, 220, 150), bold=True)
        y += 34
        for slot, kind_name in (("gun", "Огнестрел"), ("melee", "Ближний бой")):
            w = me["eq"].get(slot)
            ui.text(screen, "%s: %s" % (kind_name, IT.ITEMS[w["id"]]["name"] if w else "не экипирован"), (x0, y), 18,
                    bold=True)
            y += 28
            if w:
                for mid in w.get("mods", []):
                    ui.text(screen, "+ " + IT.ITEMS[mid]["name"], (x0 + 10, y + 4), 16, (120, 190, 255))
                    br = pygame.Rect(x0 + 300, y, 100, 26)
                    ui.Button(br, "Снять", size=15).draw(screen)
                    self.zones.append((br, 1, lambda s=slot, m=mid: self.link.send({"t": "modoff", "s": s, "m": m})))
                    y += 30
                for i, it in enumerate(me["inv"]):
                    d = IT.ITEMS[it["id"]]
                    if d["kind"] == "mod" and d["for_kind"] == slot and it["id"] not in w.get("mods", []):
                        ui.text(screen, d["name"] + " - " + d["desc"], (x0 + 10, y + 4), 15, (200, 200, 200))
                        br = pygame.Rect(x0 + 400, y, 110, 26)
                        ui.Button(br, "Установить", size=15, color=(50, 110, 60)).draw(screen)
                        self.zones.append((br, 1, lambda i=i: self.link.send({"t": "use", "i": i})))
                        y += 30
            y += 16
        ui.text(screen, "Модификации: Глушитель, Увелич. магазин, Прицел (огнестрел), Шипы (ближний бой)",
                (X + 580, Y + H - 60), 13, (150, 150, 160))
        ui.text(screen, "Esc - закрыть", (X + W - 20, Y + H - 30), 15, (180, 180, 180), right=True)

    # ---------- смерть / пауза ----------
    def _draw_dead(self, screen):
        me = self.me
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((40, 0, 0, 110))
        screen.blit(ov, (0, 0))
        cx = SCREEN_W // 2
        if self.over:
            ui.text(screen, "ИГРА ОКОНЧЕНА", (cx, 220), 56, (230, 60, 50), bold=True, center=True)
            ui.text(screen, "Прожито дней: %d   Убито зомби: %d" % (self.day, me["kills"]), (cx, 290), 24,
                    center=True)
        else:
            ui.text(screen, "ВЫ ПОГИБЛИ", (cx, 200), 56, (230, 60, 50), bold=True, center=True)
            ui.text(screen, "Убито зомби: %d" % me["kills"], (cx, 260), 22, center=True)
            if me["rsp"] > 0:
                ui.text(screen, "Возрождение через %d..." % math.ceil(me["rsp"]), (cx, 310), 24, center=True)
            elif me["rsp"] == 0:
                br = pygame.Rect(cx - 130, 300, 260, 50)
                ui.Button(br, "Возродиться", size=24, color=(50, 110, 60)).draw(screen)
                self.zones.append((br, 1, lambda: self.link.send({"t": "respawn"})))
            tgt = self.players.get(self.spec)
            if tgt:
                ui.text(screen, "Наблюдение: %s (ЛКМ - следующий)" % tgt["name"], (cx, SCREEN_H - 200), 18,
                        center=True)
        br = pygame.Rect(cx - 130, 370, 260, 46)
        ui.Button(br, "Выйти в меню", size=22).draw(screen)
        self.zones.append((br, 1, lambda: self._leave()))

    def _draw_pause(self, screen):
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        screen.blit(ov, (0, 0))
        cx = SCREEN_W // 2
        ui.text(screen, "ПАУЗА" if not self.mp else "МЕНЮ", (cx, 120), 48, bold=True, center=True)
        b1 = pygame.Rect(cx - 140, 180, 280, 50)
        ui.Button(b1, "Продолжить", size=24).draw(screen)
        self.zones.append((b1, 1, lambda: setattr(self, "paused", False)))
        b2 = pygame.Rect(cx - 140, 245, 280, 50)
        ui.Button(b2, "Управление (F1)", size=24).draw(screen)
        self.zones.append((b2, 1, lambda: setattr(self.app, "show_help", not self.app.show_help)))
        y = 310
        if self.host:
            bs = pygame.Rect(cx - 140, y, 280, 50)
            ui.Button(bs, "Сохранить игру", size=24, color=(50, 110, 60)).draw(screen)
            self.zones.append((bs, 1, self._save_now))
            y += 65
        b3 = pygame.Rect(cx - 140, y, 280, 50)
        ui.Button(b3, "Сохранить и выйти" if self.host else "Выйти в меню", size=24, color=(110, 50, 45)).draw(screen)
        self.zones.append((b3, 1, lambda: self._leave()))
        if self.host:
            ui.text(screen, "Мир: %s (автосохранение каждые 90 сек)" % self.host.world_name, (cx, y + 70), 16,
                    (190, 190, 190), center=True)
        if self.mp:
            y += 100
            ui.text(screen, "Игроки:", (cx - 200, y), 20, bold=True)
            if self.host and self.host.code:
                ui.text(screen, "Код комнаты: %s" % self.host.code, (cx + 200, y), 20, (255, 220, 120), right=True)
            y += 34
            for p in self.players.values():
                ui.text(screen, p["name"] + (" (вы)" if p["id"] == self.my_id else "") +
                        ("" if p["alive"] else " - мёртв"), (cx - 200, y + 4), 19, p["color"])
                if self.host and p["id"] != self.my_id:
                    br = pygame.Rect(cx + 90, y, 110, 30)
                    ui.Button(br, "Кикнуть", size=16, color=(110, 50, 45)).draw(screen)
                    self.zones.append((br, 1, lambda pid=p["id"]: self.host.kick(pid)))
                y += 36
