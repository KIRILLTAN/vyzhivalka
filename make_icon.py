"""Создаёт icon.ico для exe (PNG внутри ICO)."""
import io
import os
import struct

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

from game.app import make_icon  # noqa: E402

pygame.init()
tmp = "icon_tmp.png"
pygame.image.save(make_icon(256), tmp)
with open(tmp, "rb") as f:
    png = f.read()
os.remove(tmp)
with open("icon.ico", "wb") as f:
    f.write(struct.pack("<HHH", 0, 1, 1))
    f.write(struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22))
    f.write(png)
print("icon.ico готов")
