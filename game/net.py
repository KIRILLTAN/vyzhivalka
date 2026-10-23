"""Сеть по локальной сети: TCP, сообщения = длина + zlib(JSON). Код комнаты = закодированный IP хоста."""
import json
import queue
import socket
import struct
import threading
import zlib

ALPH = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def encode(obj):
    data = zlib.compress(json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), 1)
    return struct.pack(">I", len(data)) + data


def _recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    return bytes(buf)


def read_msg(sock):
    n = struct.unpack(">I", _recv_exact(sock, 4))[0]
    if n > 20_000_000:
        raise ConnectionError("bad frame")
    return json.loads(zlib.decompress(_recv_exact(sock, n)).decode("utf-8"))


def _rank(ip):
    if ip.startswith("192.168."):
        return 0
    if ip.startswith("10."):
        return 1
    if ip.startswith("26."):
        return 2
    if ip.startswith("25."):
        return 3
    if ip.startswith("172."):
        return 4
    return 5


def net_label(ip):
    if ip.startswith("26."):
        return "Radmin VPN"
    if ip.startswith("25."):
        return "Hamachi"
    if ip.startswith(("192.168.", "10.", "172.")):
        return "Локальная сеть"
    return "Сеть"


def local_ips():
    """Все IPv4-адреса компьютера, самые вероятные для LAN - первыми."""
    ips = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.append(info[4][0])
    except Exception:
        pass
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ips.append(s.getsockname()[0])
    except Exception:
        pass
    finally:
        s.close()
    out = []
    for ip in ips:
        if ip not in out and not ip.startswith(("127.", "169.254.", "0.")):
            out.append(ip)
    out.sort(key=_rank)
    return out or ["127.0.0.1"]


def local_ip():
    return local_ips()[0]


def ip_to_code(ip):
    n = int.from_bytes(socket.inet_aton(ip), "big")
    out = []
    for _ in range(7):
        out.append(ALPH[n % 32])
        n //= 32
    s = "".join(reversed(out))
    return s[:3] + "-" + s[3:]


def code_to_ip(code):
    code = code.strip()
    if code.count(".") == 3:
        socket.inet_aton(code)
        return code
    s = code.upper().replace("-", "").replace(" ", "").replace("O", "0").replace("I", "1")
    if len(s) != 7 or any(ch not in ALPH for ch in s):
        raise ValueError("Неверный код комнаты")
    n = 0
    for ch in s:
        n = n * 32 + ALPH.index(ch)
    if n >= 1 << 32:
        raise ValueError("Неверный код комнаты")
    return socket.inet_ntoa(n.to_bytes(4, "big"))


class _Peer:
    def __init__(self, cid, sock, inbox):
        self.cid, self.sock, self.inbox = cid, sock, inbox
        self.lock = threading.Lock()
        self.alive = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        try:
            while self.alive:
                self.inbox.put((self.cid, read_msg(self.sock)))
        except Exception:
            pass
        if self.alive:
            self.alive = False
            self.inbox.put((self.cid, {"t": "_disc"}))
        try:
            self.sock.close()
        except Exception:
            pass

    def send(self, data):
        if not self.alive:
            return
        try:
            with self.lock:
                self.sock.sendall(data)
        except Exception:
            self.close()
            self.inbox.put((self.cid, {"t": "_disc"}))

    def close(self):
        self.alive = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


class NetServer:
    def __init__(self, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("0.0.0.0", port))
        self.sock.listen(16)
        self.inbox = queue.Queue()
        self.peers = {}
        self.next_id = 2
        self.running = True
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while self.running:
            try:
                s, _ = self.sock.accept()
            except Exception:
                break
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            cid = self.next_id
            self.next_id += 1
            self.peers[cid] = _Peer(cid, s, self.inbox)

    def poll(self):
        out = []
        while True:
            try:
                out.append(self.inbox.get_nowait())
            except queue.Empty:
                return out

    def send(self, cid, obj):
        p = self.peers.get(cid)
        if p:
            p.send(encode(obj))

    def drop(self, cid):
        p = self.peers.pop(cid, None)
        if p:
            p.close()

    def close(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass
        for p in list(self.peers.values()):
            p.close()
        self.peers.clear()


class NetClient:
    """Подключение к хосту. Подключается в фоне; status: connecting / ok / error."""

    def __init__(self, ip, port):
        self.inbox = queue.Queue()
        self.sock = None
        self.status = "connecting"
        self.error = ""
        self.alive = False
        self.lock = threading.Lock()
        threading.Thread(target=self._run, args=(ip, port), daemon=True).start()

    def _run(self, ip, port):
        try:
            s = socket.create_connection((ip, port), timeout=5)
            s.settimeout(None)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock = s
            self.alive = True
            self.status = "ok"
        except Exception as e:
            self.status = "error"
            self.error = str(e)
            return
        try:
            while self.alive:
                self.inbox.put(read_msg(self.sock))
        except Exception:
            pass
        self.alive = False

    def send(self, obj):
        if not self.alive:
            return
        try:
            with self.lock:
                self.sock.sendall(encode(obj))
        except Exception:
            self.alive = False

    def poll(self):
        out = []
        while True:
            try:
                out.append(self.inbox.get_nowait())
            except queue.Empty:
                return out

    def close(self):
        self.alive = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
