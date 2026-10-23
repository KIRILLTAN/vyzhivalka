"""Шрифты, кнопки, поля ввода."""
import pygame

_fonts = {}
_text_cache = {}

WHITE = (235, 235, 235)
GRAY = (150, 150, 155)
DARK = (20, 22, 26)
ACCENT = (200, 60, 50)
GREEN = (90, 200, 110)
YELLOW = (240, 200, 70)
PANEL = (28, 30, 36)


def font(size, bold=False):
    key = (size, bold)
    f = _fonts.get(key)
    if f is None:
        try:
            f = pygame.font.SysFont("segoeui,arial,tahoma,dejavusans", size, bold=bold)
        except Exception:
            f = pygame.font.Font(None, size + 6)
        _fonts[key] = f
    return f


def render(s, size=18, color=WHITE, bold=False):
    key = (s, size, color, bold)
    surf = _text_cache.get(key)
    if surf is None:
        surf = font(size, bold).render(str(s), True, color)
        if len(_text_cache) > 3000:
            _text_cache.clear()
        _text_cache[key] = surf
    return surf


def text(surf, s, pos, size=18, color=WHITE, bold=False, center=False, right=False, shadow=True):
    img = render(s, size, color, bold)
    x, y = pos
    if center:
        x -= img.get_width() // 2
        y -= img.get_height() // 2
    elif right:
        x -= img.get_width()
    if shadow:
        surf.blit(render(s, size, (0, 0, 0), bold), (x + 1, y + 1))
    surf.blit(img, (x, y))
    return img.get_width()


def panel(surf, rect, color=PANEL, alpha=225, border=(70, 74, 84)):
    r = pygame.Rect(rect)
    s = pygame.Surface(r.size, pygame.SRCALPHA)
    s.fill((*color, alpha))
    surf.blit(s, r.topleft)
    if border:
        pygame.draw.rect(surf, border, r, 1, border_radius=4)


def bar(surf, rect, frac, color, bg=(40, 40, 45)):
    r = pygame.Rect(rect)
    pygame.draw.rect(surf, bg, r, border_radius=3)
    if frac > 0:
        pygame.draw.rect(surf, color, (r.x, r.y, int(r.w * max(0.0, min(1.0, frac))), r.h), border_radius=3)
    pygame.draw.rect(surf, (0, 0, 0), r, 1, border_radius=3)


class Button:
    def __init__(self, rect, label, cb=None, size=24, color=(55, 60, 70), enabled=True):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.cb = cb
        self.size = size
        self.color = color
        self.enabled = enabled

    def draw(self, surf):
        hover = self.enabled and self.rect.collidepoint(pygame.mouse.get_pos())
        c = self.color if self.enabled else (40, 40, 44)
        if hover:
            c = tuple(min(255, v + 30) for v in c)
        pygame.draw.rect(surf, c, self.rect, border_radius=6)
        pygame.draw.rect(surf, (110, 110, 120) if hover else (80, 80, 90), self.rect, 2, border_radius=6)
        text(surf, self.label, self.rect.center, self.size, WHITE if self.enabled else GRAY, center=True)

    def handle(self, e):
        if self.enabled and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos):
            if self.cb:
                self.cb()
            return True
        return False


class TextInput:
    def __init__(self, rect, value="", max_len=16, placeholder="", size=26, upper=False):
        self.rect = pygame.Rect(rect)
        self.value = value
        self.max_len = max_len
        self.placeholder = placeholder
        self.size = size
        self.active = False
        self.upper = upper
        self.t = 0.0

    def handle(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.active = self.rect.collidepoint(e.pos)
            return self.active
        if not self.active:
            return False
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_BACKSPACE:
                self.value = self.value[:-1]
                return True
            if e.key == pygame.K_v and (e.mod & pygame.KMOD_CTRL):
                try:
                    pygame.scrap.init()
                    raw = pygame.scrap.get(pygame.SCRAP_TEXT)
                    if raw:
                        s = raw.decode("utf-8", "ignore").replace("\x00", "").strip()
                        self._add(s)
                except Exception:
                    pass
                return True
        if e.type == pygame.TEXTINPUT:
            self._add(e.text)
            return True
        return False

    def _add(self, s):
        if self.upper:
            s = s.upper()
        self.value = (self.value + s)[:self.max_len]

    def draw(self, surf, dt=0.016):
        self.t += dt
        pygame.draw.rect(surf, (18, 20, 24), self.rect, border_radius=6)
        pygame.draw.rect(surf, (200, 80, 60) if self.active else (80, 80, 90), self.rect, 2, border_radius=6)
        if self.value:
            w = text(surf, self.value, (self.rect.x + 12, self.rect.centery - self.size * 0.62), self.size)
        else:
            w = 0
            text(surf, self.placeholder, (self.rect.x + 12, self.rect.centery - self.size * 0.62), self.size, GRAY)
        if self.active and int(self.t * 2) % 2 == 0:
            x = self.rect.x + 14 + w
            pygame.draw.line(surf, WHITE, (x, self.rect.y + 8), (x, self.rect.bottom - 8), 2)
