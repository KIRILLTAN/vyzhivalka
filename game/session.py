"""Хост-сессия: лобби, подключения, запуск симуляции и рассылка снимков.
В одиночной игре работает то же самое, только без сети."""
import random

from . import saves
from .config import PORT, SIM_HZ, SNAP_HZ, VERSION
from .net import NetServer, ip_to_code, local_ips
from .sim import Sim

HOST_ID = 1


class HostSession:
    def __init__(self, name, diff, settings, multiplayer, save_slot=None):
        """save_slot: None - новый мир, иначе id сохранения для продолжения."""
        self.name = name
        self.save_data = saves.read(save_slot) if save_slot else None
        if self.save_data:
            diff = self.save_data["diff"]
            meta = next((m for m in saves.list_saves() if m["slot"] == save_slot), {})
            self.slot, self.world_name = save_slot, meta.get("name", "Мир")
        else:
            self.slot, self.world_name = saves.new_slot(multiplayer)
        self.diff = diff
        self.settings = settings if settings is not None else self.save_data["settings"]
        self.save_t = 0.0
        self.multiplayer = multiplayer
        self.server = NetServer(PORT) if multiplayer else None
        self.ips = local_ips() if multiplayer else ["127.0.0.1"]
        self.ip_idx = 0
        self.ip = self.ips[0]
        self.code = ip_to_code(self.ip) if multiplayer else ""
        self.players = {HOST_ID: name}
        self.local_inbox = []
        self.sim = None
        self.seed = self.save_data["seed"] if self.save_data else random.randrange(1, 1 << 30)
        self.acc = 0.0
        self.snap_acc = 0.0
        self.paused = False

    # --- отправка ---
    def send(self, pid, msg):
        if pid == HOST_ID:
            self.local_inbox.append(msg)
        elif self.server:
            self.server.send(pid, msg)

    def broadcast(self, msg):
        for pid in list(self.players):
            self.send(pid, msg)

    def lobby_msg(self):
        return {"t": "lobby", "players": [[pid, n] for pid, n in self.players.items()], "code": self.code,
                "host": HOST_ID, "diff": self.diff, "settings": self.settings}

    def start_msg(self):
        edits = self.sim.world.export_edits() if self.sim else []
        return {"t": "start", "seed": self.seed, "diff": self.diff, "settings": self.settings, "edits": edits}

    def set_setting(self, key, value):
        """Меняет настройку прямо во время игры (только хост)."""
        self.settings[key] = value
        if self.sim:
            self.sim.settings[key] = value
            if key == "respawn":
                for p in self.sim.players.values():
                    if not p.alive:
                        p.respawn_t = 0.0 if value else -1
                if value:
                    self.sim.over = False
            self.sim._all({"k": "msg", "t": "Хост изменил настройку: %s - %s" % (
                {"respawn": "возрождение", "keep_inv": "сохранение вещей при смерти"}.get(key, key),
                "включено" if value else "выключено")})
        elif self.server:
            self.broadcast(self.lobby_msg())

    def save_game(self):
        if not self.sim or self.sim.over:
            return False
        try:
            saves.write(self.slot, self.world_name, self.sim.to_save(), self.multiplayer)
            return True
        except OSError:
            return False

    # --- лобби ---
    def next_network(self):
        """Переключает показываемый код на другой сетевой адаптер (LAN / Radmin / Hamachi)."""
        self.ip_idx = (self.ip_idx + 1) % len(self.ips)
        self.ip = self.ips[self.ip_idx]
        self.code = ip_to_code(self.ip)
        if not self.sim:
            self.broadcast(self.lobby_msg())

    def kick(self, pid):
        if pid == HOST_ID or pid not in self.players:
            return
        self.send(pid, {"t": "kick"})
        if self.server:
            self.server.drop(pid)
        self._remove(pid)

    def _remove(self, pid):
        self.players.pop(pid, None)
        if self.sim:
            self.sim.remove_player(pid)
        else:
            self.broadcast(self.lobby_msg())

    def start(self):
        if self.save_data:
            self.sim = Sim.from_save(self.save_data, self.settings)
            self.save_data = None
        else:
            self.sim = Sim(self.seed, self.diff, self.settings)
        for pid, n in self.players.items():
            self.sim.add_player(pid, n)
        self.broadcast(self.start_msg())

    def local_send(self, msg):
        if self.sim:
            self.sim.handle(HOST_ID, msg)

    # --- цикл ---
    def update(self, dt):
        if self.server:
            for cid, m in self.server.poll():
                t = m.get("t") if isinstance(m, dict) else None
                if t == "_disc":
                    if cid in self.players:
                        self._remove(cid)
                    self.server.drop(cid)
                elif t == "hello":
                    self._hello(cid, m)
                elif cid in self.players and self.sim:
                    self.sim.handle(cid, m)
        if self.sim and not self.paused:
            self.acc += min(dt, 0.25)
            step = 1.0 / SIM_HZ
            while self.acc >= step:
                self.sim.update(step)
                self.acc -= step
            self.snap_acc += dt
            if self.snap_acc >= 1.0 / SNAP_HZ:
                self.snap_acc = 0.0
                for pid in list(self.sim.players):
                    self.send(pid, self.sim.snapshot(pid))
                self.sim.events.clear()
            self.save_t += dt
            if self.save_t >= 90:
                self.save_t = 0.0
                if self.save_game():
                    self.send(HOST_ID, {"t": "saved"})

    def _hello(self, cid, m):
        if cid in self.players:
            return
        name = str(m.get("name", "Игрок"))[:16].strip() or "Игрок"
        reason = None
        if m.get("ver") != VERSION:
            reason = "Разные версии игры (у хоста %s)" % VERSION
        elif len(self.players) >= self.settings.get("max_players", 4):
            reason = "Комната заполнена"
        if reason:
            self.server.send(cid, {"t": "deny", "reason": reason})
            self.server.drop(cid)
            return
        taken = set(self.players.values())
        base, k = name, 2
        while name in taken:
            name = "%s%d" % (base, k)
            k += 1
        self.players[cid] = name
        self.send(cid, {"t": "welcome", "id": cid})
        if self.sim:
            self.sim.add_player(cid, name)
            self.send(cid, self.start_msg())
        else:
            self.broadcast(self.lobby_msg())

    def close(self):
        if self.sim and not getattr(self, "closed", False):
            self.save_game()
        self.closed = True
        if self.server:
            for pid in list(self.players):
                if pid != HOST_ID:
                    self.server.send(pid, {"t": "end"})
            self.server.close()
            self.server = None


class LocalLink:
    """Связь игрового экрана хоста с собственной сессией без сети."""

    alive = True

    def __init__(self, host):
        self.host = host

    def send(self, msg):
        self.host.local_send(msg)

    def poll(self):
        msgs = self.host.local_inbox
        self.host.local_inbox = []
        return msgs

    def close(self):
        pass
