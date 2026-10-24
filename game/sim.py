"""Авторитетная симуляция мира (работает у хоста или в одиночной игре)."""
import math
import random
from collections import deque

from . import items as IT
from .config import TILE, DIFFICULTIES, VIEW_DIST
from .config import VERSION
from .world import (World, SOLID, ZSOLID, CONTAINER, TILE_NAMES, WORKBENCH, PUMP, MAX_LV, BUILD_D, RESOURCES,
                    PLACEABLE, BUSH, BUSH_EMPTY, BED, CHEST, WOOD, GRASS, DIRT, FIELD, DIRTROAD, CAMPFIRE,
                    CLIMATE_T, GROUNDS)

PCOLORS = [(66, 135, 245), (245, 166, 35), (80, 200, 120), (220, 80, 200), (240, 230, 80), (90, 220, 230),
           (240, 110, 90), (180, 140, 255)]
CAR_COLORS = [(200, 40, 40), (40, 90, 200), (225, 225, 225), (35, 35, 35), (40, 150, 70), (230, 180, 30),
              (130, 60, 160), (110, 110, 120), (240, 120, 30)]
ZTYPES = {
    "walker": {"hp": 70, "speed": 56, "dmg": 11, "r": 12},
    "runner": {"hp": 45, "speed": 112, "dmg": 8, "r": 11},
    "brute": {"hp": 320, "speed": 44, "dmg": 26, "r": 15},
    "deer": {"hp": 55, "speed": 150, "dmg": 0, "r": 11},
    "wolf": {"hp": 60, "speed": 150, "dmg": 9, "r": 11},
}
ANIMALS = ("deer", "wolf")
NPC_NAMES = ["Михалыч", "Саня", "Петрович", "Лёха", "Дед Иван", "Марина", "Олег", "Кузьмич", "Толян", "Вадим",
             "Ольга", "Серый", "Жека", "Борода", "Шрам", "Клык", "Хромой", "Косой", "Гоша", "Валера", "Нина",
             "Степан", "Рыжий", "Тихий", "Батя", "Костян", "Лиса", "Мирон", "Филин", "Зоя"]
NPC_WEAPONS = {
    "trader": [("shotgun", 1)],
    "guard": [("rifle", 1), ("shotgun", 1), ("smg", 1)],
    "surv": [("pistol", 3), ("bat", 2), ("smg", 1), ("shotgun", 1), ("machete", 1)],
    "bandit": [("bat", 2), ("machete", 1), ("pipe", 1), ("pistol", 3), ("smg", 1.5), ("shotgun", 1.5),
               ("rifle", 1)],
}
NPC_HP = {"trader": 160, "guard": 150, "surv": 100, "bandit": 100}
NPC_TITLE = {"trader": "Торговец", "guard": "Охранник", "surv": "Выживший", "bandit": "Бандит"}
DIRS8 = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
BASE_SLOTS = 16


def _cp(it):
    if it is None:
        return None
    d = dict(it)
    if "mods" in d:
        d["mods"] = list(d["mods"])
    return d


def _pick(rng, table):
    total = sum(w for _, w in table)
    r = rng.random() * total
    for v, w in table:
        r -= w
        if r <= 0:
            return v
    return table[-1][0]


class Player:
    r = 12

    def __init__(self, pid, name, color):
        self.id, self.name, self.color = pid, name, color
        self.x = self.y = 0.0
        self.lv = 0
        self.a = 0.0
        self.hp = self.food = self.water = self.stam = 100.0
        self.bleed = False
        self.alive = True
        self.inv = []
        self.eq = {"gun": None, "melee": None, "vest": None, "helmet": None, "bag": None, "cloth": None, "hat": None}
        self.temp = 36.6
        self.amb = 20.0
        self.infected = False
        self.fire = False
        self.fire_t = 0.0
        self.active = "melee"
        self.car = -1
        self.seat = -1
        self.cont = None
        self.trade = None
        self.reload_t = self.reload_total = self.fire_cd = 0.0
        self.kills = 0
        self.tpn = 0
        self.tp = None
        self.respawn_t = 0.0
        self.sprint = self.moving = False
        self.view = None
        self.spawn = None   # точка возрождения (кровать)

    def state(self):
        return {"x": self.x, "y": self.y, "lv": self.lv, "hp": self.hp, "food": self.food, "water": self.water,
                "stam": self.stam, "bleed": self.bleed, "inv": [_cp(i) for i in self.inv],
                "eq": {k: _cp(v) for k, v in self.eq.items()}, "active": self.active, "kills": self.kills,
                "spawn": self.spawn, "alive": self.alive, "temp": self.temp, "infected": self.infected}

    def restore(self, st):
        for k in ("hp", "food", "water", "stam", "bleed", "inv", "eq", "active", "kills", "spawn", "temp",
                  "infected"):
            if k in st:
                setattr(self, k, st[k])
        self.eq = {k: self.eq.get(k) for k in ("gun", "melee", "vest", "helmet", "bag", "cloth", "hat")}

    def slots(self):
        return BASE_SLOTS + (IT.ITEMS[self.eq["bag"]["id"]]["slots"] if self.eq["bag"] else 0)

    def teleport(self, x, y, lv):
        self.x, self.y, self.lv = x, y, lv
        self.tpn += 1
        self.tp = [x, y, lv]


class Zombie:
    alive = True

    def __init__(self, zid, kind, x, y, lv, diff, rng, home):
        t = ZTYPES[kind]
        self.id, self.kind, self.x, self.y, self.lv, self.home = zid, kind, x, y, lv, home
        self.chunk = None
        self.maxhp = self.hp = t["hp"] * diff["zhp"]
        self.speed = t["speed"] * diff["zspeed"] * rng.uniform(0.88, 1.12)
        self.dmg = t["dmg"] * diff["zdmg"]
        self.r = t["r"]
        self.a = rng.uniform(-math.pi, math.pi)
        self.target = None
        self.inv = None
        self.think = rng.random() * 0.3
        self.atk_cd = self.hitcd = self.lost = 0.0
        self.wander = 0.0
        self.idle = True
        self.direct = False


class NPC:
    """Выживший: торговец, охранник, бродяга (дружелюбные) или бандит (враждебный)."""
    r = 12

    def __init__(self, nid, kind, x, y, lv, rng, diff):
        self.id, self.kind, self.x, self.y, self.lv = nid, kind, x, y, lv
        self.home = (x, y)
        self.chunk = None
        self.alive = True
        self.name = rng.choice(NPC_NAMES)
        self.hostile = kind == "bandit"
        self.angry = set()
        self.a = rng.uniform(-math.pi, math.pi)
        self.maxhp = self.hp = NPC_HP[kind] * (diff["zhp"] if self.hostile else 1.0)
        self.speed = 0 if kind == "trader" else rng.uniform(95, 120)
        self.weapon = IT.make_item(_pick(rng, NPC_WEAPONS[kind]))
        if "ammo" in self.weapon:
            self.weapon["ammo"] = IT.ITEMS[self.weapon["id"]]["mag"]
        armor = kind in ("bandit", "guard")
        self.vest = rng.choice([None, None, "vest1", "vest2"]) if armor else None
        self.helmet = rng.choice([None, None, "helmet1"]) if armor else None
        self.inv = IT.roll_loot({"trader": "trader", "bandit": "bandit"}.get(kind, "surv"), rng)
        self.money = rng.randint(250, 600) if kind == "trader" else (rng.randint(20, 120) if kind == "surv" else 0)
        self.dmgk = 0.45 * min(1.6, diff["zdmg"] ** 0.6) if self.hostile else 0.8
        self.target = None
        self.los = False
        self.think = rng.random() * 0.3
        self.atk_cd = 0.0
        self.roam = None
        self.roam_t = 0.0


class Car:
    def __init__(self, cid, x, y, ang, color, fuel, hp):
        self.id, self.x, self.y, self.ang, self.color = cid, x, y, ang, color
        self.spd = 0.0
        self.up = {"engine": 0, "armor": 0, "tires": 0, "tank": 0, "ram": 0, "lights": 0}
        self.fuel, self.hp = fuel, hp
        self.seats = [None, None, None, None]
        self.wreck = False

    def maxhp(self):
        return 100 + 50 * self.up["armor"]

    def maxfuel(self):
        return 60 + 24 * self.up["tank"]


class Bag:
    def __init__(self, bid, x, y, lv, items, kind):
        self.id, self.x, self.y, self.lv, self.items, self.kind = bid, x, y, lv, items, kind


class Sim:
    def __init__(self, seed, diff, settings, world=None):
        self.world = world or World(seed)
        self.diff_key = diff
        self.diff = DIFFICULTIES[diff]
        self.settings = settings
        self.rng = random.Random(seed * 7 + 1)
        self.players, self.zombies, self.cars, self.bags, self.containers = {}, {}, {}, {}, {}
        self.npcs = {}
        self.pump_fuel = {}
        self._id = 0
        self.tod = 8 / 24
        self.day = 1
        self.events = []
        self.flow = {}
        self.flow_t = 0.0
        self.spawn_t = 0.0
        self.npc_t = 8.0
        self.act_t = 0.0
        self.active = set()
        self.cars_done = set()
        self.over = False
        self.saved_players = {}   # ник -> состояние (для вышедших и из сохранения)
        self.built = {}           # (lv, tx, ty) -> ключ постройки
        self.res_hp = {}
        self.bushes = {}          # собранные кусты -> день сбора
        self.weather = "clear"
        self.weather_t = 200.0
        self.loot_mult = self.diff["loot"] * settings.get("loot", 1.0)
        self.zmult = self.diff["zmult"] * settings.get("zombies", 1.0)
        self.spawn_center = self.world.find_spawn(self.rng, 0, 0)

    # ---------- служебное ----------
    def _nid(self):
        self._id += 1
        return self._id

    def _add_zombie(self, kind, x, y, lv, home):
        z = Zombie(self._nid(), kind, x, y, lv, self.diff, self.rng, home)
        self.zombies[z.id] = z
        return z

    def _add_npc(self, kind, x, y, lv, chunk=None):
        n = NPC(self._nid(), kind, x, y, lv, self.rng, self.diff)
        n.chunk = chunk
        self.npcs[n.id] = n
        return n

    def _valid(self, e):
        if isinstance(e, Player):
            return e.alive and self.players.get(e.id) is e
        if isinstance(e, NPC):
            return self.npcs.get(e.id) is e
        if isinstance(e, Zombie):
            return self.zombies.get(e.id) is e
        return False

    def _ev(self, ev, x, y, lv=-2):
        ev.setdefault("x", int(x))
        ev.setdefault("y", int(y))
        self.events.append((x, y, lv, None, ev))

    def _all(self, ev):
        self.events.append((0, 0, -1, None, ev))

    def _to(self, p, ev):
        self.events.append((0, 0, -1, p.id, ev))

    def _msg(self, p, text):
        self._to(p, {"k": "msg", "t": text})

    def hour(self):
        return (self.tod * 24) % 24

    def is_night(self):
        h = self.hour()
        return h >= 21 or h < 5

    def _free_spot(self, x, y, lv, r=13, rad=96):
        if self.world.circle_free(lv, x, y, r):
            return x, y
        for _ in range(40):
            nx, ny = x + self.rng.uniform(-rad, rad), y + self.rng.uniform(-rad, rad)
            if self.world.circle_free(lv, nx, ny, r):
                return nx, ny
        return x, y

    # ---------- чанки ----------
    def _activate(self):
        alive = [p for p in self.players.values() if p.alive]
        if not alive:
            return
        pcs = [(int(p.x // TILE) >> 5, int(p.y // TILE) >> 5) for p in alive]
        for pcx, pcy in pcs:
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    key = (pcx + dx, pcy + dy)
                    if key not in self.active:
                        self.active.add(key)
                        self._spawn_chunk(key)
        for key in list(self.active):
            if all(max(abs(key[0] - cx), abs(key[1] - cy)) > 4 for cx, cy in pcs):
                self._despawn_chunk(key)

    def _spawn_chunk(self, key):
        c = self.world.chunk(*key)
        rng = self.rng
        if key not in self.cars_done:
            self.cars_done.add(key)
            for (x, y, ang) in c.car_spawns:
                cid = self._nid()
                car = Car(cid, x, y, ang, rng.choice(CAR_COLORS), rng.uniform(4, 40), rng.uniform(40, 100))
                if rng.random() < 0.12:
                    car.wreck, car.hp = True, 0
                self.cars[cid] = car
        for (x, y, lv, kind) in c.zombie_spawns:
            n = int(self.zmult) + (1 if rng.random() < self.zmult - int(self.zmult) else 0)
            for k in range(n):
                zx, zy = x, y
                if k:
                    zx, zy = x + rng.uniform(-10, 10), y + rng.uniform(-10, 10)
                    if not self.world.circle_free(lv, zx, zy, 12):
                        zx, zy = x, y
                self._add_zombie(kind, zx, zy, lv, True).chunk = key
        for (x, y, lv, kind) in c.npc_spawns:
            self._add_npc(kind, x, y, lv, key)

    def _despawn_chunk(self, key):
        self.active.discard(key)
        for z in list(self.zombies.values()):
            if z.chunk == key:
                del self.zombies[z.id]
        for n in list(self.npcs.values()):
            if n.chunk == key:
                self._remove_npc(n)

    def _remove_npc(self, n):
        self.npcs.pop(n.id, None)
        n.alive = False
        for p in self.players.values():
            if p.trade == n.id:
                p.trade = None

    # ---------- игроки ----------
    def add_player(self, pid, name):
        p = Player(pid, name, PCOLORS[(pid - 1) % len(PCOLORS)])
        st = self.saved_players.pop(name, None)
        if st and st.get("alive", True):
            p.restore(st)
            x, y, lv = st["x"], st["y"], st["lv"]
            if not self.world.circle_free(lv, x, y, 12):
                x, y = self._free_spot(x, y, lv)
            p.teleport(x, y, lv)
            self._all({"k": "msg", "t": "%s вернулся в игру" % name})
        else:
            self._give_start(p)
            if st:
                p.spawn = st.get("spawn")
            x, y = self.spawn_center
            x, y = self._free_spot(x + self.rng.uniform(-48, 48), y + self.rng.uniform(-48, 48), 0)
            p.teleport(x, y, 0)
            self._all({"k": "msg", "t": "%s в игре" % name})
        self.players[pid] = p
        self._activate()
        return p

    def _give_start(self, p):
        p.inv = [IT.make_item("water"), IT.make_item("canned"), IT.make_item("bandage", n=2),
                 IT.make_item("money", n=50)]
        p.eq["cloth"] = IT.make_item("hoodie")
        p.temp = 36.6
        p.infected = False
        if self.diff_key == "easy":
            g = IT.make_item("pistol")
            g["ammo"] = 12
            p.eq["gun"] = g
            p.inv.append(IT.make_item("a9", n=24))
            p.eq["melee"] = IT.make_item("knife")
            p.active = "gun"
        elif self.diff_key == "normal":
            p.eq["melee"] = IT.make_item("knife")

    def remove_player(self, pid):
        p = self.players.pop(pid, None)
        if not p:
            return
        if p.car >= 0:
            c = self.cars.get(p.car)
            if c:
                c.seats[p.seat] = None
                if p.seat == 0:
                    c.spd = 0
        self.saved_players[p.name] = p.state()
        self._all({"k": "msg", "t": "%s вышел из игры (вещи сохранены)" % p.name})

    def handle(self, pid, m):
        p = self.players.get(pid)
        if not p or not isinstance(m, dict):
            return
        t = m.get("t")
        try:
            if t == "in":
                self._input(p, m)
            elif t == "respawn":
                self._respawn(p)
            elif p.alive or t == "chat":
                fn = getattr(self, "_a_" + str(t), None)
                if fn:
                    fn(p, m)
        except (KeyError, ValueError, TypeError, IndexError):
            pass

    def _input(self, p, m):
        if not p.alive:
            p.view = (float(m["x"]), float(m["y"]), int(m["lv"]))
            return
        p.a = float(m.get("a", 0))
        p.sprint = bool(m.get("sp"))
        p.moving = bool(m.get("mv"))
        if int(m.get("tpn", -1)) != p.tpn:
            return
        if p.car >= 0:
            c = self.cars.get(p.car)
            if c and p.seat == 0 and m.get("car") and not c.wreck:
                cx, cy, ca, cs = m["car"]
                c.x, c.y, c.ang, c.spd = float(cx), float(cy), float(ca), float(cs)
            return
        lv = int(m["lv"])
        if 0 <= lv < MAX_LV:
            p.x, p.y, p.lv = float(m["x"]), float(m["y"]), lv

    # ---------- предметы ----------
    def _count(self, p, iid):
        return sum(it["n"] for it in p.inv if it["id"] == iid)

    def _take_items(self, p, iid, n):
        got = 0
        for it in list(p.inv):
            if got >= n:
                break
            if it["id"] == iid:
                k = min(n - got, it["n"])
                it["n"] -= k
                got += k
                if it["n"] <= 0:
                    p.inv.remove(it)
        return got

    def _add_item(self, p, it):
        d = IT.ITEMS[it["id"]]
        n = it["n"]
        if d["stack"] > 1:
            for s in p.inv:
                if s["id"] == it["id"] and s["n"] < d["stack"]:
                    k = min(n, d["stack"] - s["n"])
                    s["n"] += k
                    n -= k
                    if n <= 0:
                        return 0
        while n > 0 and len(p.inv) < p.slots():
            k = min(n, d["stack"])
            new = _cp(it)
            new["n"] = k
            p.inv.append(new)
            n -= k
        return n

    @staticmethod
    def _merge_into(items, it):
        st = IT.ITEMS[it["id"]]["stack"]
        if st > 1:
            for s in items:
                if s["id"] == it["id"] and s["n"] < st:
                    k = min(it["n"], st - s["n"])
                    s["n"] += k
                    it["n"] -= k
        if it["n"] > 0:
            items.append(it)

    def _consume(self, p, idx):
        it = p.inv[idx]
        it["n"] -= 1
        if it["n"] <= 0:
            p.inv.pop(idx)

    def _drop_bag(self, x, y, lv, items, kind="bag"):
        if kind == "bag":
            for b in self.bags.values():
                if b.kind == "bag" and b.lv == lv and abs(b.x - x) < 28 and abs(b.y - y) < 28:
                    b.items.extend(items)
                    return b
        b = Bag(self._nid(), x, y, lv, list(items), kind)
        self.bags[b.id] = b
        return b

    def _a_use(self, p, m):
        idx = int(m["i"])
        if not 0 <= idx < len(p.inv):
            return
        it = p.inv[idx]
        d = IT.ITEMS[it["id"]]
        k = d["kind"]
        if k in ("food", "drink", "med"):
            p.food = min(100, max(0, p.food + d.get("food", 0)))
            p.water = min(100, max(0, p.water + d.get("water", 0)))
            p.stam = min(100, p.stam + d.get("stam", 0))
            p.hp = min(100, p.hp + d.get("hp", 0))
            if d.get("stopbleed"):
                p.bleed = False
            if d.get("cure") and p.infected:
                p.infected = False
                self._msg(p, "Заражение вылечено")
            if it["id"] == "meat":
                self._msg(p, "Сырое мясо вредно - пожарьте его у костра")
            self._consume(p, idx)
            self._to(p, {"k": "snd", "s": "eat" if k != "med" else "med"})
        elif k in ("gun", "melee", "vest", "helmet", "bag", "cloth", "hat"):
            self._equip(p, idx)
        elif k == "carfix":
            c = self._near_car(p, 110)
            if not c:
                self._msg(p, "Подойдите к машине")
                return
            if "fuel" in d:
                if c.fuel >= c.maxfuel() - 1:
                    self._msg(p, "Бак полный")
                    return
                c.fuel = min(c.maxfuel(), c.fuel + d["fuel"])
                self._msg(p, "Машина заправлена: %d/%d" % (c.fuel, c.maxfuel()))
            else:
                if c.hp >= c.maxhp():
                    self._msg(p, "Машина цела")
                    return
                c.hp = min(c.maxhp(), c.hp + d["repair"])
                self._msg(p, "Машина отремонтирована: %d/%d" % (c.hp, c.maxhp()))
            self._consume(p, idx)
            self._to(p, {"k": "snd", "s": "upgrade"})
        elif k == "mod":
            self._attach_mod(p, idx)
        elif k == "ammo":
            self._msg(p, "Патроны заряжаются перезарядкой (R)")
        else:
            self._msg(p, d["desc"])

    def _equip(self, p, idx):
        it = p.inv[idx]
        slot = IT.ITEMS[it["id"]]["kind"]
        old = p.eq[slot]
        if slot == "bag":
            new_slots = BASE_SLOTS + IT.ITEMS[it["id"]]["slots"]
            if len(p.inv) - 1 + (1 if old else 0) > new_slots:
                self._msg(p, "Не хватает места в новом рюкзаке")
                return
        p.eq[slot] = it
        if old:
            p.inv[idx] = old
        else:
            p.inv.pop(idx)
        if slot in ("gun", "melee"):
            p.active = slot
            p.reload_t = 0
        self._to(p, {"k": "snd", "s": "equip"})

    def _a_uneq(self, p, m):
        slot = m["s"]
        it = p.eq.get(slot)
        if not it:
            return
        cap = p.slots() - (IT.ITEMS[it["id"]]["slots"] if slot == "bag" else 0)
        if len(p.inv) >= cap:
            self._msg(p, "Инвентарь полон")
            return
        p.eq[slot] = None
        p.inv.append(it)
        if slot == "gun":
            p.active = "melee"
            p.reload_t = 0

    def _a_drop(self, p, m):
        idx = int(m["i"])
        if 0 <= idx < len(p.inv):
            self._drop_bag(p.x, p.y, p.lv, [p.inv.pop(idx)])

    def _attach_mod(self, p, idx):
        mod = p.inv[idx]
        d = IT.ITEMS[mod["id"]]
        w = p.eq[d["for_kind"]]
        if not w:
            self._msg(p, "Сначала экипируйте оружие (%s)" % ("огнестрел" if d["for_kind"] == "gun" else "ближний бой"))
            return
        if w["id"] == "knife":
            self._msg(p, "На нож это не поставить")
            return
        if mod["id"] in w["mods"]:
            self._msg(p, "Уже установлено")
            return
        w["mods"].append(mod["id"])
        self._consume(p, idx)
        self._msg(p, "Установлено: %s -> %s" % (d["name"], IT.ITEMS[w["id"]]["name"]))
        self._to(p, {"k": "snd", "s": "upgrade"})

    def _a_modoff(self, p, m):
        w = p.eq.get(m["s"])
        mid = m["m"]
        if not w or mid not in w.get("mods", ()):
            return
        if len(p.inv) >= p.slots():
            self._msg(p, "Инвентарь полон")
            return
        w["mods"].remove(mid)
        p.inv.append(IT.make_item(mid))
        if m["s"] == "gun" and w["ammo"] > IT.max_mag(w):
            extra = w["ammo"] - IT.max_mag(w)
            w["ammo"] = IT.max_mag(w)
            self._add_item(p, IT.make_item(IT.ITEMS[w["id"]]["ammo"], n=extra))

    # ---------- контейнеры ----------
    def _cont_items(self, key):
        if key.startswith("bag:"):
            b = self.bags.get(int(key[4:]))
            return b.items if b else None
        return self.containers.get(key)

    def _cont_pos(self, key):
        if key.startswith("bag:"):
            b = self.bags.get(int(key[4:]))
            return (b.x, b.y, b.lv) if b else None
        lv, tx, ty = (int(v) for v in key.split(","))
        return tx * TILE + 16, ty * TILE + 16, lv

    def _a_open(self, p, m):
        key = str(m["k"])
        pos = self._cont_pos(key)
        if not pos or pos[2] != p.lv or math.hypot(pos[0] - p.x, pos[1] - p.y) > 85:
            return
        if not key.startswith("bag:"):
            lv, tx, ty = (int(v) for v in key.split(","))
            t = self.world.tile(lv, tx, ty)
            if t not in CONTAINER:
                return
            if key not in self.containers:
                self.containers[key] = IT.roll_loot(CONTAINER[t], self.rng, self.loot_mult)
        p.cont = key
        p.trade = None
        self._to(p, {"k": "snd", "s": "open"})

    def _a_close(self, p, m):
        p.cont = None

    def _cleanup_bag(self, p):
        if p.cont and p.cont.startswith("bag:"):
            b = self.bags.get(int(p.cont[4:]))
            if b and not b.items:
                del self.bags[b.id]
                p.cont = None

    def _a_take(self, p, m):
        items = self._cont_items(p.cont) if p.cont else None
        idx = int(m["i"])
        if items is None or not 0 <= idx < len(items):
            return
        it = items[idx]
        left = self._add_item(p, it)
        if left == it["n"]:
            self._msg(p, "Инвентарь полон")
        elif left == 0:
            items.pop(idx)
        else:
            it["n"] = left
        self._to(p, {"k": "snd", "s": "pick"})
        self._cleanup_bag(p)

    def _a_takeall(self, p, m):
        items = self._cont_items(p.cont) if p.cont else None
        if items is None:
            return
        for it in list(items):
            left = self._add_item(p, it)
            if left == 0:
                items.remove(it)
            else:
                it["n"] = left
                self._msg(p, "Инвентарь полон")
                break
        self._to(p, {"k": "snd", "s": "pick"})
        self._cleanup_bag(p)

    def _a_put(self, p, m):
        items = self._cont_items(p.cont) if p.cont else None
        idx = int(m["i"])
        if items is None or not 0 <= idx < len(p.inv):
            return
        self._merge_into(items, p.inv.pop(idx))

    # ---------- торговля ----------
    def _trader(self, p):
        n = self.npcs.get(p.trade) if p.trade is not None else None
        if not n or n.hostile or p.id in n.angry or n.lv != p.lv or math.hypot(n.x - p.x, n.y - p.y) > 130:
            p.trade = None
            return None
        return n

    def _a_tropen(self, p, m):
        n = self.npcs.get(int(m["n"]))
        if not n or n.lv != p.lv or math.hypot(n.x - p.x, n.y - p.y) > 95:
            return
        if n.hostile or p.id in n.angry:
            self._msg(p, "%s не хочет с вами разговаривать" % n.name)
            return
        if n.kind == "guard":
            self._msg(p, "%s: «Я на посту. Торгуй с главным у костра»" % n.name)
            return
        p.trade = n.id
        p.cont = None
        n.a = math.atan2(p.y - n.y, p.x - n.x)
        self._to(p, {"k": "snd", "s": "open"})

    def _a_trclose(self, p, m):
        p.trade = None

    def _a_buy(self, p, m):
        n = self._trader(p)
        if not n:
            return
        i = int(m["i"])
        if not 0 <= i < len(n.inv):
            return
        it = n.inv[i]
        qty = IT.trade_qty(it)
        unit = IT.price(it["id"])
        if self._count(p, "money") < unit * qty:
            self._msg(p, "Не хватает денег: нужно %d" % (unit * qty))
            return
        new = _cp(it)
        new["n"] = qty
        left = self._add_item(p, new)
        bought = qty - left
        if bought <= 0:
            self._msg(p, "Инвентарь полон")
            return
        cost = unit * bought
        self._take_items(p, "money", cost)
        n.money += cost
        it["n"] -= bought
        if it["n"] <= 0:
            n.inv.pop(i)
        self._to(p, {"k": "snd", "s": "pick"})

    def _a_sell(self, p, m):
        n = self._trader(p)
        if not n:
            return
        i = int(m["i"])
        if not 0 <= i < len(p.inv) or p.inv[i]["id"] == "money":
            return
        it = p.inv[i]
        qty = IT.trade_qty(it)
        pay = IT.sell_price(it["id"]) * qty
        if n.money < pay:
            self._msg(p, "У %s не хватает денег" % n.name)
            return
        sold = _cp(it)
        sold["n"] = qty
        it["n"] -= qty
        if it["n"] <= 0:
            p.inv.pop(i)
        left = self._add_item(p, IT.make_item("money", n=pay))
        if left:
            self._take_items(p, "money", pay - left)
            self._add_item(p, sold)
            self._msg(p, "Инвентарь полон")
            return
        n.money -= pay
        self._merge_into(n.inv, sold)
        self._to(p, {"k": "snd", "s": "pick"})

    # ---------- оружие ----------
    def _a_swap(self, p, m):
        if p.active == "gun":
            p.active = "melee"
        elif p.eq["gun"]:
            p.active = "gun"
        p.reload_t = 0

    def _a_sel(self, p, m):
        s = m["s"]
        if s == "gun" and not p.eq["gun"]:
            return
        if s in ("gun", "melee") and s != p.active:
            p.active = s
            p.reload_t = 0

    def _a_rel(self, p, m):
        g = p.eq["gun"]
        if p.active != "gun" or not g or p.reload_t > 0:
            return
        d = IT.ITEMS[g["id"]]
        if g["ammo"] >= IT.max_mag(g):
            return
        if self._count(p, d["ammo"]) <= 0:
            self._msg(p, "Нет патронов: %s" % IT.ITEMS[d["ammo"]]["name"])
            self._to(p, {"k": "snd", "s": "click"})
            return
        p.reload_t = p.reload_total = d["reload"]
        self._ev({"k": "snd", "s": "reload"}, p.x, p.y)

    def _finish_reload(self, p):
        g = p.eq["gun"]
        if not g:
            return
        need = IT.max_mag(g) - g["ammo"]
        g["ammo"] += self._take_items(p, IT.ITEMS[g["id"]]["ammo"], need)

    def _a_atk(self, p, m):
        a = float(m.get("a", p.a))
        if (p.car >= 0 and p.seat == 0) or p.reload_t > 0 or p.fire_cd > 0.03:
            return
        g = p.eq["gun"]
        if p.active == "gun" and g:
            if g["ammo"] <= 0:
                self._a_rel(p, m)
                return
            d = IT.ITEMS[g["id"]]
            g["ammo"] -= 1
            p.fire_cd = d["rate"] * 0.8
            self._fire(p, a, d, 1.0, 1.0, g["mods"])
        else:
            it = p.eq["melee"]
            d = IT.ITEMS[it["id"]] if it else IT.FISTS
            p.fire_cd = d["rate"] * 0.8
            if not self._melee_hit(p, a, d, d["dmg"] * (1.35 if it and "nails" in it.get("mods", ()) else 1.0)):
                self._mine(p, a, d)

    # ---------- добыча, крафт, стройка ----------
    def _edit(self, lv, tx, ty, t):
        e = self.world.set_tile(lv, tx, ty, t)
        self._all({"k": "ed", "e": e})

    def _give(self, p, iid, n):
        left = self._add_item(p, IT.make_item(iid, n=n))
        if left:
            self._drop_bag(p.x, p.y, p.lv, [IT.make_item(iid, n=left)])
            self._msg(p, "Инвентарь полон - часть выпала на землю")

    def _mine(self, p, a, d):
        for frac in (0.55, 1.0):
            x = p.x + math.cos(a) * (d["range"] * frac + 6)
            y = p.y + math.sin(a) * (d["range"] * frac + 6)
            tx, ty = int(x // TILE), int(y // TILE)
            t = self.world.tile(p.lv, tx, ty)
            if t not in RESOURCES:
                continue
            iid, hp, (lo, hi), after = RESOURCES[t]
            key = (p.lv, tx, ty)
            power = d.get("chop" if iid == "wood" else "mine", 1)
            left = self.res_hp.get(key, hp) - power
            self._ev({"k": "chop", "x": tx * TILE + 16, "y": ty * TILE + 16, "lv": p.lv, "w": iid}, p.x, p.y)
            if left > 0:
                self.res_hp[key] = left
                return
            self.res_hp.pop(key, None)
            orig = self.world.orig_tile(p.lv, tx, ty)
            self._edit(p.lv, tx, ty, orig if orig is not None and orig != t else (after or self.world.ground(tx, ty)))
            n = self.rng.randint(lo, hi)
            self._give(p, iid, n)
            self._msg(p, "+%d %s" % (n, IT.ITEMS[iid]["name"]))
            return

    def _near_tile(self, p, tx, ty, dist=60):
        return math.hypot(tx * TILE + 16 - p.x, ty * TILE + 16 - p.y) <= dist

    def _a_harvest(self, p, m):
        lv, tx, ty = p.lv, int(m["tx"]), int(m["ty"])
        if self.world.tile(lv, tx, ty) != BUSH or not self._near_tile(p, tx, ty):
            return
        n = self.rng.randint(2, 4)
        self._give(p, "berries", n)
        self._edit(lv, tx, ty, BUSH_EMPTY)
        self.bushes[(lv, tx, ty)] = self.day
        self._msg(p, "+%d Ягоды" % n)
        self._to(p, {"k": "snd", "s": "pick"})

    def _a_setspawn(self, p, m):
        tx, ty = int(m["tx"]), int(m["ty"])
        if self.world.tile(p.lv, tx, ty) == BED and self._near_tile(p, tx, ty):
            p.spawn = [tx, ty, p.lv]
            self._msg(p, "Точка возрождения сохранена у этой кровати")
            self._to(p, {"k": "snd", "s": "equip"})

    def _a_craft(self, p, m):
        iid = m["r"]
        cost = IT.CRAFT_D.get(iid)
        if not cost:
            return
        for k, n in cost.items():
            if self._count(p, k) < n:
                self._msg(p, "Не хватает: %s" % IT.ITEMS[k]["name"])
                return
        for k, n in cost.items():
            self._take_items(p, k, n)
        self._give(p, iid, 1)
        self._msg(p, "Создано: %s" % IT.ITEMS[iid]["name"])
        self._to(p, {"k": "snd", "s": "upgrade"})

    def _blocked_by_entity(self, lv, tx, ty):
        x0, y0 = tx * TILE, ty * TILE
        for e in list(self.players.values()) + list(self.zombies.values()) + list(self.npcs.values()):
            if e.lv != lv or (isinstance(e, Player) and (not e.alive or e.car >= 0)):
                continue
            cx = min(max(e.x, x0), x0 + TILE)
            cy = min(max(e.y, y0), y0 + TILE)
            if (e.x - cx) ** 2 + (e.y - cy) ** 2 < e.r ** 2:
                return True
        if lv == 0:
            for c in self.cars.values():
                if abs(c.x - (x0 + 16)) < 50 and abs(c.y - (y0 + 16)) < 50:
                    return True
        return False

    def _a_build(self, p, m):
        key = m["s"]
        if key not in BUILD_D:
            return
        name, tile, cost = BUILD_D[key]
        lv, tx, ty = int(m["lv"]), int(m["tx"]), int(m["ty"])
        if lv != p.lv or not self._near_tile(p, tx, ty, 4.6 * TILE):
            self._msg(p, "Слишком далеко")
            return
        cur = self.world.tile(lv, tx, ty)
        if cur not in PLACEABLE or (key == "floor" and cur not in GROUNDS + (DIRT, FIELD, DIRTROAD)):
            self._msg(p, "Здесь нельзя строить")
            return
        if SOLID[tile] and self._blocked_by_entity(lv, tx, ty):
            self._msg(p, "Мешает кто-то или что-то")
            return
        for k, n in cost.items():
            if self._count(p, k) < n:
                self._msg(p, "Не хватает: %s (нужно %d)" % (IT.ITEMS[k]["name"], n))
                return
        for k, n in cost.items():
            self._take_items(p, k, n)
        self._edit(lv, tx, ty, tile)
        self.built[(lv, tx, ty)] = key
        if key == "chest":
            self.containers["%d,%d,%d" % (lv, tx, ty)] = []
        if key == "bed":
            p.spawn = [tx, ty, lv]
            self._msg(p, "Кровать построена - здесь вы будете возрождаться")
        self._ev({"k": "snd", "s": "build"}, tx * TILE + 16, ty * TILE + 16)

    def _a_unbuild(self, p, m):
        lv, tx, ty = int(m["lv"]), int(m["tx"]), int(m["ty"])
        key = self.built.get((lv, tx, ty))
        if key is None:
            self._msg(p, "Разбирать можно только свои постройки")
            return
        if lv != p.lv or not self._near_tile(p, tx, ty, 4.6 * TILE):
            self._msg(p, "Слишком далеко")
            return
        del self.built[(lv, tx, ty)]
        ck = "%d,%d,%d" % (lv, tx, ty)
        items = self.containers.pop(ck, None)
        if items:
            self._drop_bag(tx * TILE + 16, ty * TILE + 16, lv, items)
        for q in self.players.values():
            if q.cont == ck:
                q.cont = None
        orig = self.world.orig_tile(lv, tx, ty)
        self._edit(lv, tx, ty, orig if orig is not None else self.world.ground(tx, ty))
        for k, n in BUILD_D[key][2].items():
            if n // 2:
                self._give(p, k, n // 2)
        self._ev({"k": "snd", "s": "build"}, tx * TILE + 16, ty * TILE + 16)

    def _fire(self, src, a, d, dmgk, spread_k, mods=()):
        spread = d["spread"] * (0.4 if "scope" in mods else 1.0) * spread_k
        rng_ = d["range"] * (1.3 if "scope" in mods else 1.0)
        sx, sy = src.x + math.cos(a) * 18, src.y + math.sin(a) * 18
        for _ in range(d.get("pellets", 1)):
            self._hitscan(src, sx, sy, a + self.rng.gauss(0, spread * 0.6), rng_, d["dmg"] * dmgk,
                          d.get("pierce", 1))
        sil = "silencer" in mods
        self._ev({"k": "shot", "w": d["id"], "s": int(sil)}, src.x, src.y)
        self._noise(src.x, src.y, src.lv, d["noise"] * (0.3 if sil else 1.0), src)

    def _can_hit(self, src, tgt):
        if isinstance(tgt, Zombie):
            return True
        if isinstance(src, Player):
            if isinstance(tgt, Player):
                return bool(self.settings.get("friendly_fire"))
            return True
        if isinstance(tgt, Player):
            return src.hostile or tgt.id in src.angry
        return src.hostile != tgt.hostile

    def _targets(self, src, lv):
        for z in self.zombies.values():
            if z.lv == lv:
                yield z
        for q in self.players.values():
            if q is not src and q.alive and q.lv == lv and q.car < 0 and self._can_hit(src, q):
                yield q
        for n in self.npcs.values():
            if n is not src and n.lv == lv and self._can_hit(src, n):
                yield n

    def _hurt(self, e, dmg, src, kx=0.0, ky=0.0):
        if isinstance(e, Zombie):
            self._hurt_zombie(e, dmg, src, kx, ky)
            return
        self._ev({"k": "bl", "x": int(e.x), "y": int(e.y), "lv": e.lv}, e.x, e.y)
        if isinstance(e, Player):
            if isinstance(src, NPC):
                reason = "убит: %s %s" % (NPC_TITLE[src.kind].lower(), src.name)
            else:
                reason = "убит игроком %s" % src.name
            self._damage_player(e, dmg, reason, bleed=0.1)
        else:
            self._damage_npc(e, dmg, src)

    def _hitscan(self, src, x, y, a, maxd, dmg, pierce):
        dx, dy = math.cos(a), math.sin(a)
        wall = self.world.ray(src.lv, x, y, dx, dy, maxd)
        hits = []
        for e in self._targets(src, src.lv):
            rx, ry = e.x - x, e.y - y
            t = rx * dx + ry * dy
            if 0 <= t <= wall and rx * rx + ry * ry - t * t < (e.r + 2) ** 2:
                hits.append((t, id(e), e))
        hits.sort(key=lambda h: h[0])
        end = wall
        for t, _, e in hits[:pierce]:
            end = t
            self._hurt(e, dmg, src, dx * 5, dy * 5)
        self._ev({"k": "tr", "x1": int(x), "y1": int(y), "x2": int(x + dx * end), "y2": int(y + dy * end),
                  "lv": src.lv}, x, y)

    def _melee_hit(self, src, a, d, dmg):
        reach = d["range"]
        hit = False
        for e in list(self._targets(src, src.lv)):
            dx, dy = e.x - src.x, e.y - src.y
            dist = math.hypot(dx, dy)
            if dist > reach + e.r:
                continue
            da = abs((math.atan2(dy, dx) - a + math.pi) % (2 * math.pi) - math.pi)
            if da > 0.95 and dist > e.r + 14:
                continue
            kb = 4 if getattr(e, "kind", "") == "brute" else 16
            self._hurt(e, dmg, src, math.cos(a) * kb, math.sin(a) * kb)
            hit = True
        self._ev({"k": "sw", "h": int(hit)}, src.x, src.y)
        self._noise(src.x, src.y, src.lv, 140, src)
        return hit

    def _hurt_zombie(self, z, dmg, src, kx=0.0, ky=0.0):
        if z.id not in self.zombies:
            return
        z.hp -= dmg
        self._ev({"k": "bl", "x": int(z.x), "y": int(z.y), "lv": z.lv}, z.x, z.y)
        if src is not None and not isinstance(src, Zombie) and z.kind != "deer":
            z.target = src
            z.lost = 0
        if kx or ky:
            z.x, z.y, _ = self.world.move(z.lv, z.x, z.y, kx, ky, z.r, ZSOLID)
        if z.hp <= 0:
            del self.zombies[z.id]
            self._ev({"k": "zd", "x": int(z.x), "y": int(z.y), "lv": z.lv}, z.x, z.y)
            if z.kind in ANIMALS:
                n = self.rng.randint(2, 3) if z.kind == "deer" else self.rng.randint(1, 2)
                self._drop_bag(z.x, z.y, z.lv, [IT.make_item("meat", n=n), IT.make_item("hide", n=1)], "bag")
                return
            if isinstance(src, Player):
                src.kills += 1
            if self.rng.random() < 0.12:
                self._drop_bag(z.x, z.y, z.lv, IT.roll_loot("zombie", self.rng), "bag")

    def _damage_player(self, p, dmg, reason, bleed=0.0):
        if not p.alive:
            return
        absorb = 0.0
        for slot in ("vest", "helmet"):
            it = p.eq[slot]
            if it:
                d = IT.ITEMS[it["id"]]
                absorb += d["armor"]
                it["dur"] -= dmg * 0.5
                if it["dur"] <= 0:
                    p.eq[slot] = None
                    self._msg(p, "%s сломан!" % d["name"])
        absorb = min(0.75, absorb)
        p.hp -= dmg * (1 - absorb)
        if bleed and not p.bleed and self.rng.random() < bleed * (1 - absorb):
            p.bleed = True
            self._msg(p, "Кровотечение! Используйте бинт или аптечку")
        self._to(p, {"k": "hurt"})
        if p.hp <= 0:
            self._kill(p, reason)

    def _damage_npc(self, n, dmg, src):
        if not self._valid(n):
            return
        absorb = sum(IT.ITEMS[i]["armor"] for i in (n.vest, n.helmet) if i)
        n.hp -= dmg * (1 - min(0.7, absorb))
        if isinstance(src, Player) and not n.hostile and src.id not in n.angry:
            for m in self.npcs.values():
                if not m.hostile and m.lv == n.lv and math.hypot(m.x - n.x, m.y - n.y) < 500:
                    m.angry.add(src.id)
            self._msg(src, "%s и его друзья теперь враждебны к вам!" % n.name)
            if src.trade is not None:
                src.trade = None
        if src is not None and (isinstance(src, Zombie) or self._can_hit(n, src)):
            n.target = src
            n.los = True
        if n.hp <= 0:
            self._kill_npc(n, src)

    def _kill_npc(self, n, src):
        self._remove_npc(n)
        items = list(n.inv)
        w = _cp(n.weapon)
        if "ammo" in w:
            w["ammo"] = self.rng.randint(0, w["ammo"])
        items.append(w)
        for iid in (n.vest, n.helmet):
            if iid:
                it = IT.make_item(iid)
                it["dur"] = int(it["dur"] * self.rng.uniform(0.3, 0.8))
                items.append(it)
        if n.money:
            items.append(IT.make_item("money", n=n.money))
        self._drop_bag(n.x, n.y, n.lv, items, "body")
        self._ev({"k": "zd", "x": int(n.x), "y": int(n.y), "lv": n.lv}, n.x, n.y)
        if isinstance(src, Player):
            self._msg(src, "%s %s убит" % (NPC_TITLE[n.kind], n.name))

    def _kill(self, p, reason):
        if not p.alive:
            return
        p.alive = False
        p.hp = 0
        p.bleed = False
        p.view = (p.x, p.y, p.lv)
        if p.car >= 0:
            self._exit_car(p, tele=False)
        if not self.settings.get("keep_inv"):
            items = p.inv + [v for v in p.eq.values() if v]
            p.inv = []
            p.eq = {k: None for k in p.eq}
            p.active = "melee"
            if items:
                self._drop_bag(p.x, p.y, p.lv, items, "body")
        p.cont = None
        p.trade = None
        p.reload_t = 0
        p.respawn_t = 10.0 if self.settings.get("respawn") else -1
        self._all({"k": "msg", "t": "%s %s" % (p.name, reason)})
        self._ev({"k": "zd", "x": int(p.x), "y": int(p.y), "lv": p.lv}, p.x, p.y)
        if not self.settings.get("respawn") and not any(q.alive for q in self.players.values()):
            self.over = True

    def _respawn(self, p):
        if not self.settings.get("respawn") or p.alive or p.respawn_t > 0:
            return
        p.alive = True
        p.hp, p.food, p.water, p.stam = 100.0, 80.0, 80.0, 100.0
        if not p.inv and not any(p.eq.values()):
            self._give_start(p)
        others = [q for q in self.players.values() if q.alive and q is not p and q.lv == 0]
        if p.spawn and self.world.tile(p.spawn[2], p.spawn[0], p.spawn[1]) == BED:
            tx, ty, lv = p.spawn
            x, y = self._free_spot(tx * TILE + 16, ty * TILE + 16, lv, rad=48)
            p.teleport(x, y, lv)
            self._all({"k": "msg", "t": "%s возродился у своей кровати" % p.name})
            return
        if others:
            q = self.rng.choice(others)
            x, y = self.world.find_spawn(self.rng, int(q.x // TILE) >> 5, int(q.y // TILE) >> 5)
        else:
            x, y = self.world.find_spawn(self.rng, 0, 0)
        x, y = self._free_spot(x, y, 0)
        p.teleport(x, y, 0)
        self._all({"k": "msg", "t": "%s возродился" % p.name})

    # ---------- машины ----------
    def _near_car(self, p, dist):
        best, bd = None, dist
        if p.lv != 0:
            return None
        for c in self.cars.values():
            if c.wreck:
                continue
            d = math.hypot(c.x - p.x, c.y - p.y)
            if d < bd:
                best, bd = c, d
        return best

    def _a_car(self, p, m):
        if p.car >= 0:
            self._exit_car(p)
            return
        c = self._near_car(p, 80)
        if not c:
            self._msg(p, "Рядом нет целой машины")
            return
        seat = next((i for i, s in enumerate(c.seats) if s is None), None)
        if seat is None:
            self._msg(p, "В машине нет мест")
            return
        c.seats[seat] = p.id
        p.car, p.seat, p.cont, p.trade = c.id, seat, None, None
        p.reload_t = 0
        self._ev({"k": "snd", "s": "door"}, c.x, c.y)
        if seat == 0 and c.fuel <= 0:
            self._msg(p, "Бак пуст - нужна канистра или бензоколонка")

    def _exit_car(self, p, tele=True):
        c = self.cars.get(p.car)
        if c and 0 <= p.seat < 4 and c.seats[p.seat] == p.id:
            c.seats[p.seat] = None
            if p.seat == 0:
                c.spd = 0
        p.car, p.seat = -1, -1
        if tele and c:
            ca, sa = math.cos(c.ang), math.sin(c.ang)
            for ox, oy in ((-sa * 36, ca * 36), (sa * 36, -ca * 36), (-ca * 54, -sa * 54), (ca * 54, sa * 54),
                           (-sa * 60, ca * 60), (sa * 60, -ca * 60)):
                x, y = c.x + ox, c.y + oy
                if self.world.circle_free(0, x, y, 13):
                    p.teleport(x, y, 0)
                    break
            else:
                x, y = self._free_spot(c.x, c.y, 0)
                p.teleport(x, y, 0)
            self._ev({"k": "snd", "s": "door"}, c.x, c.y)

    def _car_damage(self, c, dmg):
        if c.wreck:
            return
        c.hp -= dmg
        if c.hp <= 0:
            c.hp = 0
            c.wreck = True
            c.spd = 0
            for pid in list(c.seats):
                if pid is not None and pid in self.players:
                    self._exit_car(self.players[pid])
            self._ev({"k": "boom", "x": int(c.x), "y": int(c.y), "lv": 0}, c.x, c.y)
            for q in list(self.players.values()):
                if q.alive and q.lv == 0 and math.hypot(q.x - c.x, q.y - c.y) < 110:
                    self._damage_player(q, 30, "погиб при взрыве машины")
            for z in list(self.zombies.values()):
                if z.lv == 0 and math.hypot(z.x - c.x, z.y - c.y) < 120:
                    self._hurt_zombie(z, 90, None)
            for n in list(self.npcs.values()):
                if n.lv == 0 and math.hypot(n.x - c.x, n.y - c.y) < 120:
                    self._damage_npc(n, 60, None)
            self._noise(c.x, c.y, 0, 900, None)

    def _a_crash(self, p, m):
        c = self.cars.get(p.car)
        if not c or p.seat != 0:
            return
        v = min(float(m["v"]), 700)
        if v > 110:
            self._car_damage(c, (v - 100) * 0.12 * (1 - 0.15 * c.up["armor"]))
            self._ev({"k": "snd", "s": "crash"}, c.x, c.y)
            if v > 280:
                for pid in c.seats:
                    if pid is not None and pid in self.players:
                        self._damage_player(self.players[pid], (v - 270) * 0.06, "разбился на машине")

    def _update_car(self, c, dt):
        driver = c.seats[0]
        if driver is None or driver not in self.players:
            c.spd = 0
            return
        c.fuel = max(0.0, c.fuel - abs(c.spd) * dt * 0.0035 * (1 + 0.1 * c.up["engine"]))
        if abs(c.spd) < 45:
            return
        ca, sa = math.cos(c.ang), math.sin(c.ang)
        dp = self.players.get(driver)
        for e in list(self.zombies.values()) + list(self.npcs.values()):
            if e.lv != 0 or abs(e.x - c.x) > 60 or abs(e.y - c.y) > 60:
                continue
            if getattr(e, "hitcd", 0) > 0:
                continue
            rx, ry = e.x - c.x, e.y - c.y
            along, side = rx * ca + ry * sa, -rx * sa + ry * ca
            if abs(along) < 32 + e.r * 0.5 and abs(side) < 16 + e.r:
                e.hitcd = 0.5
                dmg = abs(c.spd) * 0.45 * (1 + 0.5 * c.up["ram"])
                sgn = 1 if side >= 0 else -1
                kx, ky = ca * 20 - sa * 24 * sgn, sa * 20 + ca * 24 * sgn
                big = getattr(e, "kind", "") == "brute"
                if isinstance(e, Zombie):
                    self._hurt_zombie(e, dmg, dp, kx, ky)
                else:
                    e.x, e.y, _ = self.world.move(0, e.x, e.y, kx, ky, e.r)
                    self._damage_npc(e, dmg * 0.6, dp)
                self._car_damage(c, (12 if big else 3) * (1 - 0.15 * c.up["armor"]) * (1 - 0.15 * c.up["ram"]))
                if dp:
                    self._to(dp, {"k": "cs", "f": 0.75 if big else 0.93})

    def _a_refuel(self, p, m):
        tx0, ty0 = int(p.x // TILE), int(p.y // TILE)
        pump = None
        for oy in range(-2, 3):
            for ox in range(-2, 3):
                if p.lv == 0 and self.world.tile(0, tx0 + ox, ty0 + oy) == PUMP:
                    pump = (tx0 + ox, ty0 + oy)
        if not pump:
            return
        c = self._near_car(p, 180)
        if not c:
            self._msg(p, "Подгоните машину к колонке")
            return
        left = self.pump_fuel.get(pump, 150.0)
        amt = min(c.maxfuel() - c.fuel, left)
        if amt <= 0.5:
            self._msg(p, "Колонка пуста" if left <= 0.5 else "Бак полный")
            return
        c.fuel += amt
        self.pump_fuel[pump] = left - amt
        self._msg(p, "Заправлено %d л. В колонке осталось %d л." % (amt, left - amt))
        self._to(p, {"k": "snd", "s": "upgrade"})

    # ---------- мастерская ----------
    def _near_bench(self, p):
        tx, ty = int(p.x // TILE), int(p.y // TILE)
        for oy in range(-2, 3):
            for ox in range(-2, 3):
                if self.world.tile(p.lv, tx + ox, ty + oy) == WORKBENCH:
                    return True
        return False

    def _a_upg(self, p, m):
        c = self.cars.get(int(m["c"]))
        part = m["p"]
        if not c or c.wreck or part not in IT.CAR_UPG_D:
            return
        if not self._near_bench(p) or math.hypot(c.x - p.x, c.y - p.y) > 420:
            self._msg(p, "Машина должна стоять рядом с верстаком")
            return
        name, _, costs = IT.CAR_UPG_D[part]
        lvl = c.up[part]
        if lvl >= len(costs):
            self._msg(p, "Максимальный уровень")
            return
        if self._count(p, "tools") <= 0:
            self._msg(p, "Нужны Инструменты")
            return
        cost = costs[lvl]
        for iid, n in cost.items():
            if self._count(p, iid) < n:
                self._msg(p, "Не хватает: %s" % IT.ITEMS[iid]["name"])
                return
        for iid, n in cost.items():
            self._take_items(p, iid, n)
        c.up[part] += 1
        if part == "armor":
            c.hp += 50
        self._msg(p, "%s улучшен до ур. %d" % (name, c.up[part]))
        self._ev({"k": "snd", "s": "upgrade"}, p.x, p.y)

    def _a_paint(self, p, m):
        c = self.cars.get(int(m["c"]))
        if c and self._near_bench(p) and math.hypot(c.x - p.x, c.y - p.y) < 420:
            i = CAR_COLORS.index(tuple(c.color)) if tuple(c.color) in CAR_COLORS else 0
            c.color = CAR_COLORS[(i + 1) % len(CAR_COLORS)]

    def _a_chat(self, p, m):
        text = str(m.get("x", ""))[:120].strip()
        if text:
            self._all({"k": "chat", "n": p.name, "t": text})

    # ---------- зомби ----------
    def _noise(self, x, y, lv, radius, src):
        for z in self.zombies.values():
            if z.lv != lv:
                continue
            d = math.hypot(z.x - x, z.y - y)
            if d < radius:
                if z.target is None:
                    z.inv = (x + self.rng.uniform(-40, 40), y + self.rng.uniform(-40, 40))
                if src is not None and not isinstance(src, Zombie) and d < radius * 0.45:
                    z.target = src
                    z.lost = 0

    def _build_flow(self, lv, pts):
        w = self.world
        dist = {}
        dq = deque()
        for (x, y) in pts:
            k = (int(x // TILE), int(y // TILE))
            dist[k] = 0
            dq.append(k)
        while dq:
            k = dq.popleft()
            d = dist[k] + 1
            if d > 30:
                continue
            x, y = k
            for nk in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if nk not in dist and not ZSOLID[w.tile(lv, nk[0], nk[1])]:
                    dist[nk] = d
                    dq.append(nk)
        return dist

    def _zthink(self, z, cands, night):
        best, bd = None, 1e9
        for (e, x, y, lv) in cands:
            if lv != z.lv:
                continue
            d = math.hypot(x - z.x, y - z.y)
            if d > 900 and z.target is not e:
                continue
            sight = (220 if night else 320) * (0.85 if self.weather != "clear" else 1.0)
            if isinstance(e, Player):
                if e.sprint and e.moving:
                    sight *= 1.4
                if e.car >= 0:
                    c = self.cars.get(e.car)
                    if c and abs(c.spd) > 30:
                        sight *= 1.6
                cl = e.eq.get("cloth")
                if cl:
                    sight *= IT.ITEMS[cl["id"]].get("stealth", 1.0)
            elif z.kind == "wolf":
                continue
            if z.target is e:
                sight = max(sight, 1300 if d > 650 else 650)
            if d < sight and d < bd and (d < 50 or self.world.los(z.lv, z.x, z.y, x, y)):
                best, bd = e, d
        if best:
            if z.target is None and self.rng.random() < 0.5 and z.kind not in ANIMALS:
                self._ev({"k": "snd", "s": "groan"}, z.x, z.y)
            z.target = best
            z.direct = True
            z.lost = 0
        else:
            z.direct = False
            if z.target is not None:
                z.lost += 0.3
                t = z.target
                if not self._valid(t) or t.lv != z.lv or z.lost > 8:
                    z.inv = (t.x, t.y) if (self._valid(t) and t.lv == z.lv) else None
                    z.target = None

    def _zmove(self, z, gx, gy, speed, dt, direct):
        w = self.world
        flow = self.flow.get(z.lv)
        if not direct and flow is not None:
            tx, ty = int(z.x // TILE), int(z.y // TILE)
            best = flow.get((tx, ty), 255)
            if best < 255:
                bx = by = None
                for ox, oy in DIRS8:
                    v = flow.get((tx + ox, ty + oy), 255)
                    if v < best:
                        if ox and oy and (w.solid(z.lv, tx + ox, ty) or w.solid(z.lv, tx, ty + oy)):
                            continue
                        best, bx, by = v, tx + ox, ty + oy
                if bx is not None:
                    gx, gy = bx * TILE + 16, by * TILE + 16
        dx, dy = gx - z.x, gy - z.y
        d = math.hypot(dx, dy)
        if d < 1:
            return
        z.a = math.atan2(dy, dx)
        step = speed * dt
        z.x, z.y, _ = w.move(z.lv, z.x, z.y, dx / d * step, dy / d * step, z.r, ZSOLID)

    def _zattack(self, z, t):
        if isinstance(t, Player):
            if t.car >= 0:
                c = self.cars.get(t.car)
                if c:
                    self._car_damage(c, z.dmg * 0.6 * (1 - 0.15 * c.up["armor"]))
                    self._ev({"k": "snd", "s": "hit"}, c.x, c.y)
            else:
                self._damage_player(t, z.dmg, "загрызен волком" if z.kind == "wolf" else "съеден зомби",
                                    bleed=0.25 if z.kind == "wolf" else 0.18)
                self._ev({"k": "bl", "x": int(t.x), "y": int(t.y), "lv": t.lv}, t.x, t.y)
                if z.kind not in ANIMALS and t.alive and not t.infected and self.rng.random() < 0.07:
                    t.infected = True
                    self._msg(t, "Вас заразили! Найдите антибиотики (больница, торговцы)")
        else:
            self._ev({"k": "bl", "x": int(t.x), "y": int(t.y), "lv": t.lv}, t.x, t.y)
            self._damage_npc(t, z.dmg * 0.7, z)

    def _update_zombies(self, dt, night, cands):
        w = self.world
        smul = 1.15 if night else 1.0
        grid = {}
        for z in list(self.zombies.values()):
            near = 1e9
            for (e, x, y, lv) in cands:
                if isinstance(e, Player):
                    d = abs(x - z.x) + abs(y - z.y)
                    if d < near:
                        near = d
            if near > 2200:
                continue
            if z.atk_cd > 0:
                z.atk_cd -= dt
            if z.hitcd > 0:
                z.hitcd -= dt
            if z.kind == "deer":
                # олень убегает от людей
                fx = fy = 0.0
                for (e, x, y, lv) in cands:
                    if isinstance(e, Player) and lv == z.lv:
                        d = math.hypot(z.x - x, z.y - y)
                        if 0 < d < 340:
                            fx += (z.x - x) / d
                            fy += (z.y - y) / d
                if fx or fy:
                    ln = math.hypot(fx, fy)
                    z.a = math.atan2(fy, fx)
                    z.x, z.y, hit = w.move(z.lv, z.x, z.y, fx / ln * z.speed * dt, fy / ln * z.speed * dt, z.r,
                                           ZSOLID)
                    if hit:
                        z.x, z.y, _ = w.move(z.lv, z.x, z.y, -fy / ln * z.speed * dt, fx / ln * z.speed * dt, z.r,
                                             ZSOLID)
                    grid.setdefault((int(z.x // 40), int(z.y // 40), z.lv), []).append(z)
                    continue
                z.target = None
            z.think -= dt
            if z.think <= 0 and z.kind != "deer":
                z.think = 0.28 + self.rng.random() * 0.1
                self._zthink(z, cands, night)
            tgt = z.target
            if tgt is not None and self._valid(tgt) and tgt.lv == z.lv:
                dist = math.hypot(tgt.x - z.x, tgt.y - z.y)
                reach = z.r + (30 if isinstance(tgt, Player) and tgt.car >= 0 else 12) + 6
                if dist < reach:
                    z.a = math.atan2(tgt.y - z.y, tgt.x - z.x)
                    if z.atk_cd <= 0:
                        z.atk_cd = 1.3 if z.kind == "brute" else 0.9
                        self._zattack(z, tgt)
                else:
                    self._zmove(z, tgt.x, tgt.y, z.speed * smul, dt, z.direct and dist < 260 or dist < 70)
            elif z.inv:
                gx, gy = z.inv
                if math.hypot(gx - z.x, gy - z.y) < 20:
                    z.inv = None
                else:
                    self._zmove(z, gx, gy, z.speed * 0.8 * smul, dt, True)
            else:
                z.target = None
                z.wander -= dt
                if z.wander <= 0:
                    z.wander = self.rng.uniform(2, 5)
                    z.a = self.rng.uniform(-math.pi, math.pi)
                    z.idle = self.rng.random() < 0.4
                if not z.idle:
                    s = z.speed * 0.3 * dt
                    z.x, z.y, hit = w.move(z.lv, z.x, z.y, math.cos(z.a) * s, math.sin(z.a) * s, z.r, ZSOLID)
                    if hit:
                        z.wander = 0
            grid.setdefault((int(z.x // 40), int(z.y // 40), z.lv), []).append(z)
        for (cx, cy, lv), lst in grid.items():
            for z in lst:
                for oy in (-1, 0, 1):
                    for ox in (-1, 0, 1):
                        for o in grid.get((cx + ox, cy + oy, lv), ()):
                            if o is z:
                                continue
                            dx, dy = z.x - o.x, z.y - o.y
                            d2 = dx * dx + dy * dy
                            rr = z.r + o.r
                            if d2 < rr * rr:
                                d = math.sqrt(d2) or 0.1
                                push = (rr - d) * 0.5
                                z.x, z.y, _ = w.move(lv, z.x, z.y, dx / d * push, dy / d * push, z.r, ZSOLID)

    # ---------- выжившие ----------
    def _nthink(self, n, night):
        sight = 300 if night else 430
        cands = []
        if n.hostile:
            for p in self.players.values():
                if p.alive and p.lv == n.lv:
                    cands.append((p, sight))
            for m in self.npcs.values():
                if not m.hostile and m.lv == n.lv:
                    cands.append((m, sight))
            zl = 200
        else:
            for m in self.npcs.values():
                if m.hostile and m.lv == n.lv:
                    cands.append((m, sight))
            for p in self.players.values():
                if p.alive and p.lv == n.lv and p.id in n.angry:
                    cands.append((p, sight + 60))
            zl = 380
        for z in self.zombies.values():
            if z.lv == n.lv and abs(z.x - n.x) + abs(z.y - n.y) < zl * 1.5:
                cands.append((z, zl))
        best, bd = None, 1e9
        for e, lim in cands:
            d = math.hypot(e.x - n.x, e.y - n.y)
            if d < lim and d < bd and (d < 60 or self.world.los(n.lv, n.x, n.y, e.x, e.y)):
                best, bd = e, d
        if best is None and n.target is not None and self._valid(n.target) and n.target.lv == n.lv \
                and math.hypot(n.target.x - n.x, n.target.y - n.y) < 500:
            n.los = self.world.los(n.lv, n.x, n.y, n.target.x, n.target.y)
            return
        n.target = best
        n.los = best is not None

    def _nmove(self, n, ux, uy, dt, k):
        if n.speed:
            n.x, n.y, _ = self.world.move(n.lv, n.x, n.y, ux * n.speed * k * dt, uy * n.speed * k * dt, n.r)

    def _update_npcs(self, dt, night, alive):
        for n in list(self.npcs.values()):
            if not self._valid(n):
                continue
            if not any(abs(p.x - n.x) + abs(p.y - n.y) < 2400 for p in alive):
                continue
            n.atk_cd -= dt
            if getattr(n, "hitcd", 0) > 0:
                n.hitcd -= dt
            n.think -= dt
            if n.think <= 0:
                n.think = 0.3 + self.rng.random() * 0.15
                self._nthink(n, night)
            t = n.target
            if t is not None and not (self._valid(t) and t.lv == n.lv):
                t = n.target = None
            w = n.weapon
            wd = IT.ITEMS[w["id"]]
            if t is not None:
                dx, dy = t.x - n.x, t.y - n.y
                d = math.hypot(dx, dy) or 0.1
                n.a = math.atan2(dy, dx)
                if wd["kind"] == "gun":
                    if d > wd["range"] * 0.55 or not n.los:
                        self._nmove(n, dx / d, dy / d, dt, 1.0)
                    elif d < 110:
                        self._nmove(n, -dx / d, -dy / d, dt, 0.7)
                    if n.los and n.atk_cd <= 0 and d < wd["range"]:
                        if w["ammo"] <= 0:
                            w["ammo"] = wd["mag"]
                            n.atk_cd = wd["reload"]
                            self._ev({"k": "snd", "s": "reload"}, n.x, n.y)
                        else:
                            w["ammo"] -= 1
                            n.atk_cd = max(wd["rate"] * 2.5, 0.3) + self.rng.uniform(0, 0.45)
                            self._fire(n, n.a, wd, n.dmgk, 2.2)
                else:
                    if d > wd["range"] + t.r - 4:
                        self._nmove(n, dx / d, dy / d, dt, 1.0)
                    elif n.atk_cd <= 0:
                        n.atk_cd = wd["rate"] * 1.8 + self.rng.uniform(0, 0.3)
                        self._melee_hit(n, n.a, wd, wd["dmg"] * n.dmgk)
            elif n.kind in ("trader", "guard"):
                hx, hy = n.home
                d = math.hypot(hx - n.x, hy - n.y)
                if d > 24 and n.speed:
                    self._nmove(n, (hx - n.x) / d, (hy - n.y) / d, dt, 0.5)
                elif self.rng.random() < dt * 0.3:
                    n.a = self.rng.uniform(-math.pi, math.pi)
            else:
                n.roam_t -= dt
                if n.roam_t <= 0 or n.roam is None:
                    n.roam_t = self.rng.uniform(4, 8)
                    hx, hy = n.home
                    n.roam = (hx + self.rng.uniform(-250, 250), hy + self.rng.uniform(-250, 250))
                gx, gy = n.roam
                d = math.hypot(gx - n.x, gy - n.y)
                if d > 14:
                    n.a = math.atan2(gy - n.y, gx - n.x)
                    self._nmove(n, (gx - n.x) / d, (gy - n.y) / d, dt, 0.4)

    def _spawn_outdoor(self, night):
        alive = [p for p in self.players.values() if p.alive]
        for z in list(self.zombies.values()):
            if not z.home and all(abs(q.x - z.x) + abs(q.y - z.y) > 2600 for q in alive):
                del self.zombies[z.id]
        for n in list(self.npcs.values()):
            if n.chunk is None and all(abs(q.x - n.x) + abs(q.y - n.y) > 2800 for q in alive):
                self._remove_npc(n)
        if len(self.zombies) > 380:
            return
        want = int(20 * self.zmult * (1.7 if night else 1.0) * (1 + 0.08 * min(self.day - 1, 10)))
        for p in alive:
            if p.lv != 0:
                continue
            # животные за городом
            pc = self.world.chunk(int(p.x // TILE) >> 5, int(p.y // TILE) >> 5)
            if pc.biome not in ("downtown", "city"):
                an = sum(1 for z in self.zombies.values()
                         if z.kind in ANIMALS and abs(z.x - p.x) < 1300 and abs(z.y - p.y) < 1300)
                if an < 6 and self.rng.random() < 0.5:
                    pos = self._outdoor_spot(p, alive)
                    if pos:
                        wolf_p = 0.25 + (0.3 if night else 0) + (0.2 if pc.climate == "snow" else 0)
                        if self.rng.random() < wolf_p:
                            for _ in range(self.rng.randint(2, 3)):
                                self._add_zombie("wolf", pos[0] + self.rng.uniform(-30, 30),
                                                 pos[1] + self.rng.uniform(-30, 30), 0, False)
                        else:
                            self._add_zombie("deer", pos[0], pos[1], 0, False)
            cnt = sum(1 for z in self.zombies.values()
                      if z.lv == 0 and z.kind not in ANIMALS and abs(z.x - p.x) < 1300 and abs(z.y - p.y) < 1300)
            local_want = int(want * {"downtown": 1.4, "city": 1.25, "suburb": 1.1, "village": 0.9, "military": 1.2}.get(
                pc.biome, 0.55))
            for _ in range(min(3, local_want - cnt)):
                pos = self._outdoor_spot(p, alive)
                if pos:
                    r = self.rng.random()
                    if r < 0.05 + 0.02 * min(self.day, 5):
                        kind = "brute"
                    elif r < 0.3 + (0.15 if night else 0):
                        kind = "runner"
                    else:
                        kind = "walker"
                    self._add_zombie(kind, pos[0], pos[1], 0, False)

    def _outdoor_spot(self, p, alive, dmin=720, dmax=1050):
        for _ in range(6):
            a = self.rng.uniform(-math.pi, math.pi)
            d = self.rng.uniform(dmin, dmax)
            x, y = p.x + math.cos(a) * d, p.y + math.sin(a) * d
            if self.world.bid_at(x, y) is not None or not self.world.circle_free(0, x, y, 14):
                continue
            if any(math.hypot(q.x - x, q.y - y) < 650 for q in alive):
                continue
            return x, y
        return None

    def _spawn_wanderers(self):
        alive = [p for p in self.players.values() if p.alive and p.lv == 0]
        for p in alive:
            roam = sum(1 for n in self.npcs.values()
                       if n.chunk is None and abs(n.x - p.x) + abs(n.y - p.y) < 1800)
            if roam >= 3 or self.rng.random() > 0.4:
                continue
            pos = self._outdoor_spot(p, alive, 850, 1050)
            if not pos:
                continue
            bandits = self.rng.random() < (0.45 if self.day == 1 else 0.6)
            for k in range(self.rng.randint(1, 3 if bandits else 2)):
                x, y = self._free_spot(pos[0] + self.rng.uniform(-40, 40), pos[1] + self.rng.uniform(-40, 40), 0)
                n = self._add_npc("bandit" if bandits else "surv", x, y, 0)
                n.home = (x, y)

    # ---------- события: орда, сброс груза, погода ----------
    def _horde(self):
        alive = [p for p in self.players.values() if p.alive and p.lv == 0]
        if not alive:
            return
        size = min(28, int((6 + 2 * self.day) * self.zmult))
        for p in alive:
            pos = self._outdoor_spot(p, alive, 900, 1150)
            if not pos:
                continue
            for _ in range(size):
                x, y = pos[0] + self.rng.uniform(-90, 90), pos[1] + self.rng.uniform(-90, 90)
                if self.world.circle_free(0, x, y, 12, ZSOLID):
                    kind = "runner" if self.rng.random() < 0.3 else ("brute" if self.rng.random() < 0.1 else "walker")
                    z = self._add_zombie(kind, x, y, 0, False)
                    z.target, z.inv = p, (p.x, p.y)
        self._all({"k": "msg", "t": "Слышен рёв орды! Ночью держитесь в укрытии"})
        self._all({"k": "snd", "s": "groan"})

    def _airdrop(self):
        alive = [p for p in self.players.values() if p.alive]
        if not alive:
            return
        p = self.rng.choice(alive)
        for _ in range(20):
            a = self.rng.uniform(-math.pi, math.pi)
            d = self.rng.uniform(1100, 1800)
            x, y = p.x + math.cos(a) * d, p.y + math.sin(a) * d
            if self.world.bid_at(x, y) is None and self.world.circle_free(0, x, y, 16):
                break
        else:
            return
        self._drop_bag(x, y, 0, IT.roll_loot("drop", self.rng), "drop")
        for _ in range(int(6 * self.zmult)):
            zx, zy = x + self.rng.uniform(-150, 150), y + self.rng.uniform(-150, 150)
            if self.world.circle_free(0, zx, zy, 12, ZSOLID):
                self._add_zombie("walker" if self.rng.random() < 0.7 else "runner", zx, zy, 0, False)
        self._all({"k": "msg", "t": "Сброс груза с воздуха! Он отмечен на карте (M) жёлтым парашютом"})

    def _update_weather(self, dt):
        self.weather_t -= dt
        if self.weather_t <= 0:
            r = self.rng.random()
            self.weather = "clear" if r < 0.55 else ("rain" if r < 0.85 else "storm")
            self.weather_t = self.rng.uniform(90, 260) if self.weather != "clear" else self.rng.uniform(150, 400)

    def _ambient(self, p):
        """Температура воздуха вокруг игрока (°C)."""
        clim = self.world.climate(int(p.x // TILE) >> 5, int(p.y // TILE) >> 5)
        day, night = CLIMATE_T[clim]
        h = self.hour()
        f = max(0.0, math.sin(math.pi * (h - 6) / 14)) if 6 <= h <= 20 else 0.0
        amb = night + (day - night) * f
        if self.weather == "rain":
            amb -= 4
        elif self.weather == "storm":
            amb += 3 if clim == "desert" else -7
        if p.lv > 0 or p.car >= 0 or self.world.bid_at(p.x, p.y) is not None:
            amb = amb * 0.35 + 18 * 0.65
        return amb

    def _update_temp(self, p, dt):
        amb = self._ambient(p)
        p.amb = amb
        warm = cool = 0.0
        for slot in ("cloth", "hat"):
            it = p.eq.get(slot)
            if it:
                warm += IT.ITEMS[it["id"]].get("warm", 0)
                cool += IT.ITEMS[it["id"]].get("cool", 0)
        p.fire_t -= dt
        if p.fire_t <= 0:
            p.fire_t = 0.5
            tx, ty = int(p.x // TILE), int(p.y // TILE)
            p.fire = any(self.world.tile(p.lv, tx + ox, ty + oy) == CAMPFIRE
                         for oy in range(-3, 4) for ox in range(-3, 4))
        eff = amb
        if amb < 22:
            eff += warm * 5
        if amb > 24:
            eff -= cool * 5
        if p.fire:
            eff += 16
        if p.sprint and p.moving:
            eff += 3
        target = max(32.0, min(40.5, 36.6 + (eff - 20) * 0.075))
        p.temp += (target - p.temp) * min(1.0, dt * 0.04)
        reason = None
        if p.temp < 35.5:
            p.hp -= (0.35 if p.temp > 34.5 else 1.0) * dt
            reason = "замёрз насмерть"
        elif p.temp > 37.8:
            p.water -= 0.25 * dt
            if p.temp > 38.6:
                p.hp -= 0.5 * dt
                reason = "умер от теплового удара"
        return reason

    def _a_cook(self, p, m):
        if not p.fire:
            self._msg(p, "Нужен костёр рядом")
            return
        n = self._take_items(p, "meat", 999)
        if not n:
            self._msg(p, "Нет сырого мяса")
            return
        self._give(p, "cooked_meat", n)
        self._msg(p, "Пожарено мяса: %d" % n)
        self._to(p, {"k": "snd", "s": "eat"})

    # ---------- главный цикл ----------
    def update(self, dt):
        h0 = self.hour()
        self.tod += dt / (self.settings.get("day_len", 12) * 60)
        h1 = self.hour()
        if h0 < 21 <= h1:
            self._horde()
        if h0 < 12 <= h1:
            self._airdrop()
        self._update_weather(dt)
        if self.tod >= 1:
            self.tod -= 1
            self.day += 1
            self._all({"k": "msg", "t": "Наступил день %d. Торговцы получили новый товар" % self.day})
            for n in self.npcs.values():
                if n.kind == "trader" and len(n.inv) < 30:
                    n.inv += IT.roll_loot("trader", self.rng, 0.5)
                    n.money += 100
            for key, d in list(self.bushes.items()):
                if self.day > d and self.world.tile(*key) == BUSH_EMPTY:
                    self._edit(key[0], key[1], key[2], BUSH)
                    del self.bushes[key]
        night = self.is_night()
        self.act_t -= dt
        if self.act_t <= 0:
            self.act_t = 1.0
            self._activate()
        for p in list(self.players.values()):
            self._update_player(p, dt)
        for c in self.cars.values():
            self._update_car(c, dt)
        alive = [p for p in self.players.values() if p.alive]
        self.flow_t -= dt
        if self.flow_t <= 0:
            self.flow_t = 0.35
            pts = {}
            for p in alive:
                pts.setdefault(p.lv, []).append((p.x, p.y))
            self.flow = {lv: self._build_flow(lv, v) for lv, v in pts.items()}
        cands = [(p, p.x, p.y, p.lv) for p in alive] + [(n, n.x, n.y, n.lv) for n in self.npcs.values()]
        self._update_zombies(dt, night, cands)
        self._update_npcs(dt, night, alive)
        self.spawn_t -= dt
        if self.spawn_t <= 0:
            self.spawn_t = 1.5
            self._spawn_outdoor(night)
        self.npc_t -= dt
        if self.npc_t <= 0:
            self.npc_t = 15.0
            self._spawn_wanderers()

    def _update_player(self, p, dt):
        if not p.alive:
            if p.respawn_t > 0:
                p.respawn_t = max(0.0, p.respawn_t - dt)
            return
        if p.car >= 0:
            c = self.cars.get(p.car)
            if c is None:
                p.car = -1
            else:
                p.x, p.y, p.lv = c.x, c.y, 0
        mult = self.diff["hunger"]
        p.food -= 0.17 * mult * dt
        p.water -= 0.22 * mult * dt
        if p.sprint and p.moving and p.car < 0 and p.stam > 0:
            p.stam -= 22 * dt
            p.water -= 0.05 * dt
        else:
            p.stam += (14 if p.food > 15 and p.temp > 35.5 else 6) * dt
        reason = self._update_temp(p, dt)
        if p.infected:
            p.hp -= 0.22 * dt
            p.food -= 0.04 * dt
            reason = "умер от заражения"
        if p.food <= 0:
            p.hp -= 0.6 * dt
            reason = "умер от голода"
        if p.water <= 0:
            p.hp -= 0.9 * dt
            reason = "умер от жажды"
        if p.bleed:
            p.hp -= 1.1 * dt
            reason = "истёк кровью"
        if p.food > 50 and p.water > 50 and not p.bleed and not p.infected and 35.8 < p.temp < 37.6:
            p.hp += 0.2 * dt
        p.hp = min(100.0, p.hp)
        p.food = min(100.0, max(0.0, p.food))
        p.water = min(100.0, max(0.0, p.water))
        p.stam = min(100.0, max(0.0, p.stam))
        if p.fire_cd > 0:
            p.fire_cd -= dt
        if p.reload_t > 0:
            p.reload_t -= dt
            if p.reload_t <= 0:
                self._finish_reload(p)
        if p.cont:
            pos = self._cont_pos(p.cont)
            if not pos or pos[2] != p.lv or math.hypot(pos[0] - p.x, pos[1] - p.y) > 120:
                p.cont = None
        if p.hp <= 0:
            self._kill(p, reason or "погиб")

    # ---------- сохранение ----------
    def to_save(self):
        players = dict(self.saved_players)
        for p in self.players.values():
            players[p.name] = p.state()
        return {
            "version": VERSION, "seed": self.world.seed, "diff": self.diff_key, "settings": self.settings,
            "tod": self.tod, "day": self.day, "id": self._id, "edits": self.world.export_edits(),
            "built": [[lv, tx, ty, k] for (lv, tx, ty), k in self.built.items()],
            "bushes": [[lv, tx, ty, d] for (lv, tx, ty), d in self.bushes.items()],
            "containers": self.containers,
            "bags": [[b.x, b.y, b.lv, b.kind, b.items] for b in self.bags.values()],
            "cars": [[c.x, c.y, c.ang, list(c.color), c.fuel, c.hp, c.up, c.wreck] for c in self.cars.values()],
            "cars_done": [list(k) for k in self.cars_done],
            "pumps": [[tx, ty, v] for (tx, ty), v in self.pump_fuel.items()],
            "players": players,
        }

    @classmethod
    def from_save(cls, data, settings=None):
        s = cls(data["seed"], data["diff"], settings or data["settings"])
        s.world.load_edits(data.get("edits", []))
        s.tod, s.day = data.get("tod", s.tod), data.get("day", 1)
        s._id = max(s._id, data.get("id", 0))
        s.built = {(lv, tx, ty): k for lv, tx, ty, k in data.get("built", [])}
        s.bushes = {(lv, tx, ty): d for lv, tx, ty, d in data.get("bushes", [])}
        s.containers = data.get("containers", {})
        for x, y, lv, kind, items in data.get("bags", []):
            b = Bag(s._nid(), x, y, lv, items, kind)
            s.bags[b.id] = b
        for x, y, ang, color, fuel, hp, up, wreck in data.get("cars", []):
            c = Car(s._nid(), x, y, ang, tuple(color), fuel, hp)
            c.up.update(up)
            c.wreck = wreck
            s.cars[c.id] = c
        s.cars_done = {tuple(k) for k in data.get("cars_done", [])}
        s.pump_fuel = {(tx, ty): v for tx, ty, v in data.get("pumps", [])}
        s.saved_players = dict(data.get("players", {}))
        return s

    # ---------- снимок для клиента ----------
    def _wpn(self, q):
        if q.active == "gun" and q.eq["gun"]:
            return q.eq["gun"]["id"]
        return q.eq["melee"]["id"] if q.eq["melee"] else "fists"

    def snapshot(self, pid):
        p = self.players[pid]
        vx, vy, vlv = (p.x, p.y, p.lv) if p.alive or not p.view else p.view
        R = VIEW_DIST
        P = [[q.id, q.name, round(q.x, 1), round(q.y, 1), q.lv, round(q.a, 2), int(q.hp), int(q.alive), q.car,
              q.seat, self._wpn(q), q.eq["vest"]["id"] if q.eq["vest"] else "",
              q.eq["helmet"]["id"] if q.eq["helmet"] else "", q.color,
              q.eq["cloth"]["id"] if q.eq.get("cloth") else "", q.eq["hat"]["id"] if q.eq.get("hat") else ""]
             for q in self.players.values()]
        Z = [[z.id, z.kind, round(z.x, 1), round(z.y, 1), z.lv, round(z.a, 2), round(z.hp / z.maxhp, 2)]
             for z in self.zombies.values() if abs(z.x - vx) < R and abs(z.y - vy) < R]
        N = [[n.id, n.kind, n.name, round(n.x, 1), round(n.y, 1), n.lv, round(n.a, 2), round(n.hp / n.maxhp, 2),
              n.weapon["id"], n.vest or "", n.helmet or "", int(n.hostile or pid in n.angry)]
             for n in self.npcs.values() if abs(n.x - vx) < R and abs(n.y - vy) < R]
        C = [[c.id, round(c.x, 1), round(c.y, 1), round(c.ang, 3), round(c.spd, 1), int(c.hp), c.maxhp(),
              round(c.fuel, 1), c.maxfuel(), c.color, c.up, [s if s is not None else -1 for s in c.seats],
              int(c.wreck)] for c in self.cars.values() if abs(c.x - vx) < 3000 and abs(c.y - vy) < 3000]
        B = [[b.id, int(b.x), int(b.y), b.lv, b.kind] for b in self.bags.values()
             if abs(b.x - vx) < R and abs(b.y - vy) < R]
        me = {"hp": round(p.hp, 1), "food": round(p.food, 1), "water": round(p.water, 1), "stam": round(p.stam, 1),
              "bleed": p.bleed, "alive": p.alive, "inv": [_cp(i) for i in p.inv],
              "eq": {k: _cp(v) for k, v in p.eq.items()}, "act": p.active, "slots": p.slots(),
              "rl": (1 - p.reload_t / p.reload_total) if p.reload_t > 0 else -1, "tpn": p.tpn, "tp": p.tp,
              "kills": p.kills, "rsp": p.respawn_t if (not p.alive and self.settings.get("respawn")) else -1,
              "car": p.car, "seat": p.seat, "trade": None, "temp": round(p.temp, 2), "amb": round(p.amb, 1),
              "inf": p.infected, "fire": p.fire}
        n = self._trader(p) if p.trade is not None else None
        if n:
            me["trade"] = {"id": n.id, "name": "%s %s" % (NPC_TITLE[n.kind], n.name), "money": n.money,
                           "items": [_cp(i) for i in n.inv]}
        cont = None
        if p.cont:
            items = self._cont_items(p.cont)
            if items is not None:
                if p.cont.startswith("bag:"):
                    b = self.bags.get(int(p.cont[4:]))
                    name = {"body": "Тело", "drop": "Груз с воздуха"}.get(b.kind if b else "", "Вещи на земле")
                else:
                    lv, tx, ty = (int(v) for v in p.cont.split(","))
                    name = TILE_NAMES.get(self.world.tile(lv, tx, ty), "Контейнер")
                cont = {"k": p.cont, "n": name, "items": [_cp(i) for i in items]}
        ev = []
        for (x, y, lv, to, e) in self.events:
            if to is not None:
                if to == pid:
                    ev.append(e)
            elif lv == -1 or (abs(x - vx) < 1400 and abs(y - vy) < 1000):
                ev.append(e)
        return {"t": "s", "tod": round(self.tod, 4), "day": self.day, "P": P, "Z": Z, "N": N, "C": C, "B": B,
                "me": me, "cont": cont, "ev": ev, "over": self.over, "W": self.weather,
                "S": {"respawn": bool(self.settings.get("respawn")), "keep_inv": bool(self.settings.get("keep_inv"))},
                "D": [[int(b.x), int(b.y)] for b in self.bags.values() if b.kind == "drop"]}
