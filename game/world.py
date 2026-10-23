"""Бесконечный мир. Карта делится на чанки 32x32 тайла; каждый чанк - квартал с дорогами по краям.
Чанк генерируется по требованию из (seed, cx, cy) одинаково у хоста и у всех клиентов."""
import math
import random
from array import array

from .config import TILE

CS = 32          # размер чанка в тайлах
MAX_LV = 4       # максимум этажей

(GRASS, ROAD, ROADV, ROADH, SIDEWALK, WOOD, TILEF, CONCRETE, DIRT, WALL, DOOR, WINDOW,
 TREE, WATER, FENCE, VOID, UP, DOWN, FIELD, DIRTROAD) = range(20)
(FRIDGE, CABINET, WARDROBE, DESK, SHELF, MEDCAB, LOCKER, CRATE, MILCRATE, TOOLBOX,
 BED, TABLE, SOFA, WORKBENCH, COUNTER, PUMP, CAMPFIRE) = range(20, 37)
(ROCK, BUSH, BUSH_EMPTY, WOODWALL, STONEWALL, WOODDOOR, PATH, CHEST) = range(37, 45)

SOLID = bytearray(64)
for _t in (WALL, WINDOW, TREE, WATER, FENCE, VOID, ROCK, BUSH, BUSH_EMPTY, WOODWALL, STONEWALL, CHEST) + \
        tuple(range(20, 37)):
    SOLID[_t] = 1
ZSOLID = bytearray(SOLID)  # для зомби деревянная дверь тоже стена
ZSOLID[WOODDOOR] = 1
BULLET = bytearray(64)
for _t in (WALL, TREE, VOID, ROCK, WOODWALL, STONEWALL, WOODDOOR):
    BULLET[_t] = 1
SIGHT = bytearray(64)
for _t in (WALL, VOID, WOODWALL, STONEWALL, WOODDOOR):
    SIGHT[_t] = 1
# где можно строить
PLACEABLE = (GRASS, DIRT, SIDEWALK, CONCRETE, WOOD, TILEF, FIELD, DIRTROAD, PATH, ROAD, ROADV, ROADH)

CONTAINER = {FRIDGE: "fridge", CABINET: "cabinet", WARDROBE: "wardrobe", DESK: "desk", SHELF: "shelf",
             MEDCAB: "medcab", LOCKER: "locker", CRATE: "crate", MILCRATE: "milcrate", TOOLBOX: "toolbox",
             CHEST: "chest"}
TILE_NAMES = {FRIDGE: "Холодильник", CABINET: "Шкафчик", WARDROBE: "Шкаф", DESK: "Стол с ящиками",
              SHELF: "Стеллаж", MEDCAB: "Медшкаф", LOCKER: "Оружейный шкаф", CRATE: "Ящик",
              MILCRATE: "Военный ящик", TOOLBOX: "Ящик с инструментами", WORKBENCH: "Верстак",
              PUMP: "Бензоколонка", UP: "Лестница вверх", DOWN: "Лестница вниз", CAMPFIRE: "Костёр",
              CHEST: "Сундук", BUSH: "Ягодный куст", BED: "Кровать"}

# Строительство: ключ, название, тайл, стоимость
BUILDS = [
    ("wall", "Деревянная стена", WOODWALL, {"wood": 4}),
    ("door", "Деревянная дверь", WOODDOOR, {"wood": 3}),
    ("swall", "Каменная стена", STONEWALL, {"stone": 4}),
    ("floor", "Деревянный пол", WOOD, {"wood": 1}),
    ("chest", "Сундук", CHEST, {"wood": 5}),
    ("bed", "Кровать (точка возрождения)", BED, {"wood": 4, "berries": 2}),
    ("fire", "Костёр (свет ночью)", CAMPFIRE, {"wood": 3, "stone": 2}),
    ("bench", "Верстак", WORKBENCH, {"wood": 6, "stone": 2}),
]
BUILD_D = {k: (name, t, cost) for k, name, t, cost in BUILDS}
# добыча: тайл -> (предмет, прочность, количество, тайл после)
RESOURCES = {TREE: ("wood", 6, (2, 4), GRASS), ROCK: ("stone", 6, (2, 3), GRASS)}

KIND_LABEL = {"store": "МАГАЗИН", "police": "ПОЛИЦИЯ", "hospital": "БОЛЬНИЦА", "garage": "ГАРАЖ",
              "warehouse": "СКЛАД", "gas": "АЗС", "barracks": "КАЗАРМА", "barn": "АМБАР"}
BIOME_LABEL = {"trader": "Лагерь торговцев", "bandits": "Лагерь бандитов", "military": "Военная база"}

FLOOR_OF = {"house": WOOD, "apartment": WOOD, "store": TILEF, "police": TILEF, "hospital": TILEF,
            "garage": CONCRETE, "warehouse": CONCRETE, "gas": TILEF, "barracks": CONCRETE,
            "farmhouse": WOOD, "barn": WOOD, "cabin": WOOD, "shack": WOOD}
SIZES = {
    "house": ((9, 13), (8, 11), (1, 2)),
    "apartment": ((12, 16), (10, 14), (3, 4)),
    "store": ((11, 15), (9, 11), (1, 1)),
    "police": ((12, 15), (10, 12), (2, 2)),
    "hospital": ((14, 18), (11, 13), (3, 3)),
    "garage": ((10, 13), (8, 10), (1, 1)),
    "warehouse": ((12, 16), (10, 12), (1, 2)),
    "gas": ((9, 11), (7, 8), (1, 1)),
    "barracks": ((11, 14), (8, 10), (1, 2)),
    "farmhouse": ((9, 12), (8, 10), (1, 2)),
    "barn": ((10, 14), (8, 11), (1, 1)),
    "cabin": ((7, 9), (6, 8), (1, 1)),
    "shack": ((6, 7), (5, 6), (1, 1)),
}
_HOME = [(CABINET, 3), (WARDROBE, 3), (DESK, 2), (BED, 3), (SOFA, 2), (TABLE, 2), (FRIDGE, 2)]
FURN = {
    "house": _HOME, "apartment": _HOME, "farmhouse": _HOME,
    "police": [(LOCKER, 4), (DESK, 3), (CABINET, 2), (TABLE, 1)],
    "hospital": [(MEDCAB, 4), (BED, 4), (DESK, 2), (CABINET, 1)],
    "garage": [(TOOLBOX, 3), (CRATE, 4), (TABLE, 1)],
    "warehouse": [(CRATE, 5), (TOOLBOX, 1), (SHELF, 1)],
    "store": [(FRIDGE, 3), (SHELF, 2)],
    "gas": [(FRIDGE, 2), (SHELF, 3)],
    "barracks": [(MILCRATE, 3), (LOCKER, 3), (BED, 3)],
    "barn": [(CRATE, 4), (TOOLBOX, 2), (SHELF, 1)],
    "cabin": [(CABINET, 2), (BED, 2), (WARDROBE, 2), (TABLE, 1), (FRIDGE, 1)],
    "shack": [(CRATE, 3), (BED, 2), (CABINET, 1)],
}
FURN_P = {"house": 0.22, "apartment": 0.2, "police": 0.25, "hospital": 0.22, "garage": 0.3, "warehouse": 0.3,
          "store": 0.3, "gas": 0.35, "barracks": 0.28, "farmhouse": 0.22, "barn": 0.3, "cabin": 0.3, "shack": 0.35}
ZCOUNT = {"house": (0, 1), "apartment": (0, 2), "store": (1, 3), "police": (1, 3), "hospital": (2, 4),
          "garage": (0, 1), "warehouse": (1, 2), "gas": (0, 2), "barracks": (2, 4), "farmhouse": (0, 1),
          "barn": (0, 2), "cabin": (0, 1), "shack": (0, 0)}
NO_PARTITION = ("store", "gas", "warehouse", "garage", "barn", "cabin", "shack")
ZONES = {
    "downtown": [("apartment", 38), ("store", 14), ("police", 8), ("hospital", 8), ("garage", 7),
                 ("warehouse", 6), ("gas", 5), ("house", 4)],
    "city": [("house", 33), ("apartment", 18), ("store", 14), ("garage", 12), ("gas", 7), ("police", 5),
             ("warehouse", 6), ("hospital", 4)],
    "suburb": [("house", 60), ("garage", 10), ("warehouse", 7), ("store", 10), ("gas", 7), ("police", 2)],
    "farm": [("farmhouse", 3), ("barn", 2)],
}
HOUSE_ROOFS = [(150, 70, 50), (120, 60, 45), (95, 95, 110), (140, 100, 60), (110, 50, 50)]
ROOF = {"apartment": (95, 95, 105), "store": (70, 110, 140), "police": (40, 60, 120), "hospital": (205, 205, 210),
        "garage": (80, 80, 80), "warehouse": (110, 100, 80), "gas": (200, 60, 50), "barracks": (80, 95, 60),
        "barn": (150, 50, 40), "shack": (100, 110, 80)}
GABLE = ("house", "farmhouse", "cabin", "barn", "shack")
URBAN = ("downtown", "city", "suburb")


def _pick(rng, table):
    total = sum(w for _, w in table)
    r = rng.random() * total
    for v, w in table:
        r -= w
        if r <= 0:
            return v
    return table[-1][0]


def _hash(seed, x, y, salt=0):
    h = (x * 374761393 + y * 668265263 + seed * 2246822519 + salt * 3266489917) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return (h ^ (h >> 16)) / 4294967296.0


def _noise(seed, x, y, salt):
    x0, y0 = math.floor(x), math.floor(y)
    fx, fy = x - x0, y - y0
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = _hash(seed, x0, y0, salt)
    b = _hash(seed, x0 + 1, y0, salt)
    c = _hash(seed, x0, y0 + 1, salt)
    d = _hash(seed, x0 + 1, y0 + 1, salt)
    return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy


class Building:
    __slots__ = ("id", "x", "y", "w", "h", "kind", "floors", "roof", "doors")

    def __init__(self, bid, x, y, w, h, kind, floors, roof):
        self.id, self.x, self.y, self.w, self.h = bid, x, y, w, h
        self.kind, self.floors, self.roof = kind, floors, roof
        self.doors = []

    def contains(self, tx, ty):
        return self.x <= tx < self.x + self.w and self.y <= ty < self.y + self.h


class Chunk:
    __slots__ = ("cx", "cy", "levels", "bmap", "buildings", "car_spawns", "zombie_spawns", "npc_spawns",
                 "biome", "label")

    def __init__(self, cx, cy):
        self.cx, self.cy = cx, cy
        self.levels = [bytearray(CS * CS)]
        self.bmap = array("h", [-1]) * (CS * CS)
        self.buildings = []
        self.car_spawns = []
        self.zombie_spawns = []
        self.npc_spawns = []
        self.biome = ""
        self.label = ""


class World:
    def __init__(self, seed):
        self.seed = seed
        self.chunks = {}
        self._biomes = {}
        self._g = None
        self.edits = {}        # (lv, tx, ty) -> (тайл, исходный тайл)
        self._edits_by_chunk = {}

    # ---------------- изменения мира (стройка, вырубка) ----------------
    def apply_edit(self, lv, tx, ty, t, orig):
        key = (lv, tx, ty)
        ck = (tx >> 5, ty >> 5)
        if t == orig:
            self.edits.pop(key, None)
            self._edits_by_chunk.get(ck, set()).discard(key)
        else:
            self.edits[key] = (t, orig)
            self._edits_by_chunk.setdefault(ck, set()).add(key)
        c = self.chunks.get(ck)
        if c is not None and lv < len(c.levels):
            c.levels[lv][((ty & 31) << 5) | (tx & 31)] = t

    def set_tile(self, lv, tx, ty, t):
        """Меняет тайл, возвращает [lv, tx, ty, t, orig] для рассылки клиентам."""
        e = self.edits.get((lv, tx, ty))
        orig = e[1] if e else self.tile(lv, tx, ty)
        self.apply_edit(lv, tx, ty, t, orig)
        return [lv, tx, ty, t, orig]

    def orig_tile(self, lv, tx, ty):
        e = self.edits.get((lv, tx, ty))
        return e[1] if e else None

    def export_edits(self):
        return [[lv, tx, ty, t, o] for (lv, tx, ty), (t, o) in self.edits.items()]

    def load_edits(self, rows):
        for lv, tx, ty, t, o in rows:
            self.apply_edit(lv, tx, ty, t, o)

    # ---------------- биомы ----------------
    def biome(self, cx, cy):
        k = (cx, cy)
        b = self._biomes.get(k)
        if b:
            return b
        s = self.seed
        if k == (0, 0):
            b = "wild"          # старт за городом
        elif k == (1, 1):
            b = "trader"
        elif max(abs(cx), abs(cy)) <= 1:
            b = ("farm", "forest", "wild", "farm")[int(_hash(s, cx, cy, 6) * 4)]
        else:
            u = 0.6 * _noise(s, cx / 6.0, cy / 6.0, 1) + 0.4 * _noise(s, cx / 2.5, cy / 2.5, 2)
            sp = _hash(s, cx, cy, 3)
            if u > 0.66:
                b = "downtown"
            elif u > 0.57:
                b = "city"
            elif u > 0.48:
                b = "bandits" if sp < 0.04 else ("trader" if sp < 0.08 else "suburb")
            else:
                f = _noise(s, cx / 4.0, cy / 4.0, 4)
                if sp < 0.02:
                    b = "military"
                elif sp < 0.06:
                    b = "bandits"
                elif sp < 0.095:
                    b = "trader"
                elif f > 0.55:
                    b = "forest"
                else:
                    r = _hash(s, cx, cy, 5)
                    b = "farm" if r < 0.45 else ("park" if r < 0.6 else "wild")
        self._biomes[k] = b
        return b

    def urban(self, cx, cy):
        return self.biome(cx, cy) in URBAN

    # ---------------- доступ ----------------
    def chunk(self, cx, cy):
        c = self.chunks.get((cx, cy))
        if c is None:
            c = self._gen_chunk(cx, cy)
            for (lv, tx, ty) in self._edits_by_chunk.get((cx, cy), ()):
                if lv < len(c.levels):
                    c.levels[lv][((ty & 31) << 5) | (tx & 31)] = self.edits[(lv, tx, ty)][0]
            self.chunks[(cx, cy)] = c
        return c

    def tile(self, lv, tx, ty):
        if lv < 0 or lv >= MAX_LV:
            return VOID
        c = self.chunks.get((tx >> 5, ty >> 5))
        if c is None:
            c = self.chunk(tx >> 5, ty >> 5)
        if lv >= len(c.levels):
            return VOID
        return c.levels[lv][((ty & 31) << 5) | (tx & 31)]

    def solid(self, lv, tx, ty):
        return SOLID[self.tile(lv, tx, ty)]

    def building_at_tile(self, tx, ty):
        c = self.chunks.get((tx >> 5, ty >> 5)) or self.chunk(tx >> 5, ty >> 5)
        i = c.bmap[((ty & 31) << 5) | (tx & 31)]
        return c.buildings[i] if i >= 0 else None

    def bid_at(self, px, py):
        return self.building_at_tile(int(px // TILE), int(py // TILE))

    def buildings_in(self, tx0, ty0, tx1, ty1):
        for cy in range((ty0 >> 5), (ty1 >> 5) + 1):
            for cx in range((tx0 >> 5), (tx1 >> 5) + 1):
                for b in self.chunk(cx, cy).buildings:
                    if b.x <= tx1 and b.y <= ty1 and b.x + b.w > tx0 and b.y + b.h > ty0:
                        yield b

    def find_spawn(self, rng, cx, cy):
        for attempt in range(40):
            ccx, ccy = (cx, cy) if attempt < 3 else (cx + rng.randint(-2, 2), cy + rng.randint(-2, 2))
            c = self.chunk(ccx, ccy)
            L = c.levels[0]
            cands = [i for i in range(CS * CS) if L[i] == SIDEWALK] or \
                    [i for i in range(CS * CS) if L[i] in (ROAD, DIRTROAD)]
            if not cands:
                continue
            i = rng.choice(cands)
            x, y = (ccx * CS + (i & 31)) * TILE + 16, (ccy * CS + (i >> 5)) * TILE + 16
            if self.circle_free(0, x, y, 13):
                return x, y
        return 16.0, 16.0

    def circle_free(self, lv, x, y, r, table=SOLID):
        T = TILE
        x0, x1 = int((x - r) // T), int((x + r) // T)
        y0, y1 = int((y - r) // T), int((y + r) // T)
        rr = r * r
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                if table[self.tile(lv, tx, ty)]:
                    cx = min(max(x, tx * T), tx * T + T)
                    cy = min(max(y, ty * T), ty * T + T)
                    if (x - cx) ** 2 + (y - cy) ** 2 < rr:
                        return False
        return True

    def move(self, lv, x, y, dx, dy, r, table=SOLID):
        hit = False
        steps = int(max(abs(dx), abs(dy)) // (r * 0.7)) + 1
        sx, sy = dx / steps, dy / steps
        for _ in range(steps):
            if sx:
                if self.circle_free(lv, x + sx, y, r, table):
                    x += sx
                else:
                    hit = True
            if sy:
                if self.circle_free(lv, x, y + sy, r, table):
                    y += sy
                else:
                    hit = True
        return x, y, hit

    def ray(self, lv, x, y, dx, dy, maxd, table=BULLET):
        T = TILE
        d = 0.0
        while d < maxd:
            d += 8
            if table[self.tile(lv, int((x + dx * d) // T), int((y + dy * d) // T))]:
                return max(0.0, d - 4)
        return maxd

    def los(self, lv, x1, y1, x2, y2):
        dist = math.hypot(x2 - x1, y2 - y1)
        if dist < 1:
            return True
        return self.ray(lv, x1, y1, (x2 - x1) / dist, (y2 - y1) / dist, dist, SIGHT) >= dist - 6

    # ---------------- генерация чанка ----------------
    def _get(self, lv, tx, ty):
        c = self._g
        lx, ly = tx - c.cx * CS, ty - c.cy * CS
        if 0 <= lx < CS and 0 <= ly < CS:
            if lv < len(c.levels):
                return c.levels[lv][ly * CS + lx]
            return VOID
        return GRASS if lv == 0 else VOID

    def _set(self, lv, tx, ty, t):
        c = self._g
        lx, ly = tx - c.cx * CS, ty - c.cy * CS
        if 0 <= lx < CS and 0 <= ly < CS:
            while len(c.levels) <= lv:
                c.levels.append(bytearray([VOID]) * (CS * CS))
            c.levels[lv][ly * CS + lx] = t

    def _bget(self, tx, ty):
        c = self._g
        lx, ly = tx - c.cx * CS, ty - c.cy * CS
        if 0 <= lx < CS and 0 <= ly < CS:
            return c.bmap[ly * CS + lx]
        return -1

    def _free_local(self, lv, x, y, r):
        T = TILE
        for ty in range(int((y - r) // T), int((y + r) // T) + 1):
            for tx in range(int((x - r) // T), int((x + r) // T) + 1):
                if SOLID[self._get(lv, tx, ty)]:
                    cx = min(max(x, tx * T), tx * T + T)
                    cy = min(max(y, ty * T), ty * T + T)
                    if (x - cx) ** 2 + (y - cy) ** 2 < r * r:
                        return False
        return True

    def _gen_chunk(self, cx, cy):
        c = Chunk(cx, cy)
        self._g = c
        rng = random.Random("%d:%d:%d" % (self.seed, cx, cy))
        ox, oy = cx * CS, cy * CS
        bio = self.biome(cx, cy)
        c.biome = bio
        c.label = BIOME_LABEL.get(bio, "")
        L = c.levels[0]
        L[:] = bytes([GRASS]) * (CS * CS)
        # дороги: вертикальная слева, горизонтальная сверху
        left = self.urban(cx - 1, cy) or self.urban(cx, cy)
        top = self.urban(cx, cy - 1) or self.urban(cx, cy)
        cross = left or top or self.urban(cx - 1, cy - 1)
        for ly in range(CS):
            for lx in range(3):
                if ly < 3:
                    t = ROAD if cross else DIRTROAD
                else:
                    t = (ROADV if lx == 1 else ROAD) if left else DIRTROAD
                L[ly * CS + lx] = t
        for ly in range(3):
            for lx in range(3, CS):
                L[ly * CS + lx] = (ROADH if ly == 1 else ROAD) if top else DIRTROAD
        if bio in URBAN:
            for i in range(3, CS):
                for lx, ly in ((3, i), (31, i), (i, 3), (i, 31)):
                    L[ly * CS + lx] = SIDEWALK
        block = (ox + 4, oy + 4, 27, 27)
        if bio in URBAN:
            self._fill_block(rng, block, bio)
        elif bio == "military":
            self._military(rng, block)
        elif bio == "park":
            self._pond(rng, block, 0.07)
        elif bio in ("trader", "bandits"):
            self._camp(rng, block, bio)
        elif bio == "farm":
            self._farm(rng, block)
        elif bio == "forest":
            if rng.random() < 0.45:
                self._lone(rng, block, "cabin")
            elif rng.random() < 0.2:
                self._pond(rng, block, 0.0)
        else:
            r = rng.random()
            if r < 0.3:
                self._lone(rng, block, rng.choice(("house", "gas", "farmhouse")))
            elif r < 0.5:
                self._pond(rng, block, 0.03)
        tree_p = {"forest": 0.33, "wild": 0.06, "farm": 0.03, "suburb": 0.03, "city": 0.012, "downtown": 0.0,
                  "trader": 0.05, "bandits": 0.06, "military": 0.0, "park": 0.0}[bio]
        rock_p = {"forest": 0.015, "wild": 0.025, "farm": 0.006, "park": 0.01, "bandits": 0.01}.get(bio, 0.0)
        bush_p = {"forest": 0.03, "wild": 0.03, "farm": 0.02, "park": 0.03, "suburb": 0.008, "trader": 0.02,
                  "bandits": 0.01}.get(bio, 0.0)
        if tree_p or rock_p or bush_p:
            for ly in range(4, CS - 1):
                for lx in range(4, CS - 1):
                    if L[ly * CS + lx] != GRASS:
                        continue
                    r = rng.random()
                    if r < tree_p + rock_p + bush_p and self._clear_around(ox + lx, oy + ly):
                        L[ly * CS + lx] = TREE if r < tree_p else (ROCK if r < tree_p + rock_p else BUSH)
        if (cx, cy) == (0, 0):
            # стартовая стоянка у дороги: костёр и пара кустов
            for (lx, ly, t) in ((8, 8, CAMPFIRE), (11, 6, BUSH), (6, 11, BUSH), (13, 10, ROCK)):
                if L[ly * CS + lx] in (GRASS, TREE) and c.bmap[ly * CS + lx] < 0:
                    L[ly * CS + lx] = t
        # машины на дорогах
        if rng.random() < (0.55 if left else 0.15):
            ty = oy + rng.randint(6, 28)
            lane = rng.choice((0, 2))
            self._try_car(ox + lane, ty, math.pi / 2 if lane == 0 else -math.pi / 2)
        if rng.random() < (0.55 if top else 0.15):
            tx = ox + rng.randint(6, 28)
            lane = rng.choice((0, 2))
            self._try_car(tx, oy + lane, math.pi if lane == 0 else 0.0)
        # бродячие выжившие и бандиты внутри зданий
        for b in c.buildings:
            if b.kind == "shack":
                continue
            r = rng.random()
            if r < 0.07:
                tx, ty = b.x + b.w // 2, b.y + b.h // 2
                if not SOLID[self._get(0, tx, ty)]:
                    c.npc_spawns.append((tx * TILE + 16, ty * TILE + 16, 0, "bandit" if r < 0.045 else "surv"))
        self._g = None
        return c

    def _try_car(self, tx, ty, ang):
        x, y = tx * TILE + 16, ty * TILE + 16
        ca, sa = math.cos(ang), math.sin(ang)
        for off in (-20, 0, 20):
            if not self._free_local(0, x + ca * off, y + sa * off, 17):
                return
        for (cx, cy, _) in self._g.car_spawns:
            if abs(cx - x) < 90 and abs(cy - y) < 90:
                return
        self._g.car_spawns.append((x, y, ang))

    def _clear_around(self, tx, ty):
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                if self._get(0, tx + ox, ty + oy) not in (GRASS, TREE, SIDEWALK, FIELD) or \
                        self._bget(tx + ox, ty + oy) >= 0:
                    return False
        return True

    def _pond(self, rng, b, trees):
        bx, by, bw, bh = b
        cx, cy = bx + bw / 2 + rng.uniform(-3, 3), by + bh / 2 + rng.uniform(-3, 3)
        rx, ry = rng.uniform(3, 7), rng.uniform(3, 6)
        for ty in range(by, by + bh):
            for tx in range(bx, bx + bw):
                if ((tx + 0.5 - cx) / rx) ** 2 + ((ty + 0.5 - cy) / ry) ** 2 < 1:
                    self._set(0, tx, ty, WATER)
                elif rng.random() < trees:
                    self._set(0, tx, ty, TREE)

    def _lone(self, rng, b, kind):
        bx, by, bw, bh = b
        (w0, w1), (h0, h1), (f0, f1) = SIZES[kind]
        w, h = rng.randint(w0, w1), rng.randint(h0, h1)
        x, y = rng.randint(bx + 3, bx + bw - 3 - w), rng.randint(by + 3, by + bh - 3 - h)
        side = rng.choice("NSWE") if kind != "gas" else "S"
        if kind == "gas":
            y = min(y, by + bh - h - 5)
        self._building(rng, x, y, w, h, kind, rng.randint(f0, f1), side)

    def _farm(self, rng, b):
        bx, by, bw, bh = b
        half = bw // 2
        left_fields = rng.random() < 0.5
        fx = bx if left_fields else bx + half + 1
        for ty in range(by + 1, by + bh - 1):
            for tx in range(fx + 1, fx + half - 1):
                self._set(0, tx, ty, FIELD)
        hx = bx + half + 1 if left_fields else bx
        self._fill_lots(rng, (hx, by, half - 1, bh), "farm", bx, by, bw, bh, 14)

    def _camp(self, rng, b, bio):
        bx, by, bw, bh = b
        x0, y0, s = bx + 3, by + 3, 21
        for ty in range(y0, y0 + s):
            for tx in range(x0, x0 + s):
                edge = tx in (x0, x0 + s - 1) or ty in (y0, y0 + s - 1)
                self._set(0, tx, ty, FENCE if edge else DIRT)
        for k in range(-1, 2):
            self._set(0, x0 + s // 2 + k, y0 + s - 1, DIRT)
            self._set(0, x0 + s // 2 + k, y0, DIRT)
        mx, my = x0 + s // 2, y0 + s // 2
        self._set(0, mx, my, CAMPFIRE)
        self._building(rng, x0 + 2, y0 + 2, rng.randint(6, 7), rng.randint(5, 6), "shack", 1, "S")
        self._building(rng, x0 + s - 9, y0 + 2, rng.randint(6, 7), rng.randint(5, 6), "shack", 1, "S")
        spots = [(x0 + 3, y0 + s - 3), (x0 + s - 4, y0 + s - 3), (x0 + 2, y0 + s - 5), (x0 + s - 3, y0 + s - 6)]
        for i, (tx, ty) in enumerate(spots):
            if bio == "trader":
                self._set(0, tx, ty, WORKBENCH if i == 0 else CRATE)
            else:
                self._set(0, tx, ty, MILCRATE if i < 2 else CRATE)
        g = self._g
        px = lambda tx, ty: (tx * TILE + 16, ty * TILE + 16, 0)  # noqa: E731
        if bio == "trader":
            g.npc_spawns.append(px(mx, my + 2) + ("trader",))
            g.npc_spawns.append(px(mx - 4, my + 6) + ("guard",))
            if rng.random() < 0.6:
                g.npc_spawns.append(px(mx + 4, my + 6) + ("guard",))
            if rng.random() < 0.5:
                g.npc_spawns.append(px(mx + 2, my - 2) + ("surv",))
        else:
            for k in range(rng.randint(3, 5)):
                g.npc_spawns.append(px(mx + rng.randint(-5, 5), my + rng.randint(1, 6)) + ("bandit",))

    def _military(self, rng, b):
        bx, by, bw, bh = b
        for ty in range(by, by + bh):
            for tx in range(bx, bx + bw):
                edge = tx in (bx, bx + bw - 1) or ty in (by, by + bh - 1)
                self._set(0, tx, ty, FENCE if edge else DIRT)
        for k in range(-2, 2):
            self._set(0, bx + bw // 2 + k, by + bh - 1, DIRT)
            self._set(0, bx, by + bh // 2 + k, DIRT)
        rects = []
        for _ in range(40):
            if len(rects) >= 2:
                break
            (w0, w1), (h0, h1), (f0, f1) = SIZES["barracks"]
            w, h = rng.randint(w0, w1), rng.randint(h0, h1)
            x, y = rng.randint(bx + 3, bx + bw - 3 - w), rng.randint(by + 3, by + bh - 3 - h)
            if any(x < rx + rw + 3 and rx < x + w + 3 and y < ry + rh + 3 and ry < y + h + 3
                   for rx, ry, rw, rh in rects):
                continue
            rects.append((x, y, w, h))
            dists = {"W": x - bx, "E": bx + bw - (x + w), "N": y - by, "S": by + bh - (y + h)}
            self._building(rng, x, y, w, h, "barracks", rng.randint(f0, f1), min(dists, key=dists.get))
        placed = 0
        for _ in range(200):
            if placed >= 8:
                break
            tx, ty = rng.randint(bx + 2, bx + bw - 3), rng.randint(by + 2, by + bh - 3)
            ok = all(self._get(0, tx + ox, ty + oy) == DIRT and self._bget(tx + ox, ty + oy) < 0
                     for oy in (-1, 0, 1) for ox in (-1, 0, 1))
            if ok:
                self._set(0, tx, ty, MILCRATE)
                placed += 1
        for _ in range(7):
            tx, ty = rng.randint(bx + 2, bx + bw - 3), rng.randint(by + 2, by + bh - 3)
            if self._get(0, tx, ty) == DIRT and self._bget(tx, ty) < 0:
                self._g.zombie_spawns.append((tx * TILE + 16, ty * TILE + 16, 0,
                                              "brute" if rng.random() < 0.35 else "walker"))

    def _split(self, rng, x, y, w, h, maxs, out, once):
        can_w = w > maxs and w >= 20
        can_h = h > maxs and h >= 20
        if can_w and (w >= h or not can_h):
            c = rng.randint(10, w - 10)
            parts = [(x, y, c, h), (x + c, y, w - c, h)]
        elif can_h:
            c = rng.randint(10, h - 10)
            parts = [(x, y, w, c), (x, y + c, w, h - c)]
        else:
            out.append((x, y, w, h))
            return
        for p in parts:
            if once:
                out.append(p)
            else:
                self._split(rng, *p, maxs, out, once)

    def _fill_block(self, rng, b, zone):
        bx, by, bw, bh = b
        self._fill_lots(rng, b, zone, bx, by, bw, bh,
                        20 if zone == "downtown" else (14 if zone == "suburb" else 17))

    def _fill_lots(self, rng, area, zone, bx, by, bw, bh, maxs):
        lots = []
        self._split(rng, *area, maxs, lots, zone == "downtown")
        for (lx, ly, lw, lh) in lots:
            if zone == "suburb" and rng.random() < 0.07:
                continue
            dists = {"W": lx - bx, "E": bx + bw - (lx + lw), "N": ly - by, "S": by + bh - (ly + lh)}
            side = min(dists, key=dists.get)
            for kind in [_pick(rng, ZONES[zone]) for _ in range(8)]:
                ax, ay, aw, ah = lx + 1, ly + 1, lw - 2, lh - 2
                if kind == "gas":
                    if side == "S":
                        ah -= 3
                    elif side == "N":
                        ay += 3
                        ah -= 3
                    elif side == "E":
                        aw -= 3
                    else:
                        ax += 3
                        aw -= 3
                (w0, w1), (h0, h1), (f0, f1) = SIZES[kind]
                opts = []
                if w0 <= aw and h0 <= ah:
                    opts.append((w0, w1, h0, h1))
                if h0 <= aw and w0 <= ah:
                    opts.append((h0, h1, w0, w1))
                if not opts:
                    continue
                a0, a1, c0, c1 = rng.choice(opts)
                w, h = rng.randint(a0, min(a1, aw)), rng.randint(c0, min(c1, ah))
                x, y = rng.randint(ax, ax + aw - w), rng.randint(ay, ay + ah - h)
                self._building(rng, x, y, w, h, kind, rng.randint(f0, f1), side)
                break

    def _door_tiles(self, x, y, w, h, side, width):
        out = []
        for k in range(width):
            o = k - width // 2
            if side == "S":
                out.append((x + w // 2 + o, y + h - 1))
            elif side == "N":
                out.append((x + w // 2 + o, y))
            elif side == "W":
                out.append((x, y + h // 2 + o))
            else:
                out.append((x + w - 1, y + h // 2 + o))
        return out

    def _building(self, rng, x, y, w, h, kind, floors, side):
        g = self._g
        roof = rng.choice(HOUSE_ROOFS) if kind in ("house", "farmhouse", "cabin") else ROOF[kind]
        bi = len(g.buildings)
        b = Building((g.cx, g.cy, bi), x, y, w, h, kind, floors, roof)
        g.buildings.append(b)
        get, put = self._get, self._set
        floor_t = FLOOR_OF[kind]
        opposite = {"S": "N", "N": "S", "W": "E", "E": "W"}[side]
        dwidth = 3 if kind in ("garage", "barn") else (2 if kind in ("store", "warehouse") else 1)
        doors = self._door_tiles(x, y, w, h, side, dwidth)
        if rng.random() < 0.45 and kind not in ("gas", "shack"):
            doors += self._door_tiles(x, y, w, h, opposite, 1)
        b.doors = doors
        for lv in range(floors):
            for ty in range(y, y + h):
                for tx in range(x, x + w):
                    edge = tx == x or tx == x + w - 1 or ty == y or ty == y + h - 1
                    put(lv, tx, ty, WALL if edge else floor_t)
                    if lv == 0:
                        g.bmap[(ty - g.cy * CS) * CS + tx - g.cx * CS] = bi
            for tx in range(x + 1, x + w - 1):
                for ty in (y, y + h - 1):
                    if (tx - x) % 3 == 1 and rng.random() < 0.75:
                        put(lv, tx, ty, WINDOW)
            for ty in range(y + 1, y + h - 1):
                for tx in (x, x + w - 1):
                    if (ty - y) % 3 == 1 and rng.random() < 0.75:
                        put(lv, tx, ty, WINDOW)
            nogo = set()
            if lv == 0:
                for (tx, ty) in doors:
                    put(lv, tx, ty, DOOR)
                    nogo.add((tx, ty))
            if floors > 1:
                if lv < floors - 1:
                    put(lv, x + 1, y + 1, UP)
                if lv > 0:
                    put(lv, x + 2, y + 1, DOWN)
                for ty in (y + 1, y + 2):
                    for tx in (x + 1, x + 2, x + 3):
                        nogo.add((tx, ty))
            part = set()
            if kind not in NO_PARTITION:
                part = self._partitions(rng, lv, x, y, w, h, doors if lv == 0 else [])
            if kind in ("store", "warehouse") and h >= 9:
                mid = x + w // 2
                for ry in range(y + 3, y + h - 3, 3):
                    for rx in range(x + 3, x + w - 3):
                        if abs(rx - mid) <= (1 if kind == "warehouse" else 0):
                            continue
                        if kind == "warehouse" and rng.random() < 0.35:
                            continue
                        put(lv, rx, ry, SHELF if kind == "store" else CRATE)
                        part.add((rx, ry))
            cands = []
            for ty in range(y + 1, y + h - 1):
                for tx in range(x + 1, x + w - 1):
                    if get(lv, tx, ty) != floor_t:
                        continue
                    if not (tx == x + 1 or tx == x + w - 2 or ty == y + 1 or ty == y + h - 2):
                        continue
                    if any((tx + ox, ty + oy) in nogo or (tx + ox, ty + oy) in part
                           for oy in (-1, 0, 1) for ox in (-1, 0, 1)):
                        continue
                    cands.append((tx, ty))
            rng.shuffle(cands)
            need_bench = lv == 0 and (kind == "garage" or (kind in ("warehouse", "barracks", "barn")
                                                           and rng.random() < 0.5))
            for (tx, ty) in cands:
                if need_bench:
                    put(lv, tx, ty, WORKBENCH)
                    need_bench = False
                elif rng.random() < FURN_P[kind]:
                    put(lv, tx, ty, _pick(rng, FURN[kind]))
            self._fix_reach(lv, b, doors[0] if lv == 0 else (x + 2, y + 1), floor_t)
            free = [(tx, ty) for ty in range(y + 1, y + h - 1) for tx in range(x + 1, x + w - 1)
                    if not SOLID[get(lv, tx, ty)] and get(lv, tx, ty) not in (UP, DOWN)]
            for _ in range(rng.randint(*ZCOUNT[kind])):
                if free:
                    tx, ty = rng.choice(free)
                    r = rng.random()
                    zt = "brute" if r < 0.1 else ("runner" if r < 0.25 else "walker")
                    g.zombie_spawns.append((tx * TILE + 16, ty * TILE + 16, lv, zt))
        # дорожка от каждой входной двери наружу - чтобы вход было видно издалека
        for (dx, dy) in doors:
            ox_, oy_ = (0, -1) if dy == y else (0, 1) if dy == y + h - 1 else (-1, 0) if dx == x else (1, 0)
            for k in range(1, 14):
                px, py = dx + ox_ * k, dy + oy_ * k
                if get(0, px, py) not in (GRASS, FIELD, TREE) or self._bget(px, py) >= 0:
                    break
                put(0, px, py, PATH)
        if kind == "gas":
            nx, ny = {"S": (0, 1), "N": (0, -1), "E": (1, 0), "W": (-1, 0)}[side]
            dx, dy = doors[0]
            for o in (-2, 2):
                px, py = dx + nx * 2 + ny * o, dy + ny * 2 + nx * o
                for oy in (-1, 0, 1):
                    for ox in (-1, 0, 1):
                        if get(0, px + ox, py + oy) in (GRASS, TREE):
                            put(0, px + ox, py + oy, CONCRETE)
                put(0, px, py, PUMP)
        if kind in ("garage", "barn"):
            nx, ny = {"S": (0, 1), "N": (0, -1), "E": (1, 0), "W": (-1, 0)}[side]
            dx, dy = doors[1] if len(doors) > 1 else doors[0]
            tx, ty = dx + nx * 2, dy + ny * 2
            if get(0, tx, ty) in (GRASS, SIDEWALK, CONCRETE, PATH):
                for k in range(1, 3):
                    if get(0, dx + nx * k, dy + ny * k) in (GRASS, PATH):
                        put(0, dx + nx * k, dy + ny * k, CONCRETE)
                self._try_car(tx, ty, math.atan2(ny, nx))
        return b

    def _fix_reach(self, lv, b, start, floor_t):
        """Убирает мебель, если она отрезала часть комнаты."""
        get, put = self._get, self._set
        for _ in range(8):
            seen = {start}
            stack = [start]
            while stack:
                x, y = stack.pop()
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if b.contains(nx, ny) and (nx, ny) not in seen and not SOLID[get(lv, nx, ny)]:
                        seen.add((nx, ny))
                        stack.append((nx, ny))
            lost = [(tx, ty) for ty in range(b.y + 1, b.y + b.h - 1) for tx in range(b.x + 1, b.x + b.w - 1)
                    if not SOLID[get(lv, tx, ty)] and (tx, ty) not in seen]
            if not lost:
                return
            for tx, ty in lost:
                for nx, ny in ((tx + 1, ty), (tx - 1, ty), (tx, ty + 1), (tx, ty - 1)):
                    if get(lv, nx, ny) >= 20:
                        put(lv, nx, ny, floor_t)

    def _partitions(self, rng, lv, x, y, w, h, doors):
        put = self._set
        part = set()
        dcols = [tx for (tx, ty) in doors if ty in (y, y + h - 1)]
        drows = [ty for (tx, ty) in doors if tx in (x, x + w - 1)]
        px = py = None
        if w >= 12 or (w >= 11 and rng.random() < 0.6):
            for _ in range(10):
                c = rng.randint(x + 5, x + w - 6)
                if all(abs(c - d) > 1 for d in dcols):
                    px = c
                    break
        if h >= 10 or (h >= 9 and rng.random() < 0.5):
            for _ in range(10):
                r = rng.randint(y + 4, y + h - 5)
                if all(abs(r - d) > 1 for d in drows):
                    py = r
                    break
        if px is not None:
            for ty in range(y + 1, y + h - 1):
                put(lv, px, ty, WALL)
                part.add((px, ty))
        if py is not None:
            for tx in range(x + 1, x + w - 1):
                put(lv, tx, py, WALL)
                part.add((tx, py))
        if px is not None:
            segs = [(y + 1, py - 1), (py + 1, y + h - 2)] if py is not None else [(y + 1, y + h - 2)]
            for s0, s1 in segs:
                if s1 >= s0:
                    put(lv, px, rng.randint(s0, s1), DOOR)
        if py is not None:
            segs = [(x + 1, px - 1), (px + 1, x + w - 2)] if px is not None else [(x + 1, x + w - 2)]
            for s0, s1 in segs:
                if s1 >= s0:
                    put(lv, rng.randint(s0, s1), py, DOOR)
        return part
