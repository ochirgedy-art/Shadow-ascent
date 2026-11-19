#!/usr/bin/env python3
"""
SHADOW ASCENT  -  a pixel-art ninja tower-climbing parkour game
================================================================
Requires:  pip install pygame      (Python 3.8+, pygame 2.x)
Run:       python shadow_ascent.py

CONTROLS
  Move ............ Arrow keys / A D
  Jump / Double ... Space, W, Up, Z or K   (press again in mid-air for the double jump)
  Dash ............ X, L or Shift         (air-dash, recharges on ground / wall grab)
  Wall grab ....... Hold toward a mossy/icy pillar (or hold C / J / Ctrl) while falling.
                    You slide slowly... then faster... then your grip gives out!
                    Press Jump while gripping to wall-jump.
  Drop through .... Down + Jump on a thin platform
  Pause ........... P or Esc        Restart ... R        Fullscreen ... F11

THE TOWER
  4 biomes, getting harder as you climb:  Twilight Foothills -> Rain Terraces ->
  Frozen Spires (ice, wind) -> Storm Crown (lightning).  Spikes, saws, crumbling and
  moving platforms, wall-jump chimneys and checkpoint lanterns along the way.
"""
import math
import random
import sys
import array

import pygame

# ----------------------------------------------------------------------------
# constants
# ----------------------------------------------------------------------------
W, H = 320, 180            # internal pixel resolution (scaled up to the window)
FPS = 60
TL, TR = 56, 264           # playable interior of the tower (x range)
WT = 16                    # outer tower wall thickness
TOWER_H = 5600             # climb height in pixels
GRAV = 0.35
MAXFALL = 6.4
GRIP_MAX = 110             # frames you can cling to a wall
CHIM_GAP = 46              # width of the wall-jump chimneys


def clamp(v, a, b):
    return a if v < a else b if v > b else v


def lerp(a, b, t):
    return a + (b - a) * t


def icol(c):
    return (int(clamp(c[0], 0, 255)), int(clamp(c[1], 0, 255)), int(clamp(c[2], 0, 255)))


def lerp_c(c1, c2, t):
    return icol((lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t)))


def scale_c(c, k):
    return icol((c[0] * k, c[1] * k, c[2] * k))


def smooth(x):
    x = clamp(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


# ----------------------------------------------------------------------------
# biomes
# ----------------------------------------------------------------------------
BIOMES = [
    dict(name="TWILIGHT FOOTHILLS", sky_top=(72, 58, 120), sky_bot=(255, 152, 98), amb=(240, 222, 214),
         stone=(124, 110, 118), light=(172, 156, 158), dark=(76, 66, 84), top=(92, 152, 74), top2=(138, 202, 98),
         cloud=(255, 190, 160), flame=(255, 170, 70), rain=0.0, snow=0.0, wind=0.0, thunder=0.0),
    dict(name="RAIN TERRACES", sky_top=(24, 32, 54), sky_bot=(92, 110, 136), amb=(172, 186, 214),
         stone=(80, 92, 106), light=(120, 136, 150), dark=(46, 54, 70), top=(52, 112, 96), top2=(90, 160, 130),
         cloud=(66, 76, 96), flame=(255, 150, 60), rain=0.85, snow=0.0, wind=0.2, thunder=0.55),
    dict(name="FROZEN SPIRES", sky_top=(116, 154, 206), sky_bot=(222, 238, 250), amb=(216, 230, 248),
         stone=(128, 156, 184), light=(194, 220, 240), dark=(84, 108, 138), top=(238, 246, 255), top2=(205, 226, 244),
         cloud=(244, 248, 255), flame=(130, 205, 255), rain=0.0, snow=1.0, wind=0.65, thunder=0.0),
    dict(name="STORM CROWN", sky_top=(12, 8, 26), sky_bot=(66, 36, 84), amb=(132, 130, 182),
         stone=(78, 70, 98), light=(122, 112, 150), dark=(38, 32, 52), top=(126, 84, 206), top2=(208, 158, 255),
         cloud=(48, 36, 68), flame=(196, 124, 255), rain=1.0, snow=0.3, wind=1.0, thunder=1.0),
]


def biome_at(y):
    return int(clamp(-y / TOWER_H * 4, 0, 3.999))


def biome_t(p):
    """p in [0,4]; returns blend factors for the 3 biome boundaries."""
    return (smooth((p - 0.85) / 0.3), smooth((p - 1.85) / 0.3), smooth((p - 2.85) / 0.3))


def biome_weights(t):
    t1, t2, t3 = t
    return [(1 - t1) * (1 - t2) * (1 - t3), t1 * (1 - t2) * (1 - t3), t2 * (1 - t3), t3]


def bmix(w, key):
    if isinstance(BIOMES[0][key], tuple):
        return tuple(sum(w[i] * BIOMES[i][key][c] for i in range(4)) for c in range(3))
    return sum(w[i] * BIOMES[i][key] for i in range(4))


# ----------------------------------------------------------------------------
# tiny 3x5 pixel font
# ----------------------------------------------------------------------------
GLYPHS = {
    "A": "010101111101101", "B": "110101110101110", "C": "011100100100011", "D": "110101101101110",
    "E": "111100110100111", "F": "111100110100100", "G": "011100101101011", "H": "101101111101101",
    "I": "111010010010111", "J": "001001001101010", "K": "101101110101101", "L": "100100100100111",
    "M": "101111111101101", "N": "110101101101101", "O": "010101101101010", "P": "110101110100100",
    "Q": "010101101110011", "R": "110101110101101", "S": "011100010001110", "T": "111010010010010",
    "U": "101101101101111", "V": "101101101101010", "W": "101101111111101", "X": "101101010101101",
    "Y": "101101010010010", "Z": "111001010100111", "0": "111101101101111", "1": "010110010010111",
    "2": "110001010100111", "3": "110001010001110", "4": "101101111001001", "5": "111100110001110",
    "6": "011100111101111", "7": "111001010010010", "8": "111101111101111", "9": "111101111001110",
    ":": "000010000010000", ".": "000000000000010", "-": "000000111000000", "!": "010010010000010",
    "/": "001001010100100", "?": "110001010000010", "%": "101001010100101", "+": "000010111010000",
    ",": "000000000010100",
}
_gcache = {}


def glyph(ch, col, sc):
    k = (ch, col, sc)
    g = _gcache.get(k)
    if g is None:
        g = pygame.Surface((3 * sc, 5 * sc), pygame.SRCALPHA)
        bits = GLYPHS.get(ch)
        if bits:
            for i, b in enumerate(bits):
                if b == "1":
                    g.fill(col, ((i % 3) * sc, (i // 3) * sc, sc, sc))
        _gcache[k] = g
    return g


def text(surf, s, x, y, col=(255, 255, 255), sc=1, shadow=(8, 8, 18), center=False):
    s = s.upper()
    w = len(s) * 4 * sc - sc
    if center:
        x -= w // 2
    if shadow:
        for i, ch in enumerate(s):
            surf.blit(glyph(ch, shadow, sc), (x + i * 4 * sc + sc, y + sc))
    for i, ch in enumerate(s):
        surf.blit(glyph(ch, col, sc), (x + i * 4 * sc, y))
    return w


# ----------------------------------------------------------------------------
# procedural sound (tiny synth, no asset files)
# ----------------------------------------------------------------------------
class Sound:
    RATE = 22050

    def __init__(self):
        self.snd = {}
        self.rain = None
        self.ok = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(self.RATE, -16, 1, 512)
                pygame.mixer.init()
            freq, fmt, ch = pygame.mixer.get_init()
            if fmt != -16:
                return
            self.RATE, self.ch = freq, ch
            self.ok = True
        except Exception:
            return
        try:
            self.snd["jump"] = self.tone(260, 520, .12, .22)
            self.snd["djump"] = self.tone(380, 840, .15, .22)
            self.snd["dash"] = self.tone(900, 180, .15, .16, noise=.7)
            self.snd["land"] = self.tone(130, 60, .08, .3, noise=.4, wave="sine")
            self.snd["death"] = self.tone(320, 50, .38, .26, noise=.35)
            self.snd["check"] = self.tone(660, 1320, .28, .22, wave="sine")
            self.snd["crumble"] = self.tone(110, 40, .25, .22, noise=.8)
            self.snd["zap"] = self.tone(1400, 100, .3, .2, noise=.5)
            self.snd["thunder"] = self.noise(1.9, .03, .9, 1.6)
            self.rain = self.noise(2.0, .35, .22, 0)
            self.rain.set_volume(0)
            self.rain.play(-1)
        except Exception:
            self.ok = False

    def _mk(self, buf):
        if self.ch > 1:
            b2 = array.array("h")
            for v in buf:
                for _ in range(self.ch):
                    b2.append(v)
            buf = b2
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def tone(self, f0, f1, dur, vol, noise=0.0, wave="sq"):
        n = int(self.RATE * dur)
        buf = array.array("h")
        ph = 0.0
        for i in range(n):
            t = i / n
            ph += (f0 + (f1 - f0) * t) / self.RATE
            v = (1 if (ph % 1) < .5 else -1) if wave == "sq" else math.sin(ph * 6.2832)
            v = v * (1 - noise) + (random.random() * 2 - 1) * noise
            buf.append(int(v * (1 - t) ** 1.5 * vol * 32767))
        return self._mk(buf)

    def noise(self, dur, lp, vol, decay):
        n = int(self.RATE * dur)
        buf = array.array("h")
        y = 0.0
        for i in range(n):
            y += ((random.random() * 2 - 1) - y) * lp
            env = (1 - i / n) ** decay if decay else 1.0
            buf.append(int(clamp(y * vol * env * 3, -1, 1) * 32767))
        return self._mk(buf)

    def play(self, name, vol=1.0):
        s = self.snd.get(name)
        if s and self.ok:
            s.set_volume(clamp(vol, 0, 1))
            s.play()

    def set_rain(self, v):
        if self.rain and self.ok:
            self.rain.set_volume(clamp(v, 0, 1) * 0.55)


# ----------------------------------------------------------------------------
# pixel art generation
# ----------------------------------------------------------------------------
HOOD = (28, 30, 54)
HOOD_HI = (54, 60, 96)
CLOTH = (40, 46, 78)
CLOTH_DK = (24, 27, 48)
CLOTH_HI = (70, 80, 122)
RED = (218, 52, 62)
RED_DK = (150, 30, 46)
SKIN = (238, 192, 150)
STEEL = (196, 206, 226)
GOLD = (232, 182, 72)
WRAP = (96, 78, 66)
FOOT = (18, 20, 36)

POSES = {
    "idle0": dict(b=(0, 0), A=((5, 13), (5, 15)), B=((9, 13), (9, 15)), a=(5, 10), f=(11, 10)),
    "idle1": dict(b=(0, 1), A=((5, 13), (5, 15)), B=((9, 13), (9, 15)), a=(5, 10), f=(11, 10)),
    "run0": dict(b=(1, 0), A=((5, 13), (3, 14)), B=((10, 13), (12, 15)), a=(11, 9), f=(4, 9)),
    "run1": dict(b=(1, 1), A=((6, 13), (6, 15)), B=((10, 12), (9, 13)), a=(8, 10), f=(8, 10)),
    "run2": dict(b=(1, 0), A=((10, 13), (12, 15)), B=((5, 13), (3, 14)), a=(4, 9), f=(12, 9)),
    "run3": dict(b=(1, 1), A=((10, 12), (9, 13)), B=((6, 13), (6, 15)), a=(8, 10), f=(8, 10)),
    "jump": dict(b=(0, 0), A=((4, 12), (5, 14)), B=((10, 12), (9, 14)), a=(3, 5), f=(12, 4)),
    "fall": dict(b=(0, 0), A=((4, 13), (3, 15)), B=((10, 13), (11, 15)), a=(2, 6), f=(13, 6)),
    "cling": dict(b=(1, 0), A=((8, 13), (8, 15)), B=((11, 12), (11, 14)), a=(11, 6), f=(11, 1)),
    "land": dict(b=(0, 2), A=((3, 13), (4, 15)), B=((11, 13), (10, 15)), a=(4, 11), f=(10, 11)),
    "dash": dict(b=(0, 0), A=((3, 12), (0, 13)), B=((4, 13), (1, 15)), a=(1, 7), f=(2, 9)),
    "spin": dict(b=(0, 0), A=((4, 12), (6, 13)), B=((9, 12), (8, 13)), a=(6, 10), f=(9, 10)),
}


def build_ninja(name):
    P = POSES[name]
    bx, by = P["b"]
    s = pygame.Surface((16, 16), pygame.SRCALPHA)

    def R(x, y, w, h, c):
        s.fill(c, (x, y, w, h))

    def leg(hip, pts, col):
        k, f = pts
        pygame.draw.line(s, col, hip, k, 2)
        pygame.draw.line(s, col, k, f, 2)
        s.set_at(((k[0] + f[0]) // 2, (k[1] + f[1]) // 2), WRAP)
        R(f[0] - 1, f[1], 3, 1, FOOT)

    # back limbs
    pygame.draw.line(s, CLOTH_DK, (5 + bx, 7 + by), P["a"], 2)
    s.set_at(P["a"], WRAP)
    leg((6 + bx, 11 + by), P["A"], CLOTH_DK)
    # katana on the back
    pygame.draw.line(s, STEEL, (3 + bx, 3 + by), (6 + bx, 10 + by), 1)
    R(1 + bx, 1 + by, 2, 1, GOLD)
    R(2 + bx, 2 + by, 1, 2, WRAP)
    # torso
    R(5 + bx, 6 + by, 6, 5, CLOTH)
    R(6 + bx, 6 + by, 3, 1, CLOTH_HI)
    R(5 + bx, 7 + by, 1, 3, CLOTH_DK)
    for i in range(4):
        s.set_at((6 + bx + i, 6 + by + i), WRAP)
    R(5 + bx, 10 + by, 6, 1, RED)
    R(9 + bx, 10 + by, 1, 2, RED_DK)
    # head
    R(5 + bx, 1 + by, 6, 5, HOOD)
    R(6 + bx, 1 + by, 3, 1, HOOD_HI)
    R(5 + bx, 1 + by, 1, 4, HOOD_HI)
    R(7 + bx, 3 + by, 4, 2, SKIN)
    R(7 + bx, 3 + by, 4, 1, (206, 154, 120))
    s.set_at((9 + bx, 3 + by), (255, 255, 255))
    s.set_at((10 + bx, 3 + by), (20, 20, 30))
    R(5 + bx, 2 + by, 6, 1, RED)
    R(7 + bx, 2 + by, 2, 1, STEEL)
    R(6 + bx, 5 + by, 4, 1, HOOD)
    # front limbs
    leg((9 + bx, 11 + by), P["B"], CLOTH)
    pygame.draw.line(s, CLOTH, (10 + bx, 7 + by), P["f"], 2)
    s.set_at(P["f"], WRAP)
    return s


def make_platform_surface(w, h, bi, style, seed):
    rng = random.Random(seed)
    B = BIOMES[bi]
    OY, EX = 5, 10
    s = pygame.Surface((w, OY + h + EX), pygame.SRCALPHA)
    stone, light, dark, top, top2 = B["stone"], B["light"], B["dark"], B["top"], B["top2"]
    if style == "ice":
        stone = lerp_c(stone, (130, 200, 240), .55)
        light = lerp_c(light, (225, 247, 255), .6)
        dark = lerp_c(dark, (60, 120, 190), .5)
        top, top2 = (222, 244, 255), (252, 255, 255)
    elif style == "crumble":
        stone = lerp_c(stone, (118, 88, 66), .5)
        dark = lerp_c(dark, (44, 30, 24), .5)
        light = lerp_c(light, (176, 136, 104), .4)
    s.fill(stone, (0, OY, w, h))
    # bricks
    for r, y in enumerate(range(0, h, 5)):
        by = OY + y
        bh = min(5, h - y)
        off = 0 if r % 2 == 0 else 6
        for x0 in range(off - 12, w, 12):
            if rng.random() < .35:
                c = lerp_c(stone, light, .22) if rng.random() < .6 else lerp_c(stone, dark, .25)
                s.fill(c, (x0 + 1, by, 11, max(1, bh - 1)))
            if x0 > 0:
                s.fill(dark, (x0, by, 1, bh))
        if bh >= 5:
            s.fill(dark, (0, by + 4, w, 1))
    for _ in range(w * h // 14):
        s.set_at((rng.randrange(w), OY + rng.randrange(h)), light if rng.random() < .5 else dark)
    # top cap
    s.fill(top, (0, OY, w, 2))
    s.fill(lerp_c(top, dark, .4), (0, OY + 2, w, 1))
    for x in range(w):
        if rng.random() < .45:
            s.set_at((x, OY), top2)
    # bevels
    s.fill(light, (0, OY + 3, 1, max(0, h - 3)))
    s.fill(dark, (w - 1, OY + 3, 1, max(0, h - 3)))
    s.fill(dark, (0, OY + h - 1, w, 1))
    for (cx_, cy_) in ((0, OY), (w - 1, OY), (0, OY + h - 1), (w - 1, OY + h - 1)):
        s.set_at((cx_, cy_), (0, 0, 0, 0))
    # biome decoration
    if bi == 0:
        for x in range(1, w - 1):
            if rng.random() < .4:
                ht = rng.randint(1, 3)
                s.fill(top2 if rng.random() < .5 else top, (x, OY - ht, 1, ht))
            if rng.random() < .03:
                s.set_at((x, OY - 3), (255, 140, 190))
        for _ in range(max(1, w // 14)):
            x, ln = rng.randrange(2, w - 2), rng.randint(2, 7)
            s.fill((54, 112, 60), (x, OY + h, 1, ln))
            if ln > 3:
                s.set_at((x + 1, OY + h + ln - 2), (92, 164, 84))
    elif bi == 1:
        for _ in range(max(1, w // 16)):
            x, ln = rng.randrange(1, max(2, w - 8)), rng.randint(3, 7)
            s.fill((116, 168, 214), (x, OY, min(7, w - x - 1), 1))
        for _ in range(max(1, w // 10)):
            x, ln = rng.randrange(2, w - 2), rng.randint(2, 6)
            s.fill((96, 142, 190), (x, OY + h, 1, ln))
            s.set_at((x, OY + h + ln), (190, 225, 255))
        for _ in range(w // 8):
            s.set_at((rng.randrange(w), OY + rng.randrange(2, h)), (60, 120, 100))
    elif bi == 2:
        for x in range(1, w - 1):
            ht = 1 + int(1.4 * (1 + math.sin(x * .45 + seed)) / 2) + (1 if rng.random() < .3 else 0)
            s.fill(top, (x, OY - ht, 1, ht))
            if rng.random() < .2:
                s.set_at((x, OY - ht), (255, 255, 255))
        for _ in range(max(1, w // 9)):
            x, ln = rng.randrange(2, w - 2), rng.randint(3, 9)
            for j in range(ln):
                wd = 3 if j == 0 else (2 if j < ln // 2 else 1)
                s.fill((196, 228, 250) if j % 3 else (240, 252, 255), (x - wd // 2, OY + h + j, wd, 1))
    else:
        for x in range(2, w - 3, 5):
            if rng.random() < .55:
                ht = rng.randint(2, 5)
                for j in range(ht):
                    s.fill(top2 if j == ht - 1 else top, (x - (ht - j) // 3, OY - 1 - j, 1 + (ht - j) // 3 * 2 + 1 if j < 2 else 1, 1))
        for x in range(6, w - 6, 16):
            rune = rng.choice((((0, 0), (1, 0), (2, 0), (1, 1), (1, 2)), ((0, 0), (0, 1), (0, 2), (1, 1), (2, 0), (2, 2)),
                               ((1, 0), (0, 1), (2, 1), (1, 2))))
            for (rx, ry) in rune:
                if OY + 4 + ry < OY + h - 1:
                    s.set_at((x + rx, OY + 4 + ry), top2)
        for _ in range(max(1, w // 14)):
            x, ln = rng.randrange(2, w - 2), rng.randint(2, 5)
            s.fill(top, (x, OY + h, 1, ln))
            s.set_at((x, OY + h + ln), top2)
    # style extras
    if style == "crumble":
        for _ in range(max(2, w // 10)):
            x, y = rng.randrange(2, w - 2), OY + rng.randrange(2, max(3, h - 3))
            for j in range(rng.randint(2, 4)):
                s.set_at((x + (j % 2), y + j), dark)
    elif style == "move":
        s.fill(GOLD, (0, OY + 2, 3, min(6, h - 2)))
        s.fill(GOLD, (w - 3, OY + 2, 3, min(6, h - 2)))
        s.fill((150, 110, 40), (0, OY + 7, 3, 1))
        s.fill((150, 110, 40), (w - 3, OY + 7, 3, 1))
        s.set_at((1, OY + 4), (255, 240, 180))
        s.set_at((w - 2, OY + 4), (255, 240, 180))
    elif style == "ice":
        for x in range(2, w - 4, 7):
            for j in range(3):
                s.set_at((x + j, OY + 4 + j), (255, 255, 255))
    return s


def make_back_tile(bi):
    B = BIOMES[bi]
    rng = random.Random(100 + bi)
    base = scale_c(B["dark"], .62)
    mortar = scale_c(B["dark"], .36)
    s = pygame.Surface((32, 32))
    s.fill(mortar)
    for r in range(4):
        y = r * 8
        off = 0 if r % 2 == 0 else -8
        for x0 in range(off, 32, 16):
            sh = rng.randint(-8, 8)
            s.fill(icol((base[0] + sh, base[1] + sh, base[2] + sh)), (x0 + 1, y + 1, 14, 6))
            s.fill(scale_c(base, 1.25), (x0 + 1, y + 1, 14, 1))
    for _ in range(26):
        s.set_at((rng.randrange(32), rng.randrange(32)), scale_c(base, rng.choice((.8, 1.3))))
    if bi == 1:
        for _ in range(5):
            x, y, ln = rng.randrange(32), rng.randrange(20), rng.randint(5, 11)
            s.fill((60, 84, 120), (x, y, 1, ln))
    elif bi == 2:
        for _ in range(14):
            s.set_at((rng.randrange(32), rng.randrange(32)), (190, 220, 245))
    elif bi == 3:
        for _ in range(3):
            x, y = rng.randrange(4, 28), rng.randrange(0, 24)
            for j in range(6):
                s.set_at((x + (j % 2), y + j), (110, 70, 170))
    return s


def make_wall_tile(bi):
    B = BIOMES[bi]
    rng = random.Random(200 + bi)
    st, li, da = B["stone"], B["light"], B["dark"]
    s = pygame.Surface((16, 32))
    s.fill(st)
    for by in (0, 16):
        s.fill(li, (0, by, 16, 1))
        s.fill(lerp_c(li, st, .5), (0, by + 1, 1, 15))
        s.fill(da, (15, by, 1, 16))
        s.fill(da, (0, by + 15, 16, 1))
    s.fill(da, (0, 15, 16, 1))
    for _ in range(40):
        s.set_at((rng.randrange(16), rng.randrange(32)), li if rng.random() < .5 else da)
    if bi == 0:
        for _ in range(3):
            x, ln = rng.randrange(1, 15), rng.randint(5, 14)
            s.fill((58, 118, 62), (x, 0, 1, ln))
            s.set_at((x + 1, ln - 3), (100, 170, 84))
    elif bi == 1:
        for _ in range(4):
            s.fill((108, 160, 206), (rng.randrange(1, 15), rng.randrange(0, 12), 1, rng.randint(6, 16)))
        s.fill((50, 112, 96), (0, 0, 16, 2))
    elif bi == 2:
        s.fill((240, 248, 255), (0, 0, 16, 2))
        s.fill((240, 248, 255), (0, 16, 16, 2))
        for x in range(1, 15, 4):
            s.fill((214, 236, 252), (x, 2, 2, rng.randint(2, 5)))
    else:
        x = 8
        for y in range(32):
            x = int(clamp(x + rng.choice((-1, 0, 1)), 2, 13))
            s.set_at((x, y), B["top2"])
            s.set_at((x + 1, y), B["top"])
    return s


BAYER = ((0, 2), (3, 1))


def make_sky(bi):
    B = BIOMES[bi]
    s = pygame.Surface((W, H))
    Q = 16
    for y in range(H):
        t = y / (H - 1) * (Q - 1)
        n = int(t)
        f = t - n
        c0 = lerp_c(B["sky_top"], B["sky_bot"], n / (Q - 1))
        c1 = lerp_c(B["sky_top"], B["sky_bot"], min(n + 1, Q - 1) / (Q - 1))
        for x in range(W):
            s.set_at((x, y), c1 if f > (BAYER[y & 1][x & 1] + .5) / 4 else c0)
    return s


def make_vignette():
    s = pygame.Surface((W, H))
    for y in range(H):
        for x in range(W):
            dx, dy = (x - W / 2) / (W / 2), (y - H / 2) / (H / 2)
            d = dx * dx * .8 + dy * dy
            v = 1 - clamp((d - .45) * .42, 0, .5)
            c = int(255 * int(v * 8) / 8)
            s.set_at((x, y), (c, c, c))
    return s


def draw_pagoda(s, x, y, col):
    for i in range(3):
        w = 14 - i * 3
        yy = y - i * 7
        s.fill(col, (x - w // 2, yy - 3, w, 2))
        s.fill(col, (x - w // 2 - 1, yy - 4, 1, 1))
        s.fill(col, (x + w // 2, yy - 4, 1, 1))
        s.fill(col, (x - w // 2 + 2, yy, w - 4, 4))
    s.fill(col, (x, y - 28, 1, 8))


def make_scenery(bi):
    """returns (far, mid) RGBA layers, 220px tall; ridge baseline near y=95."""
    B = BIOMES[bi]
    rng = random.Random(300 + bi)
    far = pygame.Surface((W, 220), pygame.SRCALPHA)
    mid = pygame.Surface((W, 220), pygame.SRCALPHA)

    def ridge(surf, base, amp, col, rim, sharp, snow=False, ph=None):
        ph = ph or [rng.uniform(0, 6.28) for _ in range(4)]
        for x in range(W):
            a = math.sin(x * .018 + ph[0]) * .55 + math.sin(x * .047 + ph[1]) * .3 + math.sin(x * .11 + ph[2]) * .15
            if sharp:
                a = (1 - abs(math.sin(x * .021 + ph[3]))) * .95 + a * .2 - .45
            y = int(base - a * amp)
            surf.fill(col, (x, y, 1, 220 - y))
            surf.set_at((x, y), rim)
            if snow and y < base - amp * .35:
                surf.fill((246, 250, 255), (x, y, 1, 2 + int((base - amp * .35 - y) / 8)))
        return ph

    if bi == 0:
        pygame.draw.circle(far, (255, 170, 110, 120), (232, 62), 30)
        pygame.draw.circle(far, (255, 206, 140), (232, 62), 22)
        pygame.draw.circle(far, (255, 232, 176), (232, 62), 16)
        ridge(far, 100, 50, lerp_c(B["sky_bot"], (96, 54, 120), .55), (255, 190, 150), True)
        ridge(mid, 118, 26, (66, 40, 88), (150, 96, 120), False)
        for x in (40, 118, 270):
            draw_pagoda(mid, x, 104, (54, 32, 76))
        for _ in range(40):
            x = rng.randrange(W)
            mid.fill((44, 28, 64), (x, 112 + rng.randrange(8), 1, 4 + rng.randrange(6)))
    elif bi == 1:
        ridge(far, 96, 44, (58, 74, 98), (96, 116, 144), True)
        ridge(mid, 116, 30, (38, 50, 70), (70, 88, 112), False)
        for x in (60, 210):
            draw_pagoda(mid, x, 106, (30, 40, 58))
    elif bi == 2:
        ridge(far, 100, 62, (150, 184, 216), (230, 244, 255), True, snow=True)
        ridge(mid, 120, 40, (118, 152, 188), (214, 236, 252), True, snow=True)
    else:
        pygame.draw.circle(far, (200, 190, 240, 70), (86, 52), 36)
        pygame.draw.circle(far, (238, 232, 255), (86, 52), 27)
        for (cx_, cy_, r) in ((78, 46, 5), (94, 58, 4), (88, 40, 3), (76, 60, 3)):
            pygame.draw.circle(far, (200, 194, 232), (cx_, cy_), r)
        ridge(far, 104, 54, (30, 22, 48), (110, 76, 170), True)
        ridge(mid, 122, 34, (16, 12, 28), (150, 100, 230), True)
        for x in range(20, W, 46):
            h_ = rng.randint(26, 54)
            pygame.draw.polygon(mid, (12, 8, 22), [(x - 6, 130), (x, 112 - h_), (x + 6, 130)])
            mid.set_at((x, 112 - h_), (210, 160, 255))
    return far, mid


def make_ground():
    s = pygame.Surface((W + 40, 70), pygame.SRCALPHA)
    rng = random.Random(5)
    s.fill((78, 58, 62))
    for y in range(4, 70, 6):
        for x in range(-(y // 6 % 2) * 8, W + 40, 16):
            c = rng.choice(((88, 66, 70), (70, 52, 58), (96, 74, 76)))
            s.fill(c, (x + 1, y, 14, 5))
    s.fill((86, 156, 70), (0, 0, W + 40, 4))
    s.fill((128, 200, 96), (0, 0, W + 40, 1))
    s.fill((60, 112, 56), (0, 3, W + 40, 1))
    for x in range(0, W + 40):
        if rng.random() < .5:
            s.fill((128, 200, 96), (x, -0, 1, 1))
    # stone path inside the tower
    s.fill((150, 138, 142), (TL - WT + 20, 4, TR - TL + 2 * WT, 3))
    s.fill((190, 178, 178), (TL - WT + 20, 4, TR - TL + 2 * WT, 1))
    return s


# ----------------------------------------------------------------------------
# game objects
# ----------------------------------------------------------------------------
class Solid:
    def __init__(self, x, y, w, h, kind="stone", oneway=False, grab=False, bi=0, seed=0, vis=True):
        self.rect = pygame.Rect(x, y, w, h)
        self.kind, self.oneway, self.grab, self.bi = kind, oneway, grab, bi
        self.dx = self.dy = 0
        self.ox, self.oy = x, y
        self.amp, self.speed, self.phase, self.axis = 0, 0.02, 0.0, 0
        self.state, self.timer = 0, 0
        self.surf = None
        if vis:
            style = kind if kind in ("ice", "crumble", "move") else "stone"
            self.surf = make_platform_surface(w, h, bi, style, seed)

    def update(self, g):
        if self.kind == "move":
            ox, oy = self.rect.x, self.rect.y
            off = math.sin(g.t * self.speed + self.phase) * self.amp
            if self.axis == 0:
                self.rect.x = int(round(self.ox + off))
            else:
                self.rect.y = int(round(self.oy + off))
            self.dx, self.dy = self.rect.x - ox, self.rect.y - oy
        elif self.kind == "crumble":
            if self.state == 1:
                self.timer -= 1
                if self.timer <= 0:
                    self.state, self.timer = 2, 210
                    g.crumble_fx(self)
            elif self.state == 2:
                self.timer -= 1
                if self.timer <= 0:
                    self.state = 0
                    g.pop_fx(self)


class Spike:
    def __init__(self, x, y, w):
        self.x, self.y, self.w = x, y, w
        self.hit = pygame.Rect(x + 1, y - 5, w - 2, 5)


class Saw:
    def __init__(self, x0, x1, y, speed, phase):
        self.x0, self.x1, self.y, self.speed, self.phase = x0, x1, y, speed, phase
        self.x, self.ang = float(x0), 0.0

    def update(self, t):
        k = (math.sin(t * self.speed + self.phase) + 1) / 2
        self.x = self.x0 + (self.x1 - self.x0) * k
        self.ang += .55


class Checkpoint:
    def __init__(self, x, y):
        self.x, self.y, self.on = x, y, False


def build_level(seed=7):
    rng = random.Random(seed)
    solids, spikes, saws, checks = [], [], [], []
    solids.append(Solid(TL - WT, -TOWER_H - 140, WT, TOWER_H + 200, "wall", vis=False))
    solids.append(Solid(TR, -TOWER_H - 140, WT, TOWER_H + 200, "wall", vis=False))
    solids.append(Solid(TL - WT, 0, TR - TL + 2 * WT, 60, "ground", vis=False))
    y = 0.0
    p0, p1 = 120, 200
    i = 0
    chim = [0.19, 0.41, 0.63, 0.83]
    ci = 0
    while -y < TOWER_H - 70:
        d = clamp(-y / TOWER_H, 0, 1)
        if ci < len(chim) and d >= chim[ci]:
            ci += 1
            y -= lerp(27, 50, d)
            bi = biome_at(y)
            x = int(clamp(rng.randint(p0 - 30, p1 + 30), TL + 36, TR - 36 - CHIM_GAP))
            HT = 170
            solids.append(Solid(x, int(y), CHIM_GAP, 9, "stone", oneway=True, bi=bi, seed=rng.randint(0, 9999)))
            solids.append(Solid(TL, int(y) - HT, x - TL, HT + 9, "block", grab=True, bi=bi, seed=rng.randint(0, 9999)))
            solids.append(Solid(x + CHIM_GAP, int(y) - HT, TR - x - CHIM_GAP, HT + 9, "block", grab=True, bi=bi,
                                seed=rng.randint(0, 9999)))
            yb = int(y) - HT
            solids.append(Solid(x, yb + 18, 14, 5, "stone", oneway=True, bi=bi, seed=rng.randint(0, 9999)))
            solids.append(Solid(x + CHIM_GAP - 14, yb + 18, 14, 5, "stone", oneway=True, bi=bi, seed=rng.randint(0, 9999)))
            if ci >= 2:
                saws.append(Saw(x + 15, x + CHIM_GAP - 15, int(y) - 70, .045, rng.uniform(0, 6)))
            if ci >= 3:
                saws.append(Saw(x + 15, x + CHIM_GAP - 15, int(y) - 120, .05, rng.uniform(0, 6)))
            checks.append(Checkpoint((TL + x) // 2, yb))
            y = yb
            p0, p1 = TL, TR
            i += 1
            continue
        y -= lerp(27, 50, d) + rng.uniform(-3, 3)
        bi = biome_at(y)
        w = int(lerp(76, 28, d) // 4 * 4) + rng.choice((0, 0, 4, 8))
        gap = rng.uniform(5, lerp(30, 74, d))
        dirn = rng.choice((-1, 1))
        if dirn > 0 and p1 + gap + w > TR - 4:
            dirn = -1
        if dirn < 0 and p0 - gap - w < TL + 4:
            dirn = 1
        x = p1 + gap if dirn > 0 else p0 - gap - w
        x = int(clamp(x, TL + 4, TR - 4 - w))
        kind = "stone"
        r = rng.random()
        if i > 4:
            if r < lerp(0.0, 0.26, d):
                kind = "crumble"
            elif d > 0.1 and r < lerp(0.0, 0.26, d) + lerp(0.04, 0.22, d):
                kind = "move"
        if kind == "stone" and bi >= 2 and rng.random() < (0.55 if bi == 2 else 0.3):
            kind = "ice"
        amp = 0
        if kind == "move":
            amp = min(rng.randint(22, 46), x - (TL + 3), TR - 3 - (x + w))
            if amp < 14:
                kind, amp = "stone", 0
        s = Solid(x, int(y), w, 9, kind, oneway=True, bi=bi, seed=rng.randint(0, 99999))
        if kind == "move":
            s.amp, s.speed, s.phase = amp, rng.uniform(.016, .028), rng.uniform(0, 6.28)
        solids.append(s)
        hazard = False
        if kind in ("stone", "ice") and w >= 36 and d > .1 and rng.random() < lerp(.05, .5, d):
            sw = rng.choice((8, 12, 16))
            if w - sw >= 24:
                if d > .55 and rng.random() < .4 and w - sw >= 28:
                    sx = x + (w - sw) // 2
                else:
                    sx = x + 3 if rng.random() < .5 else x + w - 3 - sw
                spikes.append(Spike(sx, int(y), sw))
                hazard = True
        if not hazard and kind in ("stone", "ice") and w >= 52 and d > .3 and rng.random() < lerp(.05, .35, d):
            saws.append(Saw(x + 8, x + w - 8, int(y) - 5, rng.uniform(.03, .055), rng.uniform(0, 6)))
            hazard = True
        if not hazard and kind in ("stone", "ice") and i % 9 == 0 and i > 0 and w >= 36:
            checks.append(Checkpoint(x + w // 2, int(y)))
        p0, p1 = x, x + w
        i += 1
    ys = -TOWER_H + 40
    summit = Solid(TL + 6, ys, TR - TL - 12, 12, "stone", oneway=True, bi=3, seed=1)
    solids.append(summit)
    return solids, spikes, saws, checks, summit


# ----------------------------------------------------------------------------
# player
# ----------------------------------------------------------------------------
class Player:
    def __init__(self, x, y):
        self.reset(x, y)

    def reset(self, x, y):
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.face = 1
        self.on_ground, self.ground = False, None
        self.coyote = self.jbuf = self.dbuf = 0
        self.air_jumps = 1
        self.dash_t = self.dash_cd = 0
        self.dash_ready = True
        self.dash_dir = 1
        self.cling = 0
        self.grip = GRIP_MAX
        self.no_grab = 0
        self.last_wall = 0
        self.exhausted = False
        self.anim = 0
        self.run_ph = 0.0
        self.spin = self.land_t = self.drop_t = 0
        self.cut_ok = False
        self.dead = False
        self.ghosts = []
        self.scarf = [[x - 3.0, y - 10.0 + i * .2] for i in range(8)]

    def rect(self):
        return pygame.Rect(int(self.x - 3), int(self.y - 12), 6, 12)

    def pose(self):
        if self.dash_t > 0:
            return "dash", 0
        if self.cling:
            return "cling", 0
        if self.spin > 0:
            return "spin", 0
        if not self.on_ground:
            return ("jump" if self.vy < 0 else "fall"), 0
        if self.land_t > 0:
            return "land", 0
        if abs(self.vx) > .35:
            return "run", int(self.run_ph) % 4
        return "idle", (self.anim // 26) % 2

    def wall_touch(self, near):
        for sd in near:
            if not sd.grab:
                continue
            r = sd.rect
            if self.y - 11 < r.bottom and self.y - 2 > r.top:
                if abs(r.right - (self.x - 3)) < 1.2:
                    return -1
                if abs(r.left - (self.x + 3)) < 1.2:
                    return 1
        return 0

    def update(self, g, ix, down, grab, jump_held):
        if self.on_ground and self.ground is not None:
            self.x += self.ground.dx
            self.y += self.ground.dy
        self.coyote = 6 if self.on_ground else max(0, self.coyote - 1)
        self.jbuf = max(0, self.jbuf - 1)
        self.dbuf = max(0, self.dbuf - 1)
        self.dash_cd = max(0, self.dash_cd - 1)
        self.no_grab = max(0, self.no_grab - 1)
        self.drop_t = max(0, self.drop_t - 1)
        self.land_t = max(0, self.land_t - 1)
        self.spin = max(0, self.spin - 1)
        self.anim += 1
        self.run_ph += abs(self.vx) * .13
        if self.on_ground and self.dash_t == 0:
            self.dash_ready = True
        touch = self.wall_touch(g.near)

        # ---- start a dash
        if self.dbuf and self.dash_ready and self.dash_cd == 0 and self.dash_t == 0:
            d = -self.cling if self.cling else (ix if ix else self.face)
            self.dash_dir = self.face = d
            self.dash_t, self.dash_cd, self.dash_ready = 9, 30, False
            self.cling, self.dbuf, self.no_grab = 0, 0, 4
            self.vx, self.vy = d * 4.8, 0.0
            g.sfx("dash")
            for _ in range(8):
                g.emit(self.x - d * 3, self.y - 6 + random.uniform(-4, 4), -d * random.uniform(.5, 1.6),
                       random.uniform(-.3, .3), 14, (150, 200, 255), 1, 0, .9)

        if self.dash_t > 0:
            self.dash_t -= 1
            self.vy, self.vx = 0.0, self.dash_dir * 4.8
            if self.dash_t % 2 == 0:
                self.ghosts.append([self.x, self.y, self.face, 12, "dash", 0])
            if random.random() < .6:
                g.emit(self.x - self.dash_dir * 4, self.y - random.uniform(2, 10), -self.dash_dir * .6, 0, 12,
                       (190, 225, 255), 1, 0, .92)
            if self.dash_t == 0:
                self.vx = self.dash_dir * 1.9
        else:
            want = (touch != 0 and not self.on_ground and self.no_grab == 0 and self.vy > -1.2
                    and (ix == touch or grab))
            if want and self.exhausted and touch == self.last_wall:
                want = False
            if want:
                if self.cling == 0:
                    if touch != self.last_wall:
                        self.grip, self.exhausted = GRIP_MAX, False
                    self.last_wall, self.cling, self.dash_ready = touch, touch, True
                    self.vy = min(self.vy, 1.2)
                    g.dust(self.x + touch * 3, self.y - 6, 4)
                self.face = touch
            else:
                self.cling = 0

            if self.cling:
                self.grip -= 1
                self.vx = 0.0
                self.vy = 0.28 + (1.0 - max(self.grip, 0) / GRIP_MAX) * 1.5
                if random.random() < .12 + (1 - self.grip / GRIP_MAX) * .35:
                    g.emit(self.x + self.cling * 3, self.y - 4, -self.cling * .2, .3, 14,
                           (255, 200, 120) if self.grip < 40 else (200, 200, 210), 1, .04)
                if self.jbuf:
                    self.vx, self.vy = -self.cling * 2.6, -5.4
                    self.face = -self.cling
                    self.air_jumps, self.dash_ready = 1, True
                    self.no_grab, self.jbuf, self.cut_ok = 9, 0, True
                    g.sfx("jump")
                    g.dust(self.x + self.cling * 3, self.y - 6, 6)
                    self.cling = 0
                elif self.grip <= 0:
                    self.cling, self.exhausted, self.no_grab = 0, True, 14
                    g.dust(self.x, self.y - 6, 8)
            if not self.cling:
                ice = self.on_ground and self.ground is not None and self.ground.kind == "ice"
                if ix:
                    self.face = ix
                    target = ix * 1.65
                    acc = (0.05 if ice else 0.22) if self.on_ground else 0.17
                    if self.vx * ix < 0 and not ice:
                        acc *= 2
                    if abs(self.vx) > 1.65 and self.vx * ix > 0:
                        self.vx -= math.copysign(0.02, self.vx)
                    else:
                        self.vx += clamp(target - self.vx, -acc, acc)
                else:
                    fr = (0.012 if ice else 0.30) if self.on_ground else 0.025
                    self.vx -= clamp(self.vx, -fr, fr)
                if not self.on_ground:
                    self.vx += g.wind * 0.02
                # jumping
                if self.jbuf:
                    if self.on_ground and down and self.ground is not None and self.ground.oneway:
                        self.drop_t, self.jbuf = 10, 0
                        self.on_ground, self.ground = False, None
                        self.y += 1
                    elif self.coyote > 0:
                        self.vy, self.coyote, self.jbuf, self.cut_ok = -5.7, 0, 0, True
                        self.air_jumps = 1
                        g.sfx("jump")
                        g.dust(self.x, self.y, 5)
                    elif self.air_jumps > 0:
                        self.vy, self.jbuf, self.cut_ok = -5.0, 0, True
                        self.air_jumps -= 1
                        self.spin = 22
                        g.sfx("djump")
                        g.ring(self.x, self.y - 4)
                if self.cut_ok and not jump_held and self.vy < -2.4:
                    self.vy *= .55
                    self.cut_ok = False
                self.vy = min(self.vy + GRAV, MAXFALL)
        self.move(g)
        self.update_scarf(g)

    def move(self, g):
        prev_y = self.y
        was_ground = self.on_ground
        # horizontal
        self.x += self.vx
        for sd in g.near:
            if sd.oneway or sd.state == 2:
                continue
            r = sd.rect
            if self.x + 3 > r.left and self.x - 3 < r.right and self.y > r.top and self.y - 12 < r.bottom:
                if self.vx > 0:
                    self.x = r.left - 3
                elif self.vx < 0:
                    self.x = r.right + 3
                else:
                    self.x = r.left - 3 if self.x < r.centerx else r.right + 3
                self.vx = 0.0
        # vertical
        self.y += self.vy
        land = None
        for sd in g.near:
            if sd.state == 2:
                continue
            r = sd.rect
            if self.x + 3 <= r.left or self.x - 3 >= r.right:
                continue
            if self.vy >= 0:
                if sd.oneway and self.drop_t:
                    continue
                if prev_y <= r.top + 1 and self.y >= r.top:
                    if land is None or r.top < land.rect.top:
                        land = sd
            elif not sd.oneway and prev_y - 12 >= r.bottom - 1 and self.y - 12 < r.bottom:
                self.y = r.bottom + 12
                self.vy = 0.0
        if land is not None:
            if not was_ground and self.vy > 2.5:
                g.dust(self.x, land.rect.top, 6)
                g.sfx("land", .6)
                self.land_t = 6
            self.y, self.vy = float(land.rect.top), 0.0
            self.on_ground, self.ground = True, land
            self.air_jumps, self.cling, self.spin = 1, 0, 0
            self.last_wall, self.grip, self.exhausted = 0, GRIP_MAX, False
        else:
            self.on_ground, self.ground = False, None

    def update_scarf(self, g):
        ax, ay = self.x - self.face * 3.0, self.y - 10.0
        if self.cling:
            ax, ay = self.x - self.cling * 3.0, self.y - 10.0
        self.scarf[0][0], self.scarf[0][1] = ax, ay
        for i in range(1, len(self.scarf)):
            px, py = self.scarf[i - 1]
            q = self.scarf[i]
            q[0] += -self.vx * .10 + g.wind * .05 - self.face * .07
            q[1] += .10 - self.vy * .05
            dx, dy = q[0] - px, q[1] - py
            d = math.hypot(dx, dy) or 1.0
            q[0], q[1] = px + dx / d * 1.9, py + dy / d * 1.9


# ----------------------------------------------------------------------------
# art cache
# ----------------------------------------------------------------------------
class Art:
    def __init__(self):
        self.ninja = {}
        self.ghost_cache = {}
        self.light_cache = {}
        self.back = [make_back_tile(i) for i in range(4)]
        self.wall = [make_wall_tile(i) for i in range(4)]
        self.sky = [make_sky(i) for i in range(4)]
        self.scen = [make_scenery(i) for i in range(4)]
        self.vig = make_vignette()
        self.ground = make_ground()

    def ninja_surf(self, pose, f, flip=False):
        name = pose + str(f) if pose in ("idle", "run") else pose
        k = (name, flip)
        s = self.ninja.get(k)
        if s is None:
            s = build_ninja(name)
            if flip:
                s = pygame.transform.flip(s, True, False)
            self.ninja[k] = s
        return s

    def light(self, r, col):
        col = (col[0] // 8 * 8, col[1] // 8 * 8, col[2] // 8 * 8)
        k = (r, col)
        s = self.light_cache.get(k)
        if s is None:
            s = pygame.Surface((r * 2, r * 2))
            bands = 7
            for i in range(bands):
                rr = max(1, int(r * (1 - i / bands)))
                kf = ((i + 1) / bands) ** 1.7
                pygame.draw.circle(s, (int(col[0] * kf), int(col[1] * kf), int(col[2] * kf)), (r, r), rr)
            self.light_cache[k] = s
        return s


# ----------------------------------------------------------------------------
# the game
# ----------------------------------------------------------------------------
JUMP_KEYS = (pygame.K_SPACE, pygame.K_UP, pygame.K_w, pygame.K_z, pygame.K_k)
DASH_KEYS = (pygame.K_x, pygame.K_l, pygame.K_LSHIFT, pygame.K_RSHIFT)


class Game:
    def __init__(self, art=None, snd=None):
        self.art = art or Art()
        self.snd = snd or Sound()
        self.lightmap = pygame.Surface((W, H))
        self.solids, self.spikes, self.saws, self.checks, self.summit = build_level()
        rng = random.Random(11)
        self.clouds = [(-rng.uniform(0, TOWER_H), rng.uniform(0, W + 120), rng.uniform(.04, .16), rng.uniform(.8, 1.8))
                       for _ in range(80)]
        self.stars = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0, 6.28)) for _ in range(90)]
        self.state = "title"
        self.best_h = 0
        self.new_game()

    # ---- state ---------------------------------------------------------
    def new_game(self):
        for s in self.solids:
            s.state = 0
        for c in self.checks:
            c.on = False
        self.cp = (160, 0)
        self.p = Player(160, 0)
        self.t = 0
        self.cam = -156.0
        self.parts, self.rain_d, self.snow_f, self.strikes = [], [], [], []
        self.deaths, self.time_f, self.dead_t = 0, 0, 0
        self.shake = 0.0
        self.flash, self.flash_echo = 0.0, 0
        self.bolt = None
        self.thunder_cd = 300
        self.strike_cd = 200
        self.wind = 0.0
        self.rain = self.snow = self.windk = self.thunder = 0.0
        self.bw = [1, 0, 0, 0]
        self.tt = (0, 0, 0)
        self.cur_biome = 0
        self.banner_t, self.banner_name = 0, ""
        self.red_t = 0
        self.msg_t, self.msg = 0, ""
        self.near = []
        self.cx = self.cy = 0
        self.L, self.G = [], []
        self.paused = False
        self.win_time = 0
        self.update_weather()

    # ---- effects -------------------------------------------------------
    def sfx(self, n, v=1.0):
        self.snd.play(n, v)

    def emit(self, x, y, vx, vy, life, col, size=1, grav=0.0, drag=.98):
        if len(self.parts) < 900:
            self.parts.append([x, y, vx, vy, life, life, col, size, grav, drag])

    def dust(self, x, y, n):
        for _ in range(n):
            self.emit(x + random.uniform(-3, 3), y - 1, random.uniform(-.8, .8), random.uniform(-.7, -.1), 16,
                      lerp_c((200, 200, 210), BIOMES[self.cur_biome]["light"], .4), 1, .02, .93)

    def ring(self, x, y):
        for i in range(14):
            a = i / 14 * 6.283
            self.emit(x, y, math.cos(a) * 1.5, math.sin(a) * .8, 12, (180, 225, 255), 1, 0, .9)

    def crumble_fx(self, s):
        self.sfx("crumble", .6)
        self.shake = max(self.shake, 1.5)
        c = BIOMES[s.bi]["stone"]
        for _ in range(18):
            self.emit(s.rect.x + random.uniform(0, s.rect.w), s.rect.y + 4, random.uniform(-.6, .6), random.uniform(0, 1),
                      40, lerp_c(c, (0, 0, 0), random.uniform(0, .4)), random.choice((1, 2)), .25, .99)

    def pop_fx(self, s):
        for _ in range(8):
            self.emit(s.rect.x + random.uniform(0, s.rect.w), s.rect.y, 0, random.uniform(-.6, -.1), 18,
                      (220, 210, 190), 1, .02)

    def kill(self):
        p = self.p
        if p.dead:
            return
        p.dead = True
        self.deaths += 1
        self.dead_t, self.red_t = 50, 12
        self.shake = max(self.shake, 3.5)
        self.sfx("death")
        for _ in range(40):
            a = random.uniform(0, 6.283)
            sp = random.uniform(.5, 2.8)
            self.emit(p.x, p.y - 7, math.cos(a) * sp, math.sin(a) * sp - 1, random.randint(25, 50),
                      random.choice((RED, HOOD_HI, CLOTH_HI, (255, 255, 255), RED_DK)), random.choice((1, 1, 2)), .1)

    def respawn(self, silent=False):
        x, y = self.cp
        self.p.reset(x, y)
        self.cam = clamp(y - 112, -(TOWER_H + 60), -(H - 26))
        for _ in range(26):
            a = random.uniform(0, 6.283)
            self.emit(x + math.cos(a) * 5, y - 7 + math.sin(a) * 6, math.cos(a) * .5, math.sin(a) * .5, 24,
                      (150, 170, 220), 1, 0, .95)
        if silent:
            self.say("THE SHADOWS CARRY YOU BACK")

    def say(self, s):
        self.msg, self.msg_t = s, 130

    # ---- input ---------------------------------------------------------
    def read_input(self):
        k = pygame.key.get_pressed()
        ix = int(bool(k[pygame.K_RIGHT] or k[pygame.K_d])) - int(bool(k[pygame.K_LEFT] or k[pygame.K_a]))
        down = bool(k[pygame.K_DOWN] or k[pygame.K_s])
        grab = bool(k[pygame.K_c] or k[pygame.K_j] or k[pygame.K_LCTRL])
        jh = any(k[c] for c in JUMP_KEYS)
        return ix, down, grab, jh

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            if self.state == "title":
                if e.key != pygame.K_ESCAPE:
                    self.state = "play"
                return
            if e.key in (pygame.K_p, pygame.K_ESCAPE) and self.state == "play":
                self.paused = not self.paused
            elif e.key == pygame.K_r:
                self.new_game()
                self.state = "play"
            elif e.key == pygame.K_q and self.paused:
                pygame.quit()
                sys.exit()
            elif self.state == "play" and not self.paused:
                if e.key in JUMP_KEYS:
                    self.p.jbuf = 8
                if e.key in DASH_KEYS:
                    self.p.dbuf = 7

    # ---- update --------------------------------------------------------
    def update(self, inp=None):
        if self.paused:
            return
        self.t += 1
        p = self.p
        for s in self.solids:
            if s.kind in ("move", "crumble"):
                s.update(self)
        for sw in self.saws:
            sw.update(self.t)
        self.near = [s for s in self.solids if s.rect.bottom > p.y - 90 and s.rect.top < p.y + 90 and s.state != 2]
        if self.state == "play":
            self.time_f += 1
            if p.dead:
                self.dead_t -= 1
                if self.dead_t <= 0:
                    self.respawn()
            else:
                ix, down, grab, jh = inp if inp else self.read_input()
                p.update(self, ix, down, grab, jh)
                self.check_world()
        elif self.state == "title":
            p.update(self, 0, False, False, False)
        else:
            p.update(self, 0, False, False, False)
        # camera
        tgt = p.y - 112 + (18 if p.vy > 3.5 else 0)
        self.cam += (tgt - self.cam) * .1
        self.cam = clamp(self.cam, -(TOWER_H + 60), -(H - 26))
        self.update_weather()
        self.update_fx()

    def check_world(self):
        p = self.p
        # crumbling
        if p.on_ground and p.ground is not None and p.ground.kind == "crumble" and p.ground.state == 0:
            p.ground.state, p.ground.timer = 1, 26
            self.shake = max(self.shake, 1.0)
        # hazards
        r = p.rect()
        for sp in self.spikes:
            if abs(sp.y - p.y) < 40 and r.colliderect(sp.hit):
                self.kill()
                return
        for sw in self.saws:
            if abs(sw.y - p.y) < 40:
                cx_ = clamp(sw.x, r.left, r.right)
                cy_ = clamp(sw.y, r.top, r.bottom)
                if (cx_ - sw.x) ** 2 + (cy_ - sw.y) ** 2 < 5.2 ** 2:
                    self.kill()
                    return
        for st in self.strikes:
            if st["t"] <= 0 and st["life"] > 0 and abs(p.x - st["x"]) < 5:
                self.kill()
                return
        # checkpoints
        for c in self.checks:
            if not c.on and abs(c.x - p.x) < 14 and abs(c.y - p.y) < 16:
                c.on = True
                self.cp = (c.x, c.y)
                self.sfx("check")
                self.say("CHECKPOINT")
                for _ in range(20):
                    self.emit(c.x, c.y - 12, random.uniform(-1, 1), random.uniform(-1.6, -.2), 30,
                              random.choice(((255, 220, 120), (255, 255, 200))), 1, .03)
        # fell too far
        if p.y > self.cp[1] + 330 and self.cp[1] < -60:
            self.respawn(silent=True)
        # win
        if p.on_ground and p.ground is self.summit and self.state == "play":
            self.state = "win"
            self.win_time = self.time_f
        self.best_h = max(self.best_h, int(-p.y / 8))

    def update_weather(self):
        p = self.p
        pp = clamp(-p.y / TOWER_H, 0, 1) * 4
        self.tt = biome_t(pp)
        self.bw = biome_weights(self.tt)
        self.rain = bmix(self.bw, "rain")
        self.snow = bmix(self.bw, "snow")
        self.windk = bmix(self.bw, "wind")
        self.thunder = bmix(self.bw, "thunder")
        gust = math.sin(self.t * .007) * .7 + math.sin(self.t * .019 + 1.3) * .5
        self.wind = gust * self.windk
        self.snd.set_rain(self.rain)
        bi = biome_at(p.y)
        if bi != self.cur_biome:
            self.cur_biome = bi
            self.banner_t, self.banner_name = 200, BIOMES[bi]["name"]
        # spawn rain / snow in screen space
        n = self.rain * 5.5
        for _ in range(int(n) + (1 if random.random() < n % 1 else 0)):
            layer = random.random() < .35
            self.rain_d.append([random.uniform(-50, W + 50), -6.0, .8 + self.wind * 1.7 + (.4 if layer else 0),
                                (8.5 if layer else 5.5) + random.uniform(-.5, .5), layer])
        n = self.snow * 1.1
        for _ in range(int(n) + (1 if random.random() < n % 1 else 0)):
            layer = random.random() < .3
            self.snow_f.append([random.uniform(-40, W + 40), -4.0, (.7 if layer else .4) + random.uniform(0, .25),
                                random.uniform(0, 6.28), layer])
        for d in self.rain_d:
            d[0] += d[2]
            d[1] += d[3]
        self.rain_d = [d for d in self.rain_d if d[1] < H + 4 and -60 < d[0] < W + 60]
        for f in self.snow_f:
            f[3] += .04
            f[0] += math.sin(f[3]) * .35 + self.wind * (1.3 if f[4] else .8) + .15
            f[1] += f[2]
        self.snow_f = [f for f in self.snow_f if f[1] < H + 4]
        # rain rumble & thunder
        if self.rain > .05 and random.random() < self.rain * .035:
            self.shake = max(self.shake, 1.1 + self.rain * .6)
        if self.rain > .6 and random.random() < .02:
            self.shake = max(self.shake, .8)
        self.thunder_cd -= 1 if self.thunder > .25 else 0
        if self.thunder_cd <= 0 and self.thunder > .25:
            self.flash, self.flash_echo = 1.0, 14
            self.shake = max(self.shake, 3 + 4 * self.thunder)
            self.snd.play("thunder", .5 + .4 * self.thunder)
            x0 = random.uniform(30, W - 30)
            pts = [(x0, -10)]
            y_ = -10
            while y_ < random.uniform(80, 150):
                y_ += random.uniform(8, 16)
                pts.append((pts[-1][0] + random.uniform(-12, 12), y_))
            self.bolt = [pts, 9]
            self.thunder_cd = int(random.uniform(260, 620) / self.thunder)
        # lightning strikes (storm crown only)
        self.strike_cd -= 1 if self.bw[3] > .6 and self.state == "play" else 0
        if self.strike_cd <= 0 and self.bw[3] > .6:
            self.strikes.append(dict(x=clamp(p.x + random.uniform(-45, 45), TL + 6, TR - 6), t=58, life=11))
            self.strike_cd = random.randint(170, 320)
        for st in self.strikes:
            if st["t"] > 0:
                st["t"] -= 1
                if st["t"] == 0:
                    self.flash, self.flash_echo = 1.0, 0
                    self.shake = max(self.shake, 4.5)
                    self.sfx("zap", .8)
            else:
                st["life"] -= 1
        self.strikes = [s for s in self.strikes if s["life"] > 0]
        if self.flash_echo > 0:
            self.flash_echo -= 1
            if self.flash_echo == 0:
                self.flash = .7
        self.flash = max(0.0, self.flash - .07)
        if self.bolt:
            self.bolt[1] -= 1
            if self.bolt[1] <= 0:
                self.bolt = None
        if self.banner_t > 0:
            self.banner_t -= 1
        if self.msg_t > 0:
            self.msg_t -= 1
        if self.red_t > 0:
            self.red_t -= 1

    def update_fx(self):
        p = self.p
        for q in self.parts:
            q[0] += q[2]
            q[1] += q[3]
            q[3] += q[8]
            q[2] *= q[9]
            q[4] -= 1
        self.parts = [q for q in self.parts if q[4] > 0]
        for gh in p.ghosts:
            gh[3] -= 1
        p.ghosts = [gh for gh in p.ghosts if gh[3] > 0]
        # rain splashes on platform tops / player
        if self.rain > .1:
            cam = self.cam
            for s in self.solids:
                if s.surf is None or s.state == 2:
                    continue
                if cam - 10 < s.rect.y < cam + H + 10 and random.random() < self.rain * .05:
                    self.emit(s.rect.x + random.uniform(0, s.rect.w), s.rect.y - 1, random.uniform(-.4, .4),
                              -random.uniform(.5, 1.2), 14, (170, 205, 245), 1, .1)
            if cam + H > -4 and random.random() < self.rain * .6:
                self.emit(random.uniform(TL - 30, TR + 30), -1, random.uniform(-.4, .4), -random.uniform(.5, 1.1), 12,
                          (170, 205, 245), 1, .1)
            if not p.dead and random.random() < self.rain * .15:
                self.emit(p.x + random.uniform(-3, 3), p.y - 12, random.uniform(-.3, .3), -random.uniform(.2, .8), 12,
                          (190, 220, 255), 1, .08)
        if self.snow > .3 and not p.dead and random.random() < .05 and p.on_ground and abs(p.vx) < .5:
            self.emit(p.x + p.face * 3, p.y - 11, p.face * .2, -.15, 22, (235, 245, 255), 1, 0, .97)
        # embers + summit magic
        if self.state in ("play", "win") and p.y < -TOWER_H + 400 and random.random() < .5:
            self.emit(random.uniform(TL + 10, TR - 10), -TOWER_H + 36, random.uniform(-.2, .2), -random.uniform(.3, 1), 50,
                      (255, 226, 140), 1, -.002)

    # ---- drawing helpers ----------------------------------------------
    def add_light(self, x, y, r, col, glow=0.0):
        self.L.append((int(x), int(y), r, icol(col)))
        if glow:
            self.G.append((int(x), int(y), max(4, r // 4), icol(scale_c(col, glow))))

    def draw_sky(self, cv):
        art = self.art
        cv.blit(art.sky[0], (0, 0))
        for k in (1, 2, 3):
            t = self.tt[k - 1]
            if t > .004:
                art.sky[k].set_alpha(int(t * 255))
                cv.blit(art.sky[k], (0, 0))
        w3 = self.bw[3]
        if w3 > .02 or self.bw[1] > .3:
            cam_c = self.cy + H / 2
            for (sx, sy, ph) in self.stars:
                y = (sy + (-cam_c) * .02) % H
                b = (.55 + .45 * math.sin(self.t * .05 + ph)) * w3
                if y < H * .8 and b > .1:
                    v = int(200 * b)
                    cv.fill((v, v, int(v * 1.1)), (int(sx), int(y), 1, 1), special_flags=pygame.BLEND_RGB_ADD)
        cam_c = self.cy + H / 2
        for k in range(4):
            wt = self.bw[k]
            if wt < .02:
                continue
            anchor = -k * TOWER_H / 4
            for surf, f in zip(art.scen[k], (.06, .14)):
                top = int(125 + (anchor - cam_c) * f) - 100
                if -220 < top < H:
                    surf.set_alpha(int(wt * 255))
                    cv.blit(surf, (0, top))
        # clouds
        col = icol(bmix(self.bw, "cloud"))
        sh = scale_c(col, .78)
        for (wy, xb, sp, sc) in self.clouds:
            sy = H / 2 + (wy - cam_c) * .35
            if -20 < sy < H + 10:
                x = int((xb + self.t * sp) % (W + 120) - 60)
                y = int(sy)
                r = int(5 * sc)
                pygame.draw.rect(cv, sh, (x - 2 * r, y, 4 * r, r // 2 + 2))
                pygame.draw.circle(cv, col, (x - r, y), r)
                pygame.draw.circle(cv, col, (x + r, y), r)
                pygame.draw.circle(cv, col, (x, y - r // 2), r + 1)
                cv.fill(sh, (x - 2 * r + 1, y + r // 2, 4 * r - 2, 2))

    def flame_col(self, bi):
        return BIOMES[bi]["flame"]

    def draw_torch(self, cv, x, y, bi, seed):
        fc = self.flame_col(bi)
        pygame.draw.rect(cv, (50, 44, 56), (x - 1, y, 3, 3))
        pygame.draw.rect(cv, (88, 78, 92), (x - 3, y - 3, 7, 3))
        pygame.draw.rect(cv, (30, 26, 36), (x - 3, y - 1, 7, 1))
        f = (self.t // 4 + seed) % 3
        h = 4 + (f == 1) * 1 + (bi == 1)
        pygame.draw.rect(cv, fc, (x - 2, y - 3 - h + 1, 5, h))
        pygame.draw.rect(cv, lerp_c(fc, (255, 255, 255), .7), (x - 1, y - 3 - h + 3, 3, h - 2))
        cv.set_at((x + (f - 1), y - 4 - h), fc)
        if random.random() < .06:
            self.emit(x + self.cx, y - 8 + self.cy, random.uniform(-.2, .2), -random.uniform(.3, .7), 36, fc, 1, -.004)
        flick = .85 + .15 * math.sin(self.t * .3 + seed) + random.uniform(-.05, .05)
        self.add_light(x, y - 6, 46, scale_c(fc, .95 * flick), .35)

    def draw_window(self, cv, x, y, bi):
        B = BIOMES[bi]
        fr = scale_c(B["light"], .6)
        gl = lerp_c(B["flame"], (255, 255, 255), .25) if bi != 2 else (200, 230, 255)
        if bi == 3:
            gl = (170, 120, 255)
        pygame.draw.rect(cv, fr, (x - 7, y - 4, 14, 25))
        pygame.draw.circle(cv, fr, (x, y - 4), 7)
        pygame.draw.rect(cv, gl, (x - 5, y - 3, 10, 22))
        pygame.draw.circle(cv, gl, (x, y - 3), 5)
        pygame.draw.line(cv, fr, (x, y - 8), (x, y + 19))
        pygame.draw.line(cv, fr, (x - 5, y + 6), (x + 4, y + 6))
        self.add_light(x, y + 6, 44, scale_c(gl, .55), .0)

    def draw_world(self, cv):
        art, cx, cy = self.art, self.cx, self.cy
        self.L, self.G = [], []
        # ---- tower interior & walls
        cv.set_clip(pygame.Rect(TL - cx, 0, TR - TL, H))
        y0 = (cy // 32) * 32
        for ty in range(y0, cy + H + 32, 32):
            tile = art.back[biome_at(ty)]
            for tx in range(TL, TR, 32):
                cv.blit(tile, (tx - cx, ty - cy))
        # windows
        k0 = int((-(cy + H)) // 176) - 1
        for k in range(max(0, k0), max(0, k0) + 6):
            wy = -(k * 176) - 96
            if cy - 30 < wy < cy + H + 10:
                self.draw_window(cv, 160 + (48 if k % 2 else -48) - cx, wy - cy, biome_at(wy))
        # entrance door
        if cy + H > -60:
            dx, dy = 140 - cx, -40 - cy
            pygame.draw.rect(cv, (70, 58, 70), (dx - 2, dy - 2, 44, 42))
            pygame.draw.rect(cv, (16, 12, 22), (dx, dy, 40, 40))
            pygame.draw.circle(cv, (16, 12, 22), (dx + 20, dy), 20)
            pygame.draw.circle(cv, (70, 58, 70), (dx + 20, dy), 21, 2)
            pygame.draw.rect(cv, (255, 176, 90), (dx + 6, dy + 8, 2, 32))
            self.add_light(dx + 20, dy + 20, 40, (150, 100, 50), 0)
        cv.set_clip(None)
        for side in (0, 1):
            wx = TL - WT if side == 0 else TR
            cv.set_clip(pygame.Rect(wx - cx, 0, WT, H))
            for ty in range(y0, cy + H + 32, 32):
                cv.blit(art.wall[biome_at(ty)], (wx - cx, ty - cy))
            cv.set_clip(None)
        # inner shadow edges on walls
        cv.fill((34, 34, 34), (TL - cx, 0, 2, H), special_flags=pygame.BLEND_RGB_SUB)
        cv.fill((34, 34, 34), (TR - 2 - cx, 0, 2, H), special_flags=pygame.BLEND_RGB_SUB)
        # torches
        for k in range(max(0, int(-(cy + H) // 72) - 1), max(0, int(-(cy + H) // 72)) + 5):
            ty = -(k * 72) - 30
            if cy - 14 < ty < cy + H + 14:
                if k % 2 == 0:
                    self.draw_torch(cv, TL + 2 - cx, ty - cy, biome_at(ty), k)
                else:
                    self.draw_torch(cv, TR - 3 - cx, ty - cy, biome_at(ty), k)
        # ground
        if cy + H > -4:
            cv.blit(art.ground, (-20 - cx, -cy))
            for lx in (TL - 34, TR + 34):
                sx, sy = lx - cx, -cy
                pygame.draw.rect(cv, (110, 100, 110), (sx - 3, sy - 12, 6, 12))
                pygame.draw.rect(cv, (140, 130, 140), (sx - 5, sy - 15, 10, 3))
                pygame.draw.rect(cv, (255, 190, 100), (sx - 2, sy - 10, 4, 5))
                pygame.draw.rect(cv, (110, 100, 110), (sx - 4, sy - 18, 8, 3))
                self.add_light(sx, sy - 8, 44, (255, 170, 90), .3)
        # ---- platforms
        self.vis = []
        for s in self.solids:
            if s.surf is None or s.state == 2:
                continue
            r = s.rect
            if r.bottom + 14 < cy or r.top - 6 > cy + H:
                continue
            ox = (random.choice((-1, 1)) if s.state == 1 and self.t % 2 else 0)
            if s.kind == "move":
                for xx in range(int(s.ox - s.amp), int(s.ox + s.amp + r.w), 4):
                    cv.fill(scale_c(BIOMES[s.bi]["dark"], .8), (xx - cx, r.y + 4 - cy, 1, 1))
            cv.blit(s.surf, (r.x + ox - cx, r.y - 5 - cy))
            self.vis.append(s)
            if s.bi == 3 and s.kind != "block":
                self.add_light(r.centerx - cx, r.y - cy + 3, 22, (80, 40, 150), 0)
        # ---- hazards
        for sp in self.spikes:
            if cy - 10 < sp.y < cy + H + 10:
                for xx in range(sp.x, sp.x + sp.w, 4):
                    pts = [(xx - cx, sp.y - cy), (xx + 2 - cx, sp.y - 6 - cy), (xx + 4 - cx, sp.y - cy)]
                    pygame.draw.polygon(cv, (150, 160, 184), pts)
                    pygame.draw.line(cv, (232, 238, 252), (xx + 2 - cx, sp.y - 6 - cy), (xx + 1 - cx, sp.y - 2 - cy))
                    cv.set_at((xx + 2 - cx, sp.y - 6 - cy), (255, 120, 120))
                cv.fill((66, 72, 94), (sp.x - cx, sp.y - 1 - cy, sp.w, 1))
        for sw in self.saws:
            if cy - 12 < sw.y < cy + H + 12:
                self.draw_saw(cv, sw.x - cx, sw.y - cy, sw.ang)
        for c in self.checks:
            if cy - 20 < c.y < cy + H + 20:
                self.draw_checkpoint(cv, c)
        self.draw_summit(cv)
        # hint text at the start
        if cy < -40 and cy > -330 and self.state != "title":
            pass
        # ---- strikes (telegraph + bolt)
        for st in self.strikes:
            x = int(st["x"] - cx)
            if st["t"] > 0:
                if (self.t // 3) % 2 == 0 or st["t"] < 14:
                    for yy in range(0, H, 6):
                        cv.fill((190, 130, 255), (x, yy, 1, 3))
                    cv.fill((255, 220, 255), (x - 1, 2, 3, 4))
                    cv.fill((50, 20, 90), (x, 3, 1, 2))
            else:
                self.draw_bolt_line(cv, x, 0, H)
        # ---- background lightning
        if self.bolt:
            pts = [(int(a), int(b)) for a, b in self.bolt[0]]
            pygame.draw.lines(cv, (170, 150, 255), False, pts, 3)
            pygame.draw.lines(cv, (255, 255, 255), False, pts, 1)

    def draw_bolt_line(self, cv, x, y0, y1):
        pts = [(x, y0)]
        yy = y0
        rng = random.Random(self.t // 2)
        while yy < y1:
            yy += rng.randint(8, 14)
            pts.append((x + rng.randint(-4, 4), yy))
        pygame.draw.lines(cv, (150, 110, 255), False, pts, 5)
        pygame.draw.lines(cv, (255, 255, 255), False, pts, 2)

    def draw_saw(self, cv, x, y, ang):
        x, y = int(x), int(y)
        pts = []
        for i in range(16):
            a = ang + i * math.pi / 8
            r = 6.2 if i % 2 == 0 else 4.2
            pts.append((x + math.cos(a) * r, y + math.sin(a) * r))
        pygame.draw.polygon(cv, (170, 178, 196), pts)
        pygame.draw.circle(cv, (110, 118, 140), (x, y), 3)
        pygame.draw.circle(cv, (210, 60, 70), (x, y), 1)
        pygame.draw.polygon(cv, (230, 236, 250), pts, 1)
        if random.random() < .08:
            self.emit(x + self.cx, y + self.cy + 4, random.uniform(-1, 1), -random.uniform(.5, 1.2), 12, (255, 210, 120), 1, .1)

    def draw_checkpoint(self, cv, c):
        x, y = int(c.x - self.cx), int(c.y - self.cy)
        pygame.draw.rect(cv, (92, 70, 58), (x - 1, y - 16, 2, 16))
        pygame.draw.rect(cv, (92, 70, 58), (x - 4, y - 18, 8, 2))
        col = (255, 196, 96) if c.on else (110, 110, 126)
        pygame.draw.rect(cv, (60, 50, 50), (x - 3, y - 17, 6, 8))
        pygame.draw.rect(cv, col, (x - 2, y - 16, 4, 6))
        if c.on:
            cv.set_at((x, y - 14), (255, 255, 230))
            self.add_light(x, y - 13, 42, (255, 190, 100), .5)
        else:
            self.add_light(x, y - 13, 14, (50, 50, 60), 0)

    def draw_summit(self, cv):
        cy, cx = self.cy, self.cx
        ys = -TOWER_H + 40
        if not (cy - 60 < ys < cy + H + 60):
            return
        x, y = 160 - cx, ys - cy
        red, dk = (220, 60, 56), (140, 30, 40)
        pygame.draw.rect(cv, red, (x - 26, y - 44, 4, 44))
        pygame.draw.rect(cv, red, (x + 22, y - 44, 4, 44))
        pygame.draw.rect(cv, dk, (x - 26, y - 44, 1, 44))
        pygame.draw.rect(cv, dk, (x + 22, y - 44, 1, 44))
        pygame.draw.rect(cv, red, (x - 32, y - 52, 64, 4))
        pygame.draw.rect(cv, (40, 30, 40), (x - 34, y - 56, 68, 3))
        pygame.draw.rect(cv, red, (x - 28, y - 42, 56, 3))
        pulse = .7 + .3 * math.sin(self.t * .06)
        pygame.draw.ellipse(cv, lerp_c((255, 220, 140), (255, 255, 255), pulse * .5), (x - 14, y - 40, 28, 36))
        pygame.draw.ellipse(cv, (255, 246, 210), (x - 8, y - 34, 16, 24))
        self.add_light(x, y - 24, 70, (255, 210, 130), .5)
        text(cv, "SUMMIT", x, y - 70, (255, 230, 150), 1, center=True)

    # ---- player draw ---------------------------------------------------
    def draw_player(self, cv):
        p, art = self.p, self.art
        cx, cy = self.cx, self.cy
        # ghosts
        for gx, gy, face, life, pose, f in p.ghosts:
            spr = art.ninja_surf("dash", 0, face < 0)
            spr = pygame.transform.rotate(spr, -62 if face > 0 else 62)
            m = pygame.mask.from_surface(spr).to_surface(setcolor=(90, 170, 255, int(120 * life / 12)),
                                                         unsetcolor=(0, 0, 0, 0))
            cv.blit(m, m.get_rect(center=(int(gx) - cx, int(gy) - 8 - cy)))
        pose, f = p.pose()
        flip = p.face < 0
        spr = art.ninja_surf(pose, f, flip)
        ang = 0
        if pose == "dash":
            ang = -62
        elif pose == "spin":
            ang = -(1 - p.spin / 22) * 360
        if ang:
            spr = pygame.transform.rotate(spr, -ang if flip else ang)
        # scarf
        for i, (sx, sy) in enumerate(p.scarf):
            c = RED if i % 2 == 0 else RED_DK
            sz = 2 if i < 5 else 1
            cv.fill(c, (int(round(sx)) - cx, int(round(sy)) - cy, sz, sz))
        r = spr.get_rect(center=(int(p.x) - cx, int(p.y) - 8 - cy))
        cv.blit(spr, r)
        # grip meter
        if p.cling:
            k = max(0, p.grip) / GRIP_MAX
            bx = int(p.x) - cx - 6
            by = int(p.y) - cy - 20
            cv.fill((10, 10, 20), (bx - 1, by - 1, 14, 4))
            col = (120, 230, 140) if k > .5 else ((255, 210, 90) if k > .25 else (255, 80, 80))
            if k < .25 and (self.t // 4) % 2:
                col = (255, 255, 255)
            cv.fill(col, (bx, by, max(1, int(12 * k)), 2))
        self.add_light(p.x - cx, p.y - 7 - cy, 40, (96, 130, 180), .0)

    def draw_particles(self, cv):
        cx, cy = self.cx, self.cy
        for q in self.parts:
            x, y = int(q[0]) - cx, int(q[1]) - cy
            if 0 <= x < W and 0 <= y < H:
                if q[4] < q[5] * .3 and (q[4] & 1):
                    continue
                cv.fill(q[6], (x, y, q[7], q[7]))

    # ---- lighting ------------------------------------------------------
    def apply_lighting(self, cv):
        art = self.art
        lm = self.lightmap
        lm.fill(icol(bmix(self.bw, "amb")))
        for (x, y, r, col) in self.L:
            if -r < x < W + r and -r < y < H + r:
                lm.blit(art.light(r, col), (x - r, y - r), special_flags=pygame.BLEND_RGB_ADD)
        if self.flash > 0:
            v = int(150 * self.flash)
            lm.fill((v, v, v + 20), special_flags=pygame.BLEND_RGB_ADD)
        for st in self.strikes:
            if st["t"] <= 0:
                x = int(st["x"] - self.cx)
                lm.blit(art.light(70, (200, 170, 255)), (x - 70, int(self.p.y - self.cy) - 70), special_flags=pygame.BLEND_RGB_ADD)
        cv.blit(lm, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        for (x, y, r, col) in self.G:
            if -r < x < W + r and -r < y < H + r:
                cv.blit(art.light(r, col), (x - r, y - r), special_flags=pygame.BLEND_RGB_ADD)
        # rim light on platform tops keeps dark biomes readable
        amb = bmix(self.bw, "amb")
        dark = 1.25 - sum(amb) / 765
        for s in self.vis:
            B = BIOMES[s.bi]
            c = scale_c(B["top2"], .2 * dark)
            cv.fill(c, (s.rect.x - self.cx, s.rect.y - self.cy, s.rect.w, 1), special_flags=pygame.BLEND_RGB_ADD)
        if self.flash > 0:
            v = int(50 * self.flash)
            cv.fill((v, v, v), special_flags=pygame.BLEND_RGB_ADD)

    def draw_weather(self, cv):
        br = clamp(sum(bmix(self.bw, "amb")) / 765 + self.flash * .6, .35, 1.1)
        far_c = icol((120 * br, 145 * br, 190 * br))
        near_c = icol((180 * br, 210 * br, 250 * br))
        for x, y, vx, vy, layer in self.rain_d:
            if layer:
                pygame.draw.line(cv, near_c, (int(x), int(y)), (int(x - vx * 1.6), int(y - vy * 1.3)))
            else:
                cv.fill(far_c, (int(x), int(y), 1, 2))
        sc = icol((235 * br, 242 * br, 255 * br))
        for x, y, vy, ph, layer in self.snow_f:
            cv.fill(sc, (int(x), int(y), 2 if layer else 1, 2 if layer else 1))

    # ---- HUD -----------------------------------------------------------
    def draw_hud(self, cv):
        p = self.p
        m = max(0, int(-p.y / 8))
        text(cv, "HEIGHT %04d M" % m, 6, 5, (255, 240, 200))
        text(cv, "FALLS %02d" % self.deaths, 6, 13, (255, 160, 160))
        secs = self.time_f // FPS
        text(cv, "%02d:%02d" % (secs // 60, secs % 60), 6, 21, (190, 210, 255))
        # ability pips
        dc = (110, 220, 255) if p.dash_ready and p.dash_cd == 0 else (50, 70, 90)
        cv.fill(dc, (6, H - 12, 5, 5))
        cv.fill((255, 255, 255), (7, H - 11, 1, 1))
        text(cv, "DASH", 13, H - 12, (200, 215, 235))
        jc = (255, 220, 120) if (p.air_jumps > 0 or p.on_ground) else (80, 70, 50)
        cv.fill(jc, (38, H - 12, 5, 5))
        text(cv, "JUMP", 45, H - 12, (200, 215, 235))
        # progress bar
        bx, by, bh = W - 8, 12, H - 30
        for i in range(4):
            seg = bh // 4
            c = BIOMES[3 - i]["top2"]
            cv.fill(scale_c(c, .6), (bx, by + i * seg, 3, seg))
        mk = by + bh - int(clamp(-p.y / TOWER_H, 0, 1) * (bh - 1))
        cv.fill((255, 255, 255), (bx - 2, mk, 7, 2))
        cv.fill((0, 0, 0), (bx - 2, mk + 2, 7, 1))
        # biome banner
        if self.banner_t > 0 and self.state == "play":
            a = min(1.0, self.banner_t / 40, (200 - self.banner_t) / 25)
            surf = pygame.Surface((W, 30), pygame.SRCALPHA)
            text(surf, self.banner_name, W // 2, 4, (255, 240, 200), 2, center=True)
            text(surf, "ZONE %d / 4" % (self.cur_biome + 1), W // 2, 21, (200, 210, 235), 1, center=True)
            surf.set_alpha(int(255 * clamp(a, 0, 1)))
            cv.blit(surf, (0, 36))
        if self.msg_t > 0:
            a = clamp(self.msg_t / 30, 0, 1)
            surf = pygame.Surface((W, 8), pygame.SRCALPHA)
            text(surf, self.msg, W // 2, 0, (255, 235, 170), 1, center=True)
            surf.set_alpha(int(255 * a))
            cv.blit(surf, (0, 70))
        if self.red_t > 0:
            ov = pygame.Surface((W, H))
            ov.fill((int(90 * self.red_t / 12), 0, 0))
            cv.blit(ov, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        # tutorial near the start
        if self.state == "play" and p.y > -150:
            ty = int(-self.cy) - 130
            a = clamp((p.y + 150) / 100, 0, 1)
            surf = pygame.Surface((W, 40), pygame.SRCALPHA)
            text(surf, "ARROWS MOVE   SPACE JUMP (TWICE FOR DOUBLE)", W // 2, 0, (255, 255, 255), 1, center=True)
            text(surf, "X DASH   HOLD TOWARD WALL TO GRAB + JUMP", W // 2, 9, (255, 255, 255), 1, center=True)
            text(surf, "THE TOWER GETS HARDER AS YOU CLIMB", W // 2, 18, (255, 210, 140), 1, center=True)
            surf.set_alpha(int(255 * a))
            cv.blit(surf, (0, 40))

    def draw_overlay(self, cv):
        if self.state == "title":
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 90))
            cv.blit(ov, (0, 0))
            text(cv, "SHADOW", W // 2, 26, (255, 236, 200), 4, shadow=(120, 30, 40), center=True)
            text(cv, "ASCENT", W // 2, 50, (255, 120, 120), 4, shadow=(60, 10, 30), center=True)
            text(cv, "A NINJA'S CLIMB UP THE STORM TOWER", W // 2, 78, (220, 220, 240), 1, center=True)
            if (self.t // 30) % 2 == 0 or True:
                text(cv, "PRESS ANY KEY", W // 2, 112, (255, 255, 255) if (self.t // 30) % 2 == 0 else (150, 150, 170), 1,
                     center=True)
            text(cv, "ARROWS/WASD MOVE  SPACE JUMP  X DASH  P PAUSE", W // 2, 150, (170, 180, 210), 1, center=True)
        elif self.state == "win":
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 120))
            cv.blit(ov, (0, 0))
            text(cv, "SUMMIT REACHED!", W // 2, 42, (255, 232, 150), 3, shadow=(120, 60, 20), center=True)
            s = self.win_time // FPS
            text(cv, "TIME %02d:%02d    FALLS %d" % (s // 60, s % 60, self.deaths), W // 2, 84, (255, 255, 255), 1, center=True)
            text(cv, "THE SHADOW HAS BECOME THE LIGHT", W // 2, 98, (200, 210, 240), 1, center=True)
            text(cv, "PRESS R TO CLIMB AGAIN", W // 2, 122, (255, 255, 255), 1, center=True)
        elif self.paused:
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 140))
            cv.blit(ov, (0, 0))
            text(cv, "PAUSED", W // 2, 62, (255, 255, 255), 3, center=True)
            text(cv, "P RESUME   R RESTART   Q QUIT", W // 2, 92, (200, 210, 235), 1, center=True)

    # ---- master draw ---------------------------------------------------
    def draw(self, cv):
        sh = self.shake
        if sh > .15:
            ox = int(round(random.uniform(-sh, sh)))
            oy = int(round(random.uniform(-sh, sh)))
            self.shake *= .82
        else:
            ox = oy = 0
            self.shake = 0.0
        self.cx = ox
        self.cy = int(round(self.cam)) + oy
        self.draw_sky(cv)
        self.draw_world(cv)
        if not self.p.dead:
            self.draw_player(cv)
        self.draw_particles(cv)
        self.apply_lighting(cv)
        self.draw_weather(cv)
        cv.blit(self.art.vig, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        self.draw_hud(cv)
        self.draw_overlay(cv)


# ----------------------------------------------------------------------------
def main():
    try:
        pygame.mixer.pre_init(22050, -16, 1, 512)
    except Exception:
        pass
    pygame.init()
    pygame.display.set_caption("SHADOW ASCENT")
    info = pygame.display.Info()
    k = max(2, min(5, min(info.current_w // W, (info.current_h - 90) // H)))
    win = pygame.display.set_mode((W * k, H * k), pygame.RESIZABLE)
    cv = pygame.Surface((W, H))
    clock = pygame.time.Clock()
    # loading splash
    win.fill((10, 8, 20))
    pygame.display.flip()
    game = Game()
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
            game.handle_event(e)
        game.update()
        game.draw(cv)
        ww, wh = win.get_size()
        sc = min(ww / W, wh / H)
        if sc >= 2:
            sc = int(sc)
        sw, sh_ = int(W * sc), int(H * sc)
        win.fill((0, 0, 0))
        win.blit(pygame.transform.scale(cv, (sw, sh_)), ((ww - sw) // 2, (wh - sh_) // 2))
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
