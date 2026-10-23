"""Сохранения мира в %APPDATA%\\Vyzhivalka\\saves."""
import json
import os
import time

from .config import data_dir


def _dir():
    d = os.path.join(data_dir(), "saves")
    os.makedirs(d, exist_ok=True)
    return d


def new_slot(mp):
    names = {m["name"] for m in list_saves()}
    k = 1
    while ("Мир %d" % k) in names:
        k += 1
    return "world_%d" % int(time.time() * 1000), "Мир %d" % k


def list_saves():
    out = []
    for f in os.listdir(_dir()):
        if f.endswith(".meta.json"):
            try:
                with open(os.path.join(_dir(), f), "r", encoding="utf-8") as fh:
                    m = json.load(fh)
                m["slot"] = f[:-len(".meta.json")]
                out.append(m)
            except Exception:
                pass
    out.sort(key=lambda m: m.get("time", 0), reverse=True)
    return out


def _write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def write(slot, name, data, mp):
    _write_json(os.path.join(_dir(), slot + ".json"), data)
    _write_json(os.path.join(_dir(), slot + ".meta.json"), {
        "name": name, "day": data.get("day", 1), "diff": data.get("diff"), "mp": mp, "time": time.time(),
        "players": sorted(data.get("players", {}).keys()), "version": data.get("version")})


def read(slot):
    with open(os.path.join(_dir(), slot + ".json"), "r", encoding="utf-8") as f:
        return json.load(f)


def delete(slot):
    for ext in (".json", ".meta.json"):
        try:
            os.remove(os.path.join(_dir(), slot + ext))
        except OSError:
            pass
