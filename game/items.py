"""Предметы, оружие, броня и таблицы лута."""

ITEMS = {}


def _add(iid, name, kind, desc="", stack=1, **kw):
    d = {"id": iid, "name": name, "kind": kind, "desc": desc, "stack": stack}
    d.update(kw)
    ITEMS[iid] = d


# --- еда и вода ---
_add("canned", "Консервы", "food", "Сытная тушёнка", 5, food=35, color=(170, 170, 185))
_add("bread", "Хлеб", "food", "Слегка чёрствый", 5, food=22, color=(210, 170, 100))
_add("chips", "Чипсы", "food", "Солёные - хочется пить", 5, food=15, water=-4, color=(240, 200, 60))
_add("choco", "Шоколадка", "food", "Восстанавливает выносливость", 5, food=10, stam=40, color=(120, 70, 40))
_add("apple", "Яблоко", "food", "Немного еды и воды", 5, food=8, water=6, color=(200, 40, 40))
_add("mre", "Сухпаёк", "food", "Армейский паёк", 3, food=60, water=10, color=(110, 120, 70))
_add("water", "Бутылка воды", "drink", "Чистая вода", 5, water=45, color=(90, 160, 240))
_add("soda", "Газировка", "drink", "Сладкая", 5, water=28, food=4, color=(220, 60, 80))
_add("juice", "Сок", "drink", "Апельсиновый", 5, water=32, food=6, color=(250, 150, 40))
# --- медицина ---
_add("bandage", "Бинт", "med", "Останавливает кровотечение", 5, hp=12, stopbleed=True, color=(235, 235, 235))
_add("medkit", "Аптечка", "med", "Лечит и останавливает кровь", 3, hp=60, stopbleed=True, color=(220, 50, 50))
_add("pills", "Обезболивающее", "med", "Немного лечит", 5, hp=20, color=(250, 250, 180))
# --- ближний бой ---
_add("knife", "Нож", "melee", "Быстрый, но слабый", dmg=20, rate=0.32, range=42, color=(190, 190, 200))
_add("pipe", "Труба", "melee", "Ржавая железная труба", dmg=25, rate=0.55, range=52, color=(130, 130, 140))
_add("bat", "Бита", "melee", "Деревянная бита", dmg=29, rate=0.6, range=56, color=(170, 120, 70))
_add("crowbar", "Монтировка", "melee", "Надёжная монтировка", dmg=31, rate=0.6, range=52, color=(200, 40, 40))
_add("machete", "Мачете", "melee", "Острое лезвие", dmg=38, rate=0.5, range=56, color=(160, 170, 180))
_add("axe", "Топор", "melee", "Медленный, но мощный", dmg=50, rate=0.85, range=56, color=(140, 90, 50))
FISTS = {"id": "fists", "name": "Кулаки", "kind": "melee", "dmg": 9, "rate": 0.42, "range": 38}
# --- огнестрел ---
_add("pistol", "Пистолет", "gun", "Патроны 9мм", ammo="a9", mag=12, dmg=30, rate=0.28, spread=0.045,
     range=650, noise=650, reload=1.3, color=(60, 60, 65))
_add("smg", "Пистолет-пулемёт", "gun", "Автоматический, 9мм", ammo="a9", mag=30, dmg=21, rate=0.085,
     spread=0.09, range=550, noise=700, reload=1.9, auto=True, color=(50, 50, 60))
_add("shotgun", "Дробовик", "gun", "Патроны 12 калибра", ammo="a12", mag=6, dmg=16, pellets=8, rate=0.85,
     spread=0.2, range=380, noise=950, reload=2.4, color=(110, 70, 40))
_add("rifle", "Автомат", "gun", "Автоматический, 7.62", ammo="a762", mag=30, dmg=36, rate=0.11,
     spread=0.06, range=820, noise=1000, reload=2.2, auto=True, color=(70, 60, 40))
_add("sniper", "Снайперская винтовка", "gun", "Пробивает насквозь, 7.62", ammo="a762", mag=5, dmg=125,
     rate=1.25, spread=0.008, range=1300, noise=1200, reload=2.8, pierce=3, color=(60, 70, 50))
# --- патроны ---
_add("a9", "Патроны 9мм", "ammo", "Для пистолета и ПП", 60, color=(200, 170, 60))
_add("a12", "Патроны 12 калибра", "ammo", "Для дробовика", 30, color=(200, 50, 40))
_add("a762", "Патроны 7.62", "ammo", "Для автомата и снайперки", 60, color=(180, 140, 50))
# --- броня ---
_add("vest1", "Лёгкий бронежилет", "vest", "Защита 25%", armor=0.25, dur=80, color=(90, 100, 80))
_add("vest2", "Бронежилет", "vest", "Защита 40%", armor=0.40, dur=140, color=(60, 70, 60))
_add("vest3", "Тяжёлый бронежилет", "vest", "Защита 55%, замедляет", armor=0.55, dur=220, slow=0.1,
     color=(40, 45, 40))
_add("helmet1", "Каска", "helmet", "Защита 12%", armor=0.12, dur=60, color=(200, 180, 40))
_add("helmet2", "Военный шлем", "helmet", "Защита 22%", armor=0.22, dur=120, color=(80, 90, 60))
# --- рюкзаки ---
_add("bag1", "Рюкзак", "bag", "+8 слотов", slots=8, color=(120, 80, 50))
_add("bag2", "Туристический рюкзак", "bag", "+14 слотов", slots=14, color=(50, 100, 160))
_add("bag3", "Военный рюкзак", "bag", "+20 слотов", slots=20, color=(80, 90, 50))
# --- детали и ресурсы ---
_add("scrap", "Металлолом", "part", "Для тюнинга машин", 20, color=(150, 150, 150))
_add("engine_part", "Детали двигателя", "part", "Улучшение двигателя", 5, color=(90, 90, 110))
_add("tire", "Шина", "part", "Улучшение подвески и шин", 4, color=(30, 30, 30))
_add("battery", "Аккумулятор", "part", "Для мощных фар", 2, color=(60, 140, 60))
_add("tools", "Инструменты", "part", "Нужны для работы на верстаке", color=(200, 60, 40))
_add("fuel", "Канистра бензина", "carfix", "+35 топлива рядом с машиной", 3, fuel=35, color=(200, 40, 30))
_add("repair_kit", "Ремкомплект", "carfix", "+50 прочности машине рядом", 3, repair=50, color=(240, 180, 40))
# --- модификации оружия ---
_add("silencer", "Глушитель", "mod", "Огнестрел: шум x0.3", for_kind="gun", color=(40, 40, 40))
_add("ext_mag", "Увелич. магазин", "mod", "Огнестрел: магазин x1.5", for_kind="gun", color=(70, 70, 70))
_add("scope", "Прицел", "mod", "Огнестрел: точность и дальность", for_kind="gun", color=(30, 60, 90))
_add("nails", "Шипы", "mod", "Ближний бой: урон +35%", for_kind="melee", color=(170, 170, 170))
# --- прочее ---
_add("flashlight", "Фонарик", "misc", "Ночью видно дальше (просто носите с собой)", color=(240, 230, 120))
_add("money", "Деньги", "money", "Валюта для торговли с выжившими", 9999, color=(110, 180, 90))
# --- ресурсы и самодельные инструменты ---
_add("wood", "Дерево", "res", "Рубите деревья. Для стройки (B)", 50, color=(150, 105, 60))
_add("stone", "Камень", "res", "Разбивайте камни. Для стройки (B)", 50, color=(140, 140, 145))
_add("berries", "Ягоды", "food", "Собирайте с кустов (E)", 20, food=6, water=3, color=(170, 40, 90))
_add("stone_axe", "Каменный топор", "melee", "Рубит деревья быстрее", dmg=22, rate=0.6, range=52, chop=3,
     color=(130, 120, 110))
_add("pickaxe", "Кирка", "melee", "Разбивает камни быстрее", dmg=20, rate=0.7, range=52, mine=3,
     color=(110, 110, 120))
ITEMS["axe"]["chop"] = 3
ITEMS["machete"]["chop"] = 2
ITEMS["crowbar"]["mine"] = 2

# Крафт: предмет -> стоимость
CRAFTS = [
    ("stone_axe", {"wood": 3, "stone": 2}),
    ("pickaxe", {"wood": 3, "stone": 3}),
    ("bandage", {"berries": 3, "wood": 1}),
    ("bat", {"wood": 5}),
    ("nails", {"scrap": 2, "wood": 1}),
]
CRAFT_D = dict(CRAFTS)

# Цены у торговцев (за 1 штуку). Торговец покупает за половину цены.
VALUES = {
    "canned": 12, "bread": 8, "chips": 6, "choco": 6, "apple": 4, "mre": 25, "water": 10, "soda": 7, "juice": 8,
    "bandage": 10, "medkit": 45, "pills": 15, "knife": 20, "pipe": 15, "bat": 25, "crowbar": 30, "machete": 45,
    "axe": 55, "pistol": 120, "smg": 260, "shotgun": 220, "rifle": 400, "sniper": 550, "a9": 2, "a12": 4,
    "a762": 4, "vest1": 120, "vest2": 260, "vest3": 450, "helmet1": 60, "helmet2": 160, "bag1": 60, "bag2": 130,
    "bag3": 220, "scrap": 5, "engine_part": 40, "tire": 30, "battery": 50, "tools": 70, "fuel": 35,
    "repair_kit": 60, "silencer": 150, "ext_mag": 120, "scope": 140, "nails": 40, "flashlight": 30, "money": 1,
    "wood": 2, "stone": 2, "berries": 2, "stone_axe": 18, "pickaxe": 20,
}


def price(iid):
    return VALUES.get(iid, 10)


def sell_price(iid):
    return max(1, price(iid) // 2)


def trade_qty(it):
    """Сколько штук продаётся/покупается за один клик."""
    return min(it["n"], 10 if ITEMS[it["id"]]["kind"] == "ammo" else 1)


STACK_ROLL = {"a9": (8, 24), "a12": (4, 12), "a762": (8, 30), "scrap": (1, 4), "money": (5, 40)}

LOOT = {
    "fridge": (0, 3, [("canned", 2), ("bread", 3), ("apple", 4), ("water", 4), ("soda", 3), ("juice", 3)]),
    "cabinet": (0, 3, [("canned", 4), ("chips", 3), ("bread", 2), ("water", 2), ("choco", 2), ("knife", 1),
                       ("bandage", 1), ("pills", 1)]),
    "wardrobe": (0, 2, [("bag1", 2), ("bag2", 0.6), ("vest1", 0.4), ("helmet1", 0.6), ("flashlight", 1.5),
                        ("bandage", 1), ("pipe", 0.5), ("bat", 1), ("a9", 0.4)]),
    "desk": (0, 2, [("pills", 2), ("bandage", 2), ("choco", 2), ("flashlight", 1), ("a9", 1), ("pistol", 0.35),
                    ("tools", 0.4), ("juice", 1)]),
    "shelf": (1, 4, [("canned", 4), ("chips", 4), ("bread", 3), ("water", 4), ("soda", 4), ("juice", 3),
                     ("choco", 3), ("bandage", 0.6)]),
    "medcab": (1, 3, [("bandage", 5), ("medkit", 2), ("pills", 4)]),
    "locker": (1, 3, [("pistol", 2), ("smg", 0.8), ("shotgun", 1), ("a9", 4), ("a12", 2.5), ("vest1", 1.5),
                      ("vest2", 1), ("helmet1", 1.5), ("helmet2", 0.4), ("knife", 1), ("flashlight", 1),
                      ("bandage", 1), ("ext_mag", 0.4)]),
    "crate": (1, 3, [("scrap", 5), ("engine_part", 2), ("tire", 2), ("battery", 1), ("fuel", 2),
                     ("repair_kit", 1), ("tools", 1), ("crowbar", 1), ("axe", 0.6), ("canned", 1), ("water", 1),
                     ("nails", 0.6), ("bag2", 0.3)]),
    "toolbox": (1, 3, [("tools", 3), ("scrap", 4), ("engine_part", 2), ("repair_kit", 1.5), ("nails", 1),
                       ("crowbar", 1), ("pipe", 1), ("tire", 1)]),
    "milcrate": (1, 4, [("rifle", 1.2), ("sniper", 0.4), ("shotgun", 0.8), ("a762", 4), ("a12", 2), ("a9", 2),
                        ("vest2", 1.2), ("vest3", 0.6), ("helmet2", 1.2), ("mre", 3), ("medkit", 1.2),
                        ("silencer", 0.6), ("scope", 0.6), ("ext_mag", 0.6), ("bag3", 0.5), ("machete", 0.6),
                        ("fuel", 1)]),
    "zombie": (1, 1, [("canned", 2), ("water", 2), ("bandage", 2), ("a9", 2), ("a12", 1), ("a762", 1),
                      ("scrap", 2), ("pills", 1), ("choco", 1), ("money", 3)]),
    "trader": (14, 20, [("canned", 3), ("water", 3), ("mre", 2), ("bread", 2), ("juice", 2), ("bandage", 3),
                        ("medkit", 2), ("pills", 2), ("a9", 3), ("a12", 2), ("a762", 2), ("pistol", 1.2),
                        ("shotgun", 0.8), ("smg", 0.6), ("rifle", 0.4), ("sniper", 0.2), ("vest1", 0.8),
                        ("vest2", 0.5), ("vest3", 0.2), ("helmet1", 0.8), ("helmet2", 0.4), ("bag1", 0.8),
                        ("bag2", 0.6), ("bag3", 0.3), ("machete", 0.6), ("axe", 0.5), ("scrap", 2),
                        ("engine_part", 1.2), ("tire", 1.2), ("battery", 0.6), ("tools", 0.8), ("fuel", 1.5),
                        ("repair_kit", 1), ("silencer", 0.4), ("scope", 0.4), ("ext_mag", 0.4), ("nails", 0.5),
                        ("flashlight", 0.7)]),
    "bandit": (1, 3, [("money", 4), ("a9", 2), ("a12", 1), ("a762", 1), ("canned", 1), ("water", 1),
                      ("bandage", 1), ("pills", 1), ("scrap", 1), ("choco", 1)]),
    "surv": (2, 4, [("canned", 2), ("water", 2), ("bread", 1), ("bandage", 2), ("pills", 1), ("a9", 1),
                    ("scrap", 1), ("fuel", 0.5), ("flashlight", 0.5), ("money", 2)]),
}
for _k in ("desk", "wardrobe", "cabinet", "locker", "milcrate"):
    LOOT[_k][2].append(("money", {"desk": 2.5, "wardrobe": 1.2}.get(_k, 0.5)))


# Тюнинг машин: ключ, название, описание, стоимость каждого уровня
CAR_UPG = [
    ("engine", "Двигатель", "Скорость и разгон",
     [{"engine_part": 1, "scrap": 2}, {"engine_part": 2, "scrap": 3}, {"engine_part": 3, "scrap": 4}]),
    ("armor", "Броня", "Прочность +50 за уровень", [{"scrap": 3}, {"scrap": 5}, {"scrap": 7}]),
    ("tires", "Шины и подвеска", "Управляемость", [{"tire": 2}, {"tire": 2, "scrap": 1}, {"tire": 4, "scrap": 2}]),
    ("tank", "Топливный бак", "Запас топлива +40%", [{"scrap": 2}, {"scrap": 3}, {"scrap": 4}]),
    ("ram", "Таран", "Урон по зомби, меньше повреждений", [{"scrap": 3}, {"scrap": 4}, {"scrap": 6}]),
    ("lights", "Мощные фары", "Яркий свет ночью", [{"battery": 1, "scrap": 1}]),
]
CAR_UPG_D = {k: (name, desc, costs) for k, name, desc, costs in CAR_UPG}


def make_item(iid, rng=None, n=1):
    d = ITEMS[iid]
    it = {"id": iid, "n": n}
    if d["kind"] == "gun":
        it["ammo"] = rng.randint(0, d["mag"]) if rng else 0
        it["mods"] = []
    elif d["kind"] == "melee":
        it["mods"] = []
    elif d["kind"] in ("vest", "helmet"):
        it["dur"] = d["dur"]
    return it


def roll_loot(kind, rng, mult=1.0):
    if kind not in LOOT:
        return []
    lo, hi, table = LOOT[kind]
    count = rng.uniform(lo, hi + 0.99) * mult
    count = int(count) + (1 if rng.random() < count - int(count) else 0)
    total = sum(w for _, w in table)
    out = []
    for _ in range(count):
        r = rng.random() * total
        for iid, w in table:
            r -= w
            if r <= 0:
                break
        if iid in STACK_ROLL:
            n = rng.randint(*STACK_ROLL[iid])
        elif ITEMS[iid]["stack"] > 1:
            n = rng.choice((1, 1, 1, 2))
        else:
            n = 1
        merged = False
        for it in out:
            if it["id"] == iid and ITEMS[iid]["stack"] > 1:
                it["n"] = min(ITEMS[iid]["stack"], it["n"] + n)
                merged = True
        if not merged:
            out.append(make_item(iid, rng, n))
    return out


def max_mag(it):
    d = ITEMS[it["id"]]
    m = d.get("mag", 0)
    if "ext_mag" in it.get("mods", ()):
        m = int(m * 1.5)
    return m


def item_label(it):
    d = ITEMS.get(it["id"])
    if not d:
        return it["id"]
    s = d["name"]
    if d["kind"] == "gun":
        s += " [%d/%d]" % (it.get("ammo", 0), max_mag(it))
    if "dur" in it:
        s += " (%d%%)" % int(100 * it["dur"] / d["dur"])
    return s


def mod_names(it):
    return ", ".join(ITEMS[m]["name"] for m in it.get("mods", ()) if m in ITEMS)
