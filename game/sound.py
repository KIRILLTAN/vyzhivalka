"""Процедурные звуки (без файлов)."""
import array
import math
import random

import pygame

RATE = 22050
SOUNDS = {}
_ok = False


def _make(samples):
    arr = array.array("h", (int(max(-1.0, min(1.0, s)) * 30000) for s in samples))
    return pygame.mixer.Sound(buffer=arr.tobytes())


def _noise(dur, decay, lp, vol=1.0, rnd=None):
    rnd = rnd or random.Random(1)
    n = int(RATE * dur)
    y = 0.0
    out = []
    for i in range(n):
        y += lp * (rnd.uniform(-1, 1) - y)
        out.append(y * vol * math.exp(-decay * i / RATE))
    return out


def _tone(dur, f0, f1, decay, vol=0.6, wave="sin"):
    n = int(RATE * dur)
    out = []
    ph = 0.0
    for i in range(n):
        t = i / n
        f = f0 + (f1 - f0) * t
        ph += 2 * math.pi * f / RATE
        s = math.sin(ph) if wave == "sin" else (1.0 if math.sin(ph) > 0 else -1.0)
        out.append(s * vol * math.exp(-decay * i / RATE))
    return out


def _mix(*parts):
    n = max(len(p) for p in parts)
    return [sum(p[i] for p in parts if i < len(p)) for i in range(n)]


def init():
    global _ok
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(RATE, -16, 1, 512)
        pygame.mixer.set_num_channels(24)
        SOUNDS["pistol"] = _make(_mix(_noise(0.22, 22, 0.6, 1.0), _tone(0.08, 180, 60, 40, 0.5)))
        SOUNDS["smg"] = _make(_noise(0.12, 35, 0.6, 0.8))
        SOUNDS["rifle"] = _make(_mix(_noise(0.25, 18, 0.55, 1.0), _tone(0.1, 140, 50, 30, 0.5)))
        SOUNDS["shotgun"] = _make(_mix(_noise(0.4, 10, 0.4, 1.0), _tone(0.15, 110, 40, 20, 0.6)))
        SOUNDS["sniper"] = _make(_mix(_noise(0.5, 8, 0.5, 1.0), _tone(0.2, 120, 30, 12, 0.6)))
        SOUNDS["silenced"] = _make(_noise(0.08, 50, 0.25, 0.5))
        SOUNDS["swing"] = _make(_noise(0.15, 25, 0.08, 0.5))
        SOUNDS["hit"] = _make(_mix(_tone(0.1, 120, 60, 40, 0.7), _noise(0.08, 50, 0.2, 0.4)))
        SOUNDS["groan"] = _make([0.35 * math.sin(2 * math.pi * (85 + 15 * math.sin(i / 900)) * i / RATE) *
                                 math.sin(math.pi * i / (RATE * 0.9)) for i in range(int(RATE * 0.9))])
        SOUNDS["pick"] = _make(_tone(0.07, 700, 1100, 30, 0.35))
        SOUNDS["open"] = _make(_mix(_tone(0.1, 300, 200, 30, 0.3), _noise(0.1, 30, 0.1, 0.3)))
        SOUNDS["equip"] = _make(_tone(0.08, 400, 600, 40, 0.3, "sq"))
        SOUNDS["click"] = _make(_tone(0.03, 1500, 1500, 80, 0.3, "sq"))
        SOUNDS["reload"] = _make(_mix(_tone(0.05, 900, 900, 60, 0.3, "sq"),
                                      [0] * 6000 + _tone(0.05, 700, 700, 60, 0.3, "sq")))
        SOUNDS["eat"] = _make(_noise(0.25, 10, 0.05, 0.5))
        SOUNDS["med"] = _make(_noise(0.3, 8, 0.3, 0.3))
        SOUNDS["hurt"] = _make(_tone(0.15, 300, 150, 20, 0.5, "sq"))
        SOUNDS["zd"] = _make(_mix(_tone(0.3, 100, 40, 10, 0.5), _noise(0.2, 20, 0.15, 0.4)))
        SOUNDS["boom"] = _make(_mix(_noise(1.2, 3, 0.15, 1.0), _tone(0.6, 70, 25, 5, 0.8)))
        SOUNDS["crash"] = _make(_noise(0.4, 9, 0.3, 0.9))
        SOUNDS["door"] = _make(_tone(0.1, 200, 120, 30, 0.4, "sq"))
        SOUNDS["upgrade"] = _make(_mix(_tone(0.12, 500, 900, 20, 0.3), _noise(0.12, 25, 0.5, 0.2)))
        SOUNDS["build"] = _make(_mix(_tone(0.08, 160, 120, 30, 0.5, "sq"), [0] * 2500 + _tone(0.08, 180, 130, 30, 0.5, "sq")))
        SOUNDS["chop"] = _make(_mix(_tone(0.06, 260, 180, 50, 0.5), _noise(0.07, 45, 0.4, 0.4)))
        _ok = True
    except Exception:
        _ok = False


def play(name, vol=1.0):
    if not _ok or vol <= 0.02:
        return
    s = SOUNDS.get(name)
    if s:
        ch = pygame.mixer.find_channel()
        if ch:
            ch.set_volume(min(1.0, vol))
            ch.play(s)


SHOT_SOUND = {"pistol": "pistol", "smg": "smg", "rifle": "rifle", "shotgun": "shotgun", "sniper": "sniper"}
