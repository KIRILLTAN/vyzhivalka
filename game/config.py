import json
import os
import sys

VERSION = "1.4.0"
# Репозиторий для проверки обновлений: "ИМЯ_ПОЛЬЗОВАТЕЛЯ/ИМЯ_РЕПОЗИТОРИЯ".
# Поменяйте на свой перед сборкой (или впишите "github_repo" в settings.json).
GITHUB_REPO = "KIRILLTAN/vyzhivalka"
EXE_NAME = "Vyzhivalka.exe"              # игра + лаунчер (ставится установщиком)
SETUP_NAME = "VyzhivalkaSetup.exe"       # единственный файл, который загружается в релиз на GitHub
ONLINE_NAME = "VyzhivalkaOnline.exe"     # онлайн-установщик: качает последний Setup и запускает его
TITLE = "Выживалка"

SCREEN_W, SCREEN_H = 1280, 720
TILE = 32
MAP_W = MAP_H = 192
PORT = 47777
SIM_HZ = 30
SNAP_HZ = 20
VIEW_DIST = 1100

DIFF_ORDER = ["easy", "normal", "hard", "hardcore"]
DIFFICULTIES = {
    "easy": {"name": "Лёгкая", "desc": "Мало зомби, много лута, стартовый пистолет",
             "zmult": 0.6, "zdmg": 0.6, "zhp": 0.8, "zspeed": 0.9, "hunger": 0.6, "loot": 1.4},
    "normal": {"name": "Нормальная", "desc": "Сбалансированная выживалка, стартовый нож",
               "zmult": 1.0, "zdmg": 1.0, "zhp": 1.0, "zspeed": 1.0, "hunger": 1.0, "loot": 1.0},
    "hard": {"name": "Сложная", "desc": "Больше быстрых зомби, лута меньше",
             "zmult": 1.5, "zdmg": 1.4, "zhp": 1.2, "zspeed": 1.1, "hunger": 1.3, "loot": 0.8},
    "hardcore": {"name": "Хардкор", "desc": "Орды зомби, голод и почти пустые дома",
                 "zmult": 2.2, "zdmg": 2.0, "zhp": 1.4, "zspeed": 1.2, "hunger": 1.6, "loot": 0.6},
}

# key, название, значения, подписи (первое значение - по умолчанию)
MP_OPTIONS = [
    ("friendly_fire", "Атака друзей", [False, True], ["Выкл", "Вкл"]),
    ("respawn", "Возрождение после смерти", [True, False], ["Да", "Нет"]),
    ("keep_inv", "Сохранять вещи при смерти", [False, True], ["Нет", "Да"]),
    ("max_players", "Макс. игроков", [4, 6, 8, 2, 3], ["4", "6", "8", "2", "3"]),
    ("loot", "Количество лута", [1.0, 1.6, 0.6], ["Норма", "Много", "Мало"]),
    ("zombies", "Количество зомби", [1.0, 1.5, 2.0, 0.5], ["x1", "x1.5", "x2", "x0.5"]),
    ("day_len", "Длина суток", [12, 20, 8], ["12 мин", "20 мин", "8 мин"]),
    ("map_marks", "Друзья на карте", [True, False], ["Да", "Нет"]),
]


def default_settings(multiplayer=True):
    s = {k: vals[0] for k, _, vals, _ in MP_OPTIONS}
    if not multiplayer:
        s.update(friendly_fire=False, respawn=False, keep_inv=False, max_players=1)
    return s


def resource_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_dir():
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "Vyzhivalka")
    os.makedirs(d, exist_ok=True)
    return d


def _prefs_path():
    return os.path.join(data_dir(), "settings.json")


def load_prefs():
    try:
        with open(_prefs_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_prefs(p):
    try:
        with open(_prefs_path(), "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def github_repo():
    return load_prefs().get("github_repo") or GITHUB_REPO
