"""Отрисовка тайлов, зданий, крыш, сущностей и иконок предметов."""
import math
from collections import OrderedDict

import pygame

from . import items as IT
from . import ui
from .config import TILE
from .world import (GRASS, ROAD, ROADV, ROADH, SIDEWALK, WOOD, TILEF, CONCRETE, DIRT, WALL, DOOR, WINDOW, TREE,
                    WATER, FENCE, VOID, UP, DOWN, FIELD, DIRTROAD, FRIDGE, CABINET, WARDROBE, DESK, SHELF, MEDCAB,
                    LOCKER, CRATE, MILCRATE, TOOLBOX, BED, TABLE, SOFA, WORKBENCH, COUNTER, PUMP, CAMPFIRE,
                    ROCK, BUSH, BUSH_EMPTY, WOODWALL, STONEWALL, WOODDOOR, PATH, CHEST,
                    FLOOR_OF, KIND_LABEL, GABLE, CS)

CH = 16
MINI = {GRASS: (62, 110, 52), ROAD: (58, 58, 62), ROADV: (58, 58, 62), ROADH: (58, 58, 62),
        SIDEWALK: (140, 140, 140), CONCRETE: (120, 120, 118), DIRT: (120, 95, 60), TREE: (30, 75, 35),
        WATER: (40, 90, 160), FENCE: (90, 90, 90), PUMP: (200, 50, 40), MILCRATE: (90, 100, 60),
        FIELD: (130, 120, 55), DIRTROAD: (130, 105, 70), CAMPFIRE: (255, 150, 40), ROCK: (120, 120, 125),
        BUSH: (60, 120, 50), BUSH_EMPTY: (60, 100, 50), WOODWALL: (120, 80, 45), STONEWALL: (110, 110, 115),
        WOODDOOR: (150, 100, 55), PATH: (175, 160, 130), WOOD: (140, 100, 62), CHEST: (150, 100, 50)}
FLOORS = (GRASS, ROAD, ROADV, ROADH, SIDEWALK, WOOD, TILEF, CONCRETE, DIRT, WATER, FIELD, DIRTROAD, PATH)
NATURE = (ROCK, BUSH, BUSH_EMPTY)


def _h(tx, ty):
    return ((tx * 73856093) ^ (ty * 19349663)) & 0xFFFF


def _shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def draw_floor(s, t, x, y, tx, ty):
    h = _h(tx, ty)
    if t == GRASS:
        c = (62 + (h % 7), 110 + (h % 9), 52)
        pygame.draw.rect(s, c, (x, y, TILE, TILE))
        for k in range(3):
            hx, hy = (h >> (k * 3)) % 28 + 2, (h >> (k * 4 + 1)) % 28 + 2
            pygame.draw.line(s, (48, 92, 40), (x + hx, y + hy), (x + hx + 1, y + hy - 3))
    elif t in (ROAD, ROADV, ROADH):
        pygame.draw.rect(s, (58 + h % 4, 58 + h % 4, 62), (x, y, TILE, TILE))
        if h % 11 == 0:
            pygame.draw.line(s, (45, 45, 48), (x + h % 20, y + 5), (x + h % 20 + 8, y + 14))
        if t == ROADV and ty % 2 == 0:
            pygame.draw.rect(s, (220, 190, 60), (x + 14, y + 4, 4, 24))
        if t == ROADH and tx % 2 == 0:
            pygame.draw.rect(s, (220, 190, 60), (x + 4, y + 14, 24, 4))
    elif t == SIDEWALK:
        pygame.draw.rect(s, (148, 148, 146), (x, y, TILE, TILE))
        pygame.draw.rect(s, (125, 125, 124), (x, y, TILE, TILE), 1)
    elif t == WOOD:
        pygame.draw.rect(s, (140, 100, 62), (x, y, TILE, TILE))
        for k in range(4):
            pygame.draw.line(s, (118, 82, 50), (x, y + k * 8), (x + TILE, y + k * 8))
            ox = ((h >> k) % 4) * 8
            pygame.draw.line(s, (118, 82, 50), (x + ox, y + k * 8), (x + ox, y + k * 8 + 8))
    elif t == TILEF:
        for i in range(2):
            for j in range(2):
                c = (205, 205, 198) if (i + j) % 2 == 0 else (182, 182, 176)
                pygame.draw.rect(s, c, (x + i * 16, y + j * 16, 16, 16))
    elif t == CONCRETE:
        pygame.draw.rect(s, (120, 120, 118), (x, y, TILE, TILE))
        for k in range(4):
            pygame.draw.rect(s, (108, 108, 106), (x + (h >> k) % 30, y + (h >> (k + 3)) % 30, 2, 2))
    elif t == DIRT:
        pygame.draw.rect(s, (120 + h % 6, 95, 60), (x, y, TILE, TILE))
        for k in range(3):
            pygame.draw.rect(s, (100, 80, 50), (x + (h >> k) % 30, y + (h >> (k + 2)) % 30, 3, 2))
    elif t == FIELD:
        pygame.draw.rect(s, (115, 85, 50), (x, y, TILE, TILE))
        for k in range(4):
            pygame.draw.line(s, (95, 150, 60) if (h >> 3) % 5 else (170, 160, 60), (x + 4 + k * 8, y + 2),
                             (x + 4 + k * 8, y + 30), 4)
    elif t == PATH:
        pygame.draw.rect(s, (110, 150, 80), (x, y, TILE, TILE))
        for i in range(2):
            for j in range(2):
                pygame.draw.rect(s, (182 - (h >> (i + j)) % 14, 168, 135), (x + 2 + i * 15, y + 2 + j * 15, 13, 13),
                                 border_radius=3)
    elif t == DIRTROAD:
        pygame.draw.rect(s, (128, 102, 68), (x, y, TILE, TILE))
        for k in range(3):
            pygame.draw.rect(s, (110, 88, 58), (x + (h >> k) % 28, y + (h >> (k + 2)) % 28, 4, 3))
    elif t == WATER:
        pygame.draw.rect(s, (40, 90, 160), (x, y, TILE, TILE))
        pygame.draw.line(s, (70, 120, 190), (x + h % 16, y + 10), (x + h % 16 + 10, y + 10), 2)
        pygame.draw.line(s, (70, 120, 190), (x + (h >> 4) % 16, y + 24), (x + (h >> 4) % 16 + 8, y + 24), 2)
    else:
        pygame.draw.rect(s, (120, 120, 118), (x, y, TILE, TILE))


def draw_tile(s, t, x, y, tx, ty, under):
    """under - тип пола под мебелью/дверью."""
    if t in FLOORS:
        draw_floor(s, t, x, y, tx, ty)
        return
    if t == VOID:
        return
    if t == TREE:
        draw_floor(s, GRASS, x, y, tx, ty)
        h = _h(tx, ty)
        r = 15 + h % 4
        pygame.draw.circle(s, (25, 60, 28), (x + 16, y + 17), r)
        pygame.draw.circle(s, (38, 88, 40), (x + 15, y + 15), r - 3)
        pygame.draw.circle(s, (55, 110, 50), (x + 12, y + 12), r - 9)
        return
    if t == WALL:
        pygame.draw.rect(s, (72, 64, 60), (x, y, TILE, TILE))
        pygame.draw.rect(s, (95, 86, 80), (x + 2, y + 2, TILE - 4, TILE - 4), 2)
        return
    if t == WINDOW:
        pygame.draw.rect(s, (72, 64, 60), (x, y, TILE, TILE))
        pygame.draw.rect(s, (150, 200, 230), (x + 5, y + 5, TILE - 10, TILE - 10))
        pygame.draw.rect(s, (200, 230, 250), (x + 7, y + 7, 6, 6))
        return
    if t == FENCE:
        draw_floor(s, under if under is not None else DIRT, x, y, tx, ty)
        pygame.draw.line(s, (150, 150, 155), (x, y + 16), (x + TILE, y + 16), 2)
        pygame.draw.line(s, (150, 150, 155), (x + 16, y), (x + 16, y + TILE), 2)
        pygame.draw.rect(s, (90, 90, 95), (x + 13, y + 13, 6, 6))
        return
    draw_floor(s, under if under is not None else CONCRETE, x, y, tx, ty)
    if t == DOOR:
        for cx, cy in ((x, y), (x + TILE - 6, y), (x, y + TILE - 6), (x + TILE - 6, y + TILE - 6)):
            pygame.draw.rect(s, (90, 60, 35), (cx, cy, 6, 6))
    elif t in (UP, DOWN):
        for k in range(6):
            c = (150 - k * 12, 150 - k * 12, 150 - k * 12) if t == UP else (90 - k * 8, 90 - k * 8, 95 - k * 8)
            pygame.draw.rect(s, c, (x + 2, y + 2 + k * 5, TILE - 4, 5))
        if t == UP:
            pygame.draw.polygon(s, (240, 220, 80), [(x + 16, y + 6), (x + 9, y + 16), (x + 23, y + 16)])
        else:
            pygame.draw.polygon(s, (120, 200, 240), [(x + 16, y + 26), (x + 9, y + 16), (x + 23, y + 16)])
    elif t == FRIDGE:
        pygame.draw.rect(s, (225, 228, 232), (x + 3, y + 3, 26, 26), border_radius=3)
        pygame.draw.line(s, (160, 160, 170), (x + 4, y + 12), (x + 28, y + 12))
        pygame.draw.rect(s, (130, 130, 140), (x + 22, y + 15, 3, 8))
    elif t == CABINET:
        pygame.draw.rect(s, (130, 85, 45), (x + 2, y + 3, 28, 26))
        pygame.draw.line(s, (90, 60, 30), (x + 2, y + 16), (x + 30, y + 16))
        pygame.draw.rect(s, (200, 170, 100), (x + 14, y + 8, 4, 2))
        pygame.draw.rect(s, (200, 170, 100), (x + 14, y + 21, 4, 2))
    elif t == WARDROBE:
        pygame.draw.rect(s, (100, 65, 35), (x + 2, y + 2, 28, 28))
        pygame.draw.line(s, (60, 40, 20), (x + 16, y + 2), (x + 16, y + 30), 2)
        pygame.draw.rect(s, (200, 170, 100), (x + 12, y + 14, 2, 4))
        pygame.draw.rect(s, (200, 170, 100), (x + 18, y + 14, 2, 4))
    elif t == DESK:
        pygame.draw.rect(s, (150, 110, 70), (x + 2, y + 5, 28, 22))
        pygame.draw.rect(s, (230, 230, 230), (x + 6, y + 9, 9, 7))
        pygame.draw.rect(s, (40, 40, 40), (x + 18, y + 10, 8, 6))
    elif t == SHELF:
        pygame.draw.rect(s, (110, 110, 115), (x + 1, y + 4, 30, 24))
        cols = [(200, 60, 50), (60, 140, 200), (230, 190, 60), (90, 170, 90)]
        h = _h(tx, ty)
        for k in range(6):
            pygame.draw.rect(s, cols[(h >> k) % 4], (x + 3 + (k % 3) * 9, y + 7 + (k // 3) * 10, 7, 7))
    elif t == MEDCAB:
        pygame.draw.rect(s, (235, 235, 235), (x + 3, y + 3, 26, 26), border_radius=2)
        pygame.draw.rect(s, (210, 40, 40), (x + 13, y + 7, 6, 18))
        pygame.draw.rect(s, (210, 40, 40), (x + 7, y + 13, 18, 6))
    elif t == LOCKER:
        pygame.draw.rect(s, (70, 85, 100), (x + 2, y + 2, 28, 28))
        for k in range(3):
            pygame.draw.line(s, (40, 50, 60), (x + 6, y + 7 + k * 4), (x + 26, y + 7 + k * 4))
        pygame.draw.line(s, (40, 50, 60), (x + 16, y + 2), (x + 16, y + 30))
    elif t == CRATE:
        pygame.draw.rect(s, (160, 120, 70), (x + 2, y + 2, 28, 28))
        pygame.draw.rect(s, (110, 80, 45), (x + 2, y + 2, 28, 28), 2)
        pygame.draw.line(s, (110, 80, 45), (x + 3, y + 3), (x + 28, y + 28), 2)
        pygame.draw.line(s, (110, 80, 45), (x + 28, y + 3), (x + 3, y + 28), 2)
    elif t == MILCRATE:
        pygame.draw.rect(s, (90, 100, 60), (x + 2, y + 4, 28, 24))
        pygame.draw.rect(s, (60, 68, 40), (x + 2, y + 4, 28, 24), 2)
        pygame.draw.rect(s, (200, 200, 150), (x + 8, y + 13, 16, 5))
    elif t == TOOLBOX:
        pygame.draw.rect(s, (180, 50, 40), (x + 3, y + 9, 26, 18))
        pygame.draw.rect(s, (60, 60, 60), (x + 11, y + 5, 10, 5), 2)
    elif t == BED:
        pygame.draw.rect(s, (120, 80, 50), (x + 1, y + 1, 30, 30))
        pygame.draw.rect(s, (200, 205, 220), (x + 3, y + 3, 26, 26))
        pygame.draw.rect(s, (240, 240, 240), (x + 6, y + 5, 20, 7))
    elif t == TABLE:
        pygame.draw.circle(s, (150, 110, 70), (x + 16, y + 16), 13)
        pygame.draw.circle(s, (120, 85, 50), (x + 16, y + 16), 13, 2)
    elif t == SOFA:
        pygame.draw.rect(s, (120, 50, 50), (x + 1, y + 4, 30, 24), border_radius=4)
        pygame.draw.rect(s, (150, 70, 70), (x + 5, y + 8, 10, 16))
        pygame.draw.rect(s, (150, 70, 70), (x + 17, y + 8, 10, 16))
    elif t == WORKBENCH:
        pygame.draw.rect(s, (130, 95, 60), (x + 1, y + 4, 30, 24))
        pygame.draw.rect(s, (90, 90, 95), (x + 4, y + 8, 8, 8))
        pygame.draw.line(s, (200, 60, 40), (x + 16, y + 10), (x + 27, y + 22), 3)
        pygame.draw.line(s, (180, 180, 190), (x + 16, y + 22), (x + 26, y + 10), 2)
    elif t == COUNTER:
        pygame.draw.rect(s, (160, 150, 140), (x + 1, y + 6, 30, 20))
    elif t == PUMP:
        pygame.draw.rect(s, (200, 50, 40), (x + 8, y + 4, 16, 24), border_radius=3)
        pygame.draw.rect(s, (240, 240, 240), (x + 11, y + 8, 10, 6))
        pygame.draw.line(s, (30, 30, 30), (x + 24, y + 14), (x + 29, y + 24), 2)
    elif t == ROCK:
        pygame.draw.polygon(s, (95, 95, 100), [(x + 4, y + 24), (x + 8, y + 8), (x + 20, y + 4), (x + 29, y + 14),
                                               (x + 27, y + 28), (x + 10, y + 29)])
        pygame.draw.polygon(s, (140, 140, 148), [(x + 9, y + 10), (x + 20, y + 7), (x + 25, y + 14),
                                                 (x + 14, y + 17)])
    elif t in (BUSH, BUSH_EMPTY):
        pygame.draw.circle(s, (40, 95, 40), (x + 16, y + 17), 14)
        pygame.draw.circle(s, (60, 125, 55), (x + 14, y + 14), 10)
        if t == BUSH:
            for k in range(6):
                pygame.draw.circle(s, (200, 30, 80), (x + 8 + (k * 7) % 18, y + 9 + (k * 11) % 16), 3)
    elif t in (WOODWALL, WOODDOOR):
        pygame.draw.rect(s, (115, 78, 45), (x, y, TILE, TILE))
        for k in range(4):
            pygame.draw.line(s, (85, 55, 30), (x, y + k * 8), (x + TILE, y + k * 8), 2)
        if t == WOODDOOR:
            pygame.draw.rect(s, (160, 110, 60), (x + 4, y + 4, TILE - 8, TILE - 8))
            pygame.draw.circle(s, (230, 200, 90), (x + 22, y + 16), 3)
    elif t == STONEWALL:
        pygame.draw.rect(s, (95, 95, 100), (x, y, TILE, TILE))
        for j in range(4):
            off = 0 if j % 2 else 8
            for i in range(-1, 3):
                pygame.draw.rect(s, (130, 130, 136), (x + off + i * 16 + 1, y + j * 8 + 1, 14, 6))
    elif t == CHEST:
        pygame.draw.rect(s, (140, 90, 45), (x + 3, y + 7, 26, 20), border_radius=3)
        pygame.draw.rect(s, (90, 60, 30), (x + 3, y + 7, 26, 20), 2, border_radius=3)
        pygame.draw.line(s, (90, 60, 30), (x + 3, y + 14), (x + 29, y + 14), 2)
        pygame.draw.rect(s, (230, 200, 90), (x + 14, y + 12, 4, 5))
    elif t == CAMPFIRE:
        for k in range(8):
            a = k * math.pi / 4
            pygame.draw.circle(s, (110, 110, 115), (int(x + 16 + math.cos(a) * 11), int(y + 16 + math.sin(a) * 11)), 4)
        pygame.draw.line(s, (90, 60, 30), (x + 9, y + 12), (x + 23, y + 20), 4)
        pygame.draw.line(s, (90, 60, 30), (x + 9, y + 20), (x + 23, y + 12), 4)
        pygame.draw.circle(s, (240, 120, 30), (x + 16, y + 16), 7)
        pygame.draw.circle(s, (255, 220, 90), (x + 16, y + 17), 4)


class Renderer:
    def __init__(self, world):
        self.world = world
        self.chunks = OrderedDict()
        self.upper = {}
        self.roofs = {}
        self.minis = {}
        self.light = self._gradient(230)
        self.light_big = self._gradient(380)
        self.light_car = self._gradient(320)
        self.light_fire = self._gradient(170)
        self.car_cache = {}

    def _under(self, t, tx, ty):
        b = self.world.building_at_tile(tx, ty)
        if b:
            return FLOOR_OF[b.kind]
        o = self.world.orig_tile(0, tx, ty)
        if o in FLOORS:
            return o
        if t in NATURE:
            return GRASS
        return CONCRETE if t == PUMP else DIRT

    def invalidate(self, lv, tx, ty):
        if lv == 0:
            self.chunks.pop((tx >> 4, ty >> 4), None)
            self.minis.pop((tx >> 5, ty >> 5), None)
        else:
            b = self.world.building_at_tile(tx, ty)
            if b:
                self.upper.pop((b.id, lv), None)

    def _chunk(self, cx, cy):
        key = (cx, cy)
        s = self.chunks.get(key)
        if s is not None:
            self.chunks.move_to_end(key)
            return s
        s = pygame.Surface((CH * TILE, CH * TILE)).convert()
        w = self.world
        for j in range(CH):
            ty = cy * CH + j
            for i in range(CH):
                tx = cx * CH + i
                t = w.tile(0, tx, ty)
                draw_tile(s, t, i * TILE, j * TILE, tx, ty, None if t in FLOORS else self._under(t, tx, ty))
        self.chunks[key] = s
        if len(self.chunks) > 90:
            self.chunks.popitem(last=False)
        return s

    def draw_ground(self, screen, camx, camy):
        sw, sh = screen.get_size()
        size = CH * TILE
        for cy in range(int(camy // size), int((camy + sh) // size) + 1):
            for cx in range(int(camx // size), int((camx + sw) // size) + 1):
                screen.blit(self._chunk(cx, cy), (cx * size - camx, cy * size - camy))

    def mini(self, cx, cy):
        """Миникарта одного чанка 32x32 пикселя (или None, если чанк ещё не исследован)."""
        s = self.minis.get((cx, cy))
        if s is None:
            c = self.world.chunks.get((cx, cy))
            if c is None:
                return None
            s = pygame.Surface((CS, CS)).convert()
            L = c.levels[0]
            for i in range(CS * CS):
                bi = c.bmap[i]
                s.set_at((i & 31, i >> 5), c.buildings[bi].roof if bi >= 0 else MINI.get(L[i], (62, 110, 52)))
            self.minis[(cx, cy)] = s
        return s

    def upper_surface(self, b, lv):
        key = (b.id, lv)
        s = self.upper.get(key)
        if s is None:
            if len(self.upper) > 120:
                self.upper.clear()
            s = pygame.Surface((b.w * TILE, b.h * TILE)).convert()
            under = FLOOR_OF[b.kind]
            for ty in range(b.y, b.y + b.h):
                for tx in range(b.x, b.x + b.w):
                    draw_tile(s, self.world.tile(lv, tx, ty), (tx - b.x) * TILE, (ty - b.y) * TILE, tx, ty, under)
            self.upper[key] = s
        return s

    def roof(self, b):
        s = self.roofs.get(b.id)
        if s is None:
            if len(self.roofs) > 400:
                self.roofs.clear()
            W, H = b.w * TILE, b.h * TILE
            s = pygame.Surface((W, H)).convert()
            base = b.roof
            if b.kind in GABLE:
                if W >= H:
                    pygame.draw.rect(s, base, (0, 0, W, H // 2))
                    pygame.draw.rect(s, _shade(base, 0.78), (0, H // 2, W, H - H // 2))
                    for k in range(0, H, 8):
                        pygame.draw.line(s, _shade(base, 0.7), (0, k), (W, k))
                    pygame.draw.line(s, _shade(base, 1.2), (0, H // 2), (W, H // 2), 3)
                else:
                    pygame.draw.rect(s, base, (0, 0, W // 2, H))
                    pygame.draw.rect(s, _shade(base, 0.78), (W // 2, 0, W - W // 2, H))
                    for k in range(0, W, 8):
                        pygame.draw.line(s, _shade(base, 0.7), (k, 0), (k, H))
                    pygame.draw.line(s, _shade(base, 1.2), (W // 2, 0), (W // 2, H), 3)
                pygame.draw.rect(s, (225, 225, 225), (W - 34, 10, 14, 18))
            else:
                s.fill(_shade(base, 0.9))
                pygame.draw.rect(s, _shade(base, 1.15), (0, 0, W, H), 6)
                h = (b.x * 7919 + b.y * 104729) & 0xFFFFFF
                for k in range(3 + b.w // 6):
                    vx, vy = 16 + (h >> k) % max(1, W - 48), 16 + (h >> (k + 5)) % max(1, H - 48)
                    pygame.draw.rect(s, _shade(base, 0.65), (vx, vy, 18, 14))
                    pygame.draw.rect(s, _shade(base, 1.3), (vx + 3, vy + 3, 12, 8), 1)
                if b.kind == "hospital":
                    pygame.draw.circle(s, (230, 230, 230), (W // 2, H // 2), 34)
                    pygame.draw.rect(s, (210, 40, 40), (W // 2 - 8, H // 2 - 24, 16, 48))
                    pygame.draw.rect(s, (210, 40, 40), (W // 2 - 24, H // 2 - 8, 48, 16))
            label = KIND_LABEL.get(b.kind)
            if label and b.kind != "hospital":
                ui.text(s, label, (W // 2, H // 2), 22, (240, 240, 240), bold=True, center=True)
            elif label:
                ui.text(s, label, (W // 2, H // 2 + 48), 20, (200, 40, 40), bold=True, center=True)
            if b.floors > 1:
                ui.text(s, "%d эт." % b.floors, (10, H - 26), 16, (240, 240, 240))
            pygame.draw.rect(s, (30, 30, 30), (0, 0, W, H), 2)
            # навесы над входами со стрелкой наружу - видно, где вход
            for (dx, dy) in b.doors:
                x, y = (dx - b.x) * TILE, (dy - b.y) * TILE
                if dy == b.y:
                    out = (0, -1)
                elif dy == b.y + b.h - 1:
                    out = (0, 1)
                elif dx == b.x:
                    out = (-1, 0)
                else:
                    out = (1, 0)
                pygame.draw.rect(s, (235, 205, 90), (x, y, TILE, TILE))
                pygame.draw.rect(s, (120, 70, 30), (x, y, TILE, TILE), 3)
                cx, cy = x + 16, y + 16
                ox, oy = out
                pts = [(cx + ox * 11, cy + oy * 11), (cx - ox * 4 - oy * 9, cy - oy * 4 - ox * 9),
                       (cx - ox * 4 + oy * 9, cy - oy * 4 + ox * 9)]
                pygame.draw.polygon(s, (60, 35, 20), pts)
            self.roofs[b.id] = s
        return s

    def area_map(self, tx0, ty0, w, h):
        """Карта области 1 пиксель = 1 тайл; неисследованное - тёмное."""
        s = pygame.Surface((w, h)).convert()
        s.fill((18, 20, 24))
        for cy in range(ty0 >> 5, ((ty0 + h) >> 5) + 1):
            for cx in range(tx0 >> 5, ((tx0 + w) >> 5) + 1):
                m = self.mini(cx, cy)
                if m:
                    s.blit(m, (cx * CS - tx0, cy * CS - ty0))
        return s

    @staticmethod
    def _gradient(r):
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        for k in range(r, 0, -4):
            a = int(255 * (1 - (k / r) ** 1.6))
            pygame.draw.circle(s, (a, a, a, a), (r, r), k)
        return s

    # ---------- сущности ----------
    def car_sprite(self, color, up, wreck, ang):
        key = (tuple(color), up.get("armor", 0) > 0, up.get("ram", 0) > 0, up.get("lights", 0) > 0, wreck,
               int(round(math.degrees(ang) / 4)) % 90)
        spr = self.car_cache.get(key)
        if spr is None:
            base = pygame.Surface((72, 40), pygame.SRCALPHA)
            col = (60, 55, 50) if wreck else tuple(color)
            for wx in (14, 48):
                for wy in (2, 32):
                    pygame.draw.rect(base, (20, 20, 20), (wx, wy, 12, 6), border_radius=2)
            pygame.draw.rect(base, col, (4, 5, 64, 30), border_radius=8)
            pygame.draw.rect(base, _shade(col, 0.6), (4, 5, 64, 30), 2, border_radius=8)
            pygame.draw.rect(base, (40, 50, 65) if not wreck else (30, 30, 30), (42, 9, 10, 22), border_radius=3)
            pygame.draw.rect(base, (40, 50, 65) if not wreck else (30, 30, 30), (14, 10, 7, 20), border_radius=3)
            pygame.draw.rect(base, _shade(col, 1.15), (22, 9, 19, 22), border_radius=3)
            if not wreck:
                lc = (255, 255, 200) if key[3] else (240, 230, 160)
                pygame.draw.rect(base, lc, (64, 8, 4, 6))
                pygame.draw.rect(base, lc, (64, 26, 4, 6))
                pygame.draw.rect(base, (200, 30, 30), (4, 8, 3, 6))
                pygame.draw.rect(base, (200, 30, 30), (4, 26, 3, 6))
            if key[1]:
                pygame.draw.rect(base, (120, 120, 125), (8, 5, 56, 30), 3, border_radius=6)
            if key[2]:
                pygame.draw.rect(base, (150, 150, 155), (66, 3, 5, 34))
            if wreck:
                for k in range(6):
                    pygame.draw.circle(base, (25, 25, 25), (10 + k * 10, 12 + (k * 7) % 16), 5)
            spr = pygame.transform.rotate(base, -key[5] * 4)
            if len(self.car_cache) > 600:
                self.car_cache.clear()
            self.car_cache[key] = spr
        return spr

    def draw_car(self, screen, x, y, ang, color, up, wreck):
        spr = self.car_sprite(color, up, wreck, ang)
        screen.blit(spr, (x - spr.get_width() // 2, y - spr.get_height() // 2))


def draw_player(screen, x, y, a, color, weapon, vest, helmet):
    ca, sa = math.cos(a), math.sin(a)
    wd = IT.ITEMS.get(weapon)
    if wd and wd["kind"] == "gun":
        ln = 26 if weapon in ("rifle", "sniper", "shotgun") else 20
        if weapon == "sniper":
            ln = 32
        pygame.draw.line(screen, (30, 30, 30), (x + ca * 6, y + sa * 6), (x + ca * ln, y + sa * ln), 5)
        pygame.draw.line(screen, wd["color"], (x + ca * 6, y + sa * 6), (x + ca * ln, y + sa * ln), 3)
    elif wd:
        ln = 16 + wd["range"] * 0.25
        px, py = x + ca * 10 - sa * 9, y + sa * 10 + ca * 9
        pygame.draw.line(screen, wd["color"], (px, py), (px + ca * ln * 0.6, py + sa * ln * 0.6), 4)
    for side in (-1, 1):
        hx, hy = x + ca * 9 - sa * 8 * side, y + sa * 9 + ca * 8 * side
        pygame.draw.circle(screen, (220, 180, 140), (int(hx), int(hy)), 4)
    pygame.draw.circle(screen, (20, 20, 20), (int(x), int(y)), 13)
    pygame.draw.circle(screen, color, (int(x), int(y)), 12)
    if vest:
        pygame.draw.circle(screen, IT.ITEMS[vest]["color"], (int(x), int(y)), 12, 4)
    hc = IT.ITEMS[helmet]["color"] if helmet else (90, 60, 40)
    pygame.draw.circle(screen, hc, (int(x - ca * 2), int(y - sa * 2)), 7)


ZCOL = {"walker": (95, 130, 85), "runner": (140, 110, 80), "brute": (75, 95, 70)}


def draw_zombie(screen, x, y, a, kind, frac):
    r = 18 if kind == "brute" else (11 if kind == "runner" else 12)
    ca, sa = math.cos(a), math.sin(a)
    col = ZCOL.get(kind, (95, 130, 85))
    arm = r + 10
    for side in (-1, 1):
        bx, by = x - sa * (r - 4) * side, y + ca * (r - 4) * side
        pygame.draw.line(screen, _shade(col, 0.8), (bx, by), (bx + ca * arm, by + sa * arm), 5 if kind == "brute" else 4)
    pygame.draw.circle(screen, (20, 25, 20), (int(x), int(y)), r + 1)
    pygame.draw.circle(screen, col, (int(x), int(y)), r)
    pygame.draw.circle(screen, (110, 40, 40), (int(x + ca * r * 0.3), int(y + sa * r * 0.3)), max(3, r // 3))
    pygame.draw.circle(screen, (230, 60, 40), (int(x + ca * r * 0.6 - sa * 3), int(y + sa * r * 0.6 + ca * 3)), 2)
    pygame.draw.circle(screen, (230, 60, 40), (int(x + ca * r * 0.6 + sa * 3), int(y + sa * r * 0.6 - ca * 3)), 2)
    if frac < 0.99:
        pygame.draw.rect(screen, (40, 0, 0), (x - 14, y - r - 9, 28, 4))
        pygame.draw.rect(screen, (220, 40, 40), (x - 14, y - r - 9, int(28 * frac), 4))


def draw_bag(screen, x, y, kind):
    if kind == "body":
        pygame.draw.ellipse(screen, (90, 20, 20), (x - 16, y - 10, 32, 20))
        pygame.draw.rect(screen, (110, 80, 50), (x - 8, y - 8, 16, 16), border_radius=3)
    else:
        pygame.draw.rect(screen, (110, 80, 50), (x - 9, y - 10, 18, 20), border_radius=4)
        pygame.draw.rect(screen, (80, 55, 35), (x - 9, y - 10, 18, 20), 2, border_radius=4)
        pygame.draw.rect(screen, (80, 55, 35), (x - 5, y - 2, 10, 7))


def draw_icon(s, rect, iid):
    r = pygame.Rect(rect)
    d = IT.ITEMS.get(iid)
    if not d:
        return
    c = d.get("color", (180, 180, 180))
    cx, cy = r.center
    k = d["kind"]
    if k == "food" and iid != "berries":
        if iid in ("apple",):
            pygame.draw.circle(s, c, (cx, cy + 2), r.w // 4)
            pygame.draw.line(s, (60, 120, 40), (cx, cy - r.h // 4), (cx + 4, cy - r.h // 3), 3)
        else:
            pygame.draw.rect(s, c, (cx - r.w // 4, cy - r.h // 4, r.w // 2, r.h // 2), border_radius=4)
            pygame.draw.rect(s, (255, 255, 255), (cx - r.w // 4, cy - 3, r.w // 2, 6))
    elif k == "drink":
        pygame.draw.rect(s, c, (cx - 7, cy - 10, 14, 24), border_radius=4)
        pygame.draw.rect(s, (230, 230, 230), (cx - 3, cy - 16, 6, 7))
    elif k == "med":
        pygame.draw.rect(s, c, (cx - 12, cy - 10, 24, 20), border_radius=3)
        pygame.draw.rect(s, (220, 40, 40) if iid != "medkit" else (255, 255, 255), (cx - 3, cy - 7, 6, 14))
        pygame.draw.rect(s, (220, 40, 40) if iid != "medkit" else (255, 255, 255), (cx - 7, cy - 3, 14, 6))
    elif k == "gun":
        ln = 30 if iid in ("rifle", "sniper", "shotgun") else 20
        pygame.draw.rect(s, c, (cx - ln // 2, cy - 5, ln, 7))
        pygame.draw.rect(s, c, (cx - ln // 2 + 2, cy, 6, 11))
        if iid in ("smg", "rifle"):
            pygame.draw.rect(s, c, (cx, cy + 1, 4, 9))
    elif k == "melee":
        pygame.draw.line(s, (120, 90, 60), (cx - 12, cy + 12), (cx, cy), 4)
        pygame.draw.line(s, c, (cx, cy), (cx + 12, cy - 12), 6 if iid in ("bat", "axe") else 4)
    elif k == "ammo":
        for i in range(3):
            pygame.draw.rect(s, c, (cx - 10 + i * 8, cy - 8, 5, 16), border_radius=2)
    elif k in ("vest", "helmet"):
        if k == "vest":
            pygame.draw.rect(s, c, (cx - 12, cy - 12, 24, 26), border_radius=5)
            pygame.draw.rect(s, (25, 25, 25), (cx - 4, cy - 12, 8, 6))
        else:
            pygame.draw.circle(s, c, (cx, cy + 4), 13, draw_top_left=True, draw_top_right=True)
    elif k == "bag":
        pygame.draw.rect(s, c, (cx - 11, cy - 12, 22, 26), border_radius=6)
        pygame.draw.rect(s, _shade(c, 0.7), (cx - 7, cy, 14, 9))
    elif iid == "wood":
        for i in range(3):
            pygame.draw.rect(s, c, (cx - 13, cy - 10 + i * 7, 26, 6), border_radius=3)
            pygame.draw.circle(s, (200, 160, 110), (cx + 11, cy - 7 + i * 7), 3)
    elif iid == "stone":
        pygame.draw.circle(s, c, (cx - 4, cy + 3), 9)
        pygame.draw.circle(s, _shade(c, 1.2), (cx + 6, cy - 2), 7)
    elif iid == "berries":
        for i in range(5):
            pygame.draw.circle(s, c, (cx - 8 + (i * 7) % 18, cy - 5 + (i * 5) % 12), 5)
    elif k == "mod":
        pygame.draw.rect(s, c, (cx - 13, cy - 5, 26, 10), border_radius=4)
        pygame.draw.circle(s, (120, 120, 120), (cx, cy), 3)
    else:
        pygame.draw.rect(s, c, (cx - 11, cy - 11, 22, 22), border_radius=5)
        pygame.draw.circle(s, _shade(c, 0.6), (cx, cy), 5)
