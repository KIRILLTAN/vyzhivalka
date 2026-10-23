import sys

import pygame

from . import sound, updater
from .config import SCREEN_W, SCREEN_H, TITLE, VERSION


def make_icon(size=64):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    pygame.draw.circle(s, (25, 30, 25), (c, c), c)
    pygame.draw.circle(s, (95, 140, 85), (c, c), c - 4)
    pygame.draw.circle(s, (220, 40, 30), (c - size // 6, c - size // 10), size // 10)
    pygame.draw.circle(s, (220, 40, 30), (c + size // 6, c - size // 10), size // 10)
    pygame.draw.rect(s, (60, 20, 20), (c - size // 5, c + size // 8, size * 2 // 5, size // 9))
    return s


class App:
    def __init__(self):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("%s v%s" % (TITLE, VERSION))
        pygame.display.set_icon(make_icon())
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.SCALED | pygame.RESIZABLE)
        sound.init()
        self.clock = pygame.time.Clock()
        self.show_help = False
        self.running = True
        updater.cleanup(sys.argv)
        self.updater = updater.Checker()
        from .menus import MainMenu
        self.scene = MainMenu(self)

    def switch(self, scene):
        self.scene = scene

    def quit(self):
        sc = self.scene
        for attr in ("host", "client", "link"):
            obj = getattr(sc, attr, None)
            if obj is not None and hasattr(obj, "close"):
                try:
                    obj.close()
                except Exception:
                    pass
        self.running = False

    def run(self):
        from .menus import draw_help
        while self.running:
            dt = min(self.clock.tick(60) / 1000.0, 0.1)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.quit()
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
                elif self.show_help and e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_F1):
                    self.show_help = False
                elif self.show_help and e.type == pygame.MOUSEBUTTONDOWN:
                    self.show_help = False
                else:
                    self.scene.handle(e)
            if not self.running:
                break
            self.scene.update(dt)
            self.scene.draw(self.screen)
            if self.show_help:
                draw_help(self.screen)
            pygame.display.flip()
        pygame.quit()
