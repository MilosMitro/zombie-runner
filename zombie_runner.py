import pygame
import math
import sys
import random
import array
import json
import os

# ── Init ──────────────────────────────────────────────────────────────────────
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

# Virtual canvas — game always renders at 800x600, then scaled to fill screen
WIDTH  = 800
HEIGHT = 600
info   = pygame.display.Info()
screen = pygame.display.set_mode((info.current_w, info.current_h), pygame.FULLSCREEN)
canvas = pygame.Surface((WIDTH, HEIGHT))
pygame.display.set_caption("ZOMBIE RUNNER")
clock = pygame.time.Clock()
FPS = 60

SCALE = 1.0  # virtual canvas approach — everything stays at 800x600

# ── Palette ───────────────────────────────────────────────────────────────────
BLACK       = (10, 10, 10)
DARK_GRAY   = (30, 30, 30)
MID_GRAY    = (55, 55, 55)
GRID_COLOR  = (22, 22, 22)
GREEN       = (80, 200, 80)
RED         = (220, 60, 60)
MUZZLE      = (255, 230, 100)
BULLET_COL  = (255, 220, 80)
HUD_GREEN   = (60, 200, 100)  # default, overridden by theme at runtime
WHITE       = (230, 230, 230)
BLOOD_RED   = (160, 20, 20)
ZOMBIE_COL  = (80, 160, 60)
ZOMBIE_DARK = (50, 110, 40)
ZOMBIE_EYE  = (220, 30, 30)
BAT_COL     = (180, 130, 70)
BAT_DARK    = (120, 80, 40)
BOSS_COL    = (140, 40, 160)
BOSS_DARK   = (90, 20, 110)
BOSS_EYE    = (255, 80, 0)
BOSS_GLOW   = (200, 60, 220)

def pixel_font(size):
    return pygame.font.SysFont("monospace", size, bold=True)

font_sm = pixel_font(14)
font_md = pixel_font(20)
font_lg = pixel_font(32)
font_xl = pixel_font(56)

# Pause button — top-right corner
PAUSE_BTN_RECT = pygame.Rect(WIDTH - 54, 8, 42, 28)

# Help button — main menu top-right
HELP_BTN_RECT = pygame.Rect(WIDTH - 110, 10, 32, 32)

# ── Procedural sound synthesis ────────────────────────────────────────────────
SAMPLE_RATE = 44100

def _make_sound(samples):
    buf = array.array('h')
    for s in samples:
        v = max(-32767, min(32767, int(s)))
        buf.append(v)
        buf.append(v)
    return pygame.mixer.Sound(buffer=buf.tobytes())

def _gen(freq, dur, vol, noise_mix=0.0, decay=4.0):
    n = int(SAMPLE_RATE * dur)
    out = []
    for i in range(n):
        t   = i / SAMPLE_RATE
        env = math.exp(-decay * i / n)
        sine = math.sin(2 * math.pi * freq * t)
        nz   = (hash((i * 2654435761) & 0xFFFFFFFF) / 0x7FFFFFFF - 1.0)
        out.append(vol * 32767 * env * (sine * (1 - noise_mix) + nz * noise_mix))
    return out

def build_sounds():
    sounds = {}
    sounds['shoot']      = _make_sound(_gen(180,  0.10, 0.55, noise_mix=0.45, decay=8))
    sounds['swing']      = _make_sound(_gen(120,  0.14, 0.50, noise_mix=0.90, decay=5))
    sounds['hit']        = _make_sound(_gen(90,   0.09, 0.50, noise_mix=0.60, decay=9))
    sounds['death']      = _make_sound(_gen(65,   0.16, 0.55, noise_mix=0.70, decay=5))
    sounds['boss_hit']   = _make_sound(_gen(50,   0.12, 0.60, noise_mix=0.40, decay=6))
    sounds['boss_death'] = _make_sound(_gen(38,   0.28, 0.70, noise_mix=0.80, decay=3))
    sounds['hurt']       = _make_sound(_gen(380,  0.07, 0.40, noise_mix=0.55, decay=10))
    sounds['wave_clear'] = _make_sound(_gen(520,  0.20, 0.40, noise_mix=0.05, decay=3))

    for snd in sounds.values():
        snd.set_volume(0.35)
    return sounds

SOUNDS = build_sounds()

# ── Menu music ────────────────────────────────────────────────────────────────
GAME_DIR   = os.path.dirname(os.path.abspath(__file__))
MUSIC_FILE = None
for _ext in ('menu_music.mp3', 'menu_music.ogg', 'menu_music.wav'):
    _path = os.path.join(GAME_DIR, _ext)
    if os.path.exists(_path):
        MUSIC_FILE = _path
        break

def play_menu_music():
    if MUSIC_FILE:
        vol = load_settings().get("music_vol", 0.4)
        if vol > 0:
            pygame.mixer.music.load(MUSIC_FILE)
            pygame.mixer.music.set_volume(vol)
            pygame.mixer.music.play(-1)

def stop_menu_music():
    pygame.mixer.music.stop()


def play(name, volume=1.0):
    snd = SOUNDS.get(name)
    if snd:
        snd.set_volume(0.35 * volume)
        snd.play()


# ── Leaderboard ───────────────────────────────────────────────────────────────
SCORES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scores.json")
MAX_ENTRIES = 10

def load_scores():
    try:
        with open(SCORES_FILE) as f:
            return json.load(f)
    except Exception:
        return []

def save_score(name, score, wave):
    scores = load_scores()
    scores.append({"name": name.upper()[:5], "score": score, "wave": wave})
    scores.sort(key=lambda x: x["score"], reverse=True)
    scores = scores[:MAX_ENTRIES]
    with open(SCORES_FILE, "w") as f:
        json.dump(scores, f)
    return scores

def get_rank(score):
    scores = load_scores()
    rank = sum(1 for s in scores if s["score"] > score) + 1
    return rank


# ── Shop / Skin system ────────────────────────────────────────────────────────
SHOP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shop.json")

PLAYER_SKINS = [
    # CLASSIC — blue shirt, jeans, brown boots, light skin
    {"id": "classic",  "name": "CLASSIC",   "cost": 0,
     "shirt": (30,100,200),  "shirt_drk": (20,70,140),
     "pants": (60,80,160),   "pants_drk": (40,55,120),
     "skin":  (225,172,110), "hair": (80,50,20),   "boot": (70,45,20)},
    # SOLDIER — olive green camo shirt, dark green pants, tan skin, dark boots
    {"id": "soldier",  "name": "SOLDIER",   "cost": 500,
     "shirt": (75,110,45),   "shirt_drk": (50,80,28),
     "pants": (55,75,30),    "pants_drk": (35,52,18),
     "skin":  (195,155,95),  "hair": (55,38,12),   "boot": (42,30,10)},
    # COP — navy blue shirt, black pants, badge-gold accent, dark hair
    {"id": "cop",      "name": "COP",       "cost": 800,
     "shirt": (20,40,130),   "shirt_drk": (10,25,90),
     "pants": (15,15,15),    "pants_drk": (8,8,8),
     "skin":  (220,175,115), "hair": (20,15,10),   "boot": (10,10,10)},
    # MEDIC — bright white shirt with red cross tint, white pants, fair skin, blonde
    {"id": "medic",    "name": "MEDIC",     "cost": 1500,
     "shirt": (230,60,60),   "shirt_drk": (180,30,30),
     "pants": (220,220,220), "pants_drk": (160,160,160),
     "skin":  (245,200,155), "hair": (210,190,120),"boot": (80,80,80)},
    # DOCTOR — white lab coat, teal scrubs pants, fair skin, grey hair
    {"id": "doctor",   "name": "DOCTOR",    "cost": 2000,
     "shirt": (240,240,240), "shirt_drk": (190,190,190),
     "pants": (30,160,160),  "pants_drk": (20,110,110),
     "skin":  (250,215,175), "hair": (170,170,170),"boot": (50,50,50)},
    # NINJA — dark charcoal, dark skin, black boots
    {"id": "ninja",    "name": "NINJA",     "cost": 2500,
     "shirt": (30,30,30),    "shirt_drk": (15,15,15),
     "pants": (20,20,20),    "pants_drk": (10,10,10),
     "skin":  (60,60,60),    "hair": (20,20,20),   "boot": (15,15,15)},
    # COWBOY — brown leather vest, beige pants, tanned skin, brown hat hair
    {"id": "cowboy",   "name": "COWBOY",    "cost": 3500,
     "shirt": (140,75,30),   "shirt_drk": (100,50,18),
     "pants": (200,175,120), "pants_drk": (155,135,85),
     "skin":  (200,148,88),  "hair": (100,65,18),  "boot": (90,55,15)},
    # SHADOW — purple-tinted dark outfit, grey skin, glowing purple hair
    {"id": "shadow",   "name": "SHADOW",    "cost": 4000,
     "shirt": (50,10,80),    "shirt_drk": (30,5,55),
     "pants": (35,5,60),     "pants_drk": (20,3,40),
     "skin":  (70,55,85),    "hair": (140,0,200),  "boot": (20,5,35)},
    # ROBOT — silver chest plate, dark chrome pants, metallic blue skin, LED hair
    {"id": "robot",    "name": "ROBOT",     "cost": 5000,
     "shirt": (180,190,200), "shirt_drk": (120,130,140),
     "pants": (60,65,75),    "pants_drk": (35,40,50),
     "skin":  (140,165,185), "hair": (0,200,255),  "boot": (40,45,55)},
    # NEON — hot pink shirt, electric cyan pants, glowing green skin
    {"id": "neon",     "name": "NEON",      "cost": 6000,
     "shirt": (255,0,180),   "shirt_drk": (180,0,120),
     "pants": (0,220,255),   "pants_drk": (0,150,180),
     "skin":  (0,255,160),   "hair": (255,255,0),  "boot": (0,180,200)},
]

BAT_SKINS = [
    {"id": "wood",    "name": "WOODEN BAT",  "cost": 0,    "desc": "Classic wood",
     "col": (180,130,70),  "drk": (120,80,40),   "tip": (160,110,55)},
    {"id": "pipe",    "name": "METAL PIPE",  "cost": 500,  "desc": "Unlock at 500 pts",
     "col": (160,160,175), "drk": (100,100,115), "tip": (200,200,215)},
    {"id": "neon_bat","name": "NEON BAT",    "cost": 1500, "desc": "Unlock at 1500 pts",
     "col": (0,220,220),   "drk": (0,140,140),   "tip": (180,255,255)},
    {"id": "bloody",  "name": "BLOODY BAT",  "cost": 2500, "desc": "Unlock at 2500 pts",
     "col": (160,30,30),   "drk": (100,10,10),   "tip": (220,60,60)},
    {"id": "golden",  "name": "GOLDEN BAT",  "cost": 3500, "desc": "Unlock at 3500 pts",
     "col": (220,180,40),  "drk": (160,120,20),  "tip": (255,220,80)},
    {"id": "ice",     "name": "ICE BAT",     "cost": 4500, "desc": "Unlock at 4500 pts",
     "col": (120,200,255), "drk": (60,140,210),  "tip": (200,240,255)},
    {"id": "fire",    "name": "FIRE BAT",    "cost": 5500, "desc": "Unlock at 5500 pts",
     "col": (240,80,20),   "drk": (180,40,10),   "tip": (255,160,40)},
    {"id": "toxic",   "name": "TOXIC BAT",   "cost": 7000, "desc": "Unlock at 7000 pts",
     "col": (80,200,40),   "drk": (40,140,20),   "tip": (160,255,80)},
]


ZOMBIE_SKINS = [
    {"id": "classic",  "name": "CLASSIC",    "cost": 0,
     "body": (80,160,60),   "drk": (50,110,40),  "eye": (220,30,30)},
    {"id": "toxic",    "name": "TOXIC",       "cost": 1000,
     "body": (120,220,20),  "drk": (80,160,10),  "eye": (255,255,0)},
    {"id": "frozen",   "name": "FROZEN",      "cost": 2000,
     "body": (80,180,220),  "drk": (50,130,170), "eye": (200,240,255)},
    {"id": "lava",     "name": "LAVA",        "cost": 3000,
     "body": (200,60,10),   "drk": (140,30,5),   "eye": (255,180,0)},
    {"id": "shadow",   "name": "SHADOW",      "cost": 4000,
     "body": (30,30,30),    "drk": (15,15,15),   "eye": (180,0,255)},
    {"id": "gold",     "name": "GOLD",        "cost": 5000,
     "body": (200,160,20),  "drk": (150,110,10), "eye": (255,220,60)},
    {"id": "neon",     "name": "NEON",        "cost": 7000,
     "body": (0,220,180),   "drk": (0,150,120),  "eye": (255,0,200)},
    {"id": "bone",     "name": "SKELETON",    "cost": 8000,
     "body": (220,210,190), "drk": (170,160,140),"eye": (255,80,0)},
]

def load_shop():
    try:
        with open(SHOP_FILE) as f:
            return json.load(f)
    except Exception:
        return {"total_score": 0, "player_skin": "classic", "bat_skin": "wood", "zombie_skin": "classic",
                "unlocked_players": ["classic"], "unlocked_bats": ["wood"], "unlocked_zombies": ["classic"]}

def save_shop(data):
    with open(SHOP_FILE, "w") as f:
        json.dump(data, f)

def add_score_to_shop(score):
    """Called after each game to accumulate total score."""
    data = load_shop()
    data["total_score"] = data.get("total_score", 0) + score
    # Auto-unlock anything affordable
    total = data["total_score"]
    for sk in PLAYER_SKINS:
        if total >= sk["cost"] and sk["id"] not in data.get("unlocked_players", []):
            data.setdefault("unlocked_players", ["classic"]).append(sk["id"])
    for sk in BAT_SKINS:
        if total >= sk["cost"] and sk["id"] not in data.get("unlocked_bats", []):
            data.setdefault("unlocked_bats", ["wood"]).append(sk["id"])
    for sk in ZOMBIE_SKINS:
        if total >= sk["cost"] and sk["id"] not in data.get("unlocked_zombies", []):
            data.setdefault("unlocked_zombies", ["classic"]).append(sk["id"])
    save_shop(data)

def get_active_skins():
    data  = load_shop()
    pskin = next((s for s in PLAYER_SKINS if s["id"] == data.get("player_skin","classic")), PLAYER_SKINS[0])
    bskin = next((s for s in BAT_SKINS    if s["id"] == data.get("bat_skin","wood")),       BAT_SKINS[0])
    return pskin, bskin

def get_zombie_skin():
    data  = load_shop()
    zskin = next((s for s in ZOMBIE_SKINS if s["id"] == data.get("zombie_skin","classic")), ZOMBIE_SKINS[0])
    return zskin

def get_total_score():
    return load_shop().get("total_score", 0)


# ── Settings ──────────────────────────────────────────────────────────────────
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except Exception:
        return {"music_vol": 0.4, "sfx_vol": 0.35, "theme": 0}

def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f)

def apply_settings(data):
    if MUSIC_FILE and pygame.mixer.music.get_busy():
        pygame.mixer.music.set_volume(data.get("music_vol", 0.4))
    for name, snd in SOUNDS.items():
        snd.set_volume(data.get("sfx_vol", 0.35))


# ── Theme colours ─────────────────────────────────────────────────────────────
THEMES = [
    (255,  70,  70),   # 0 red (default)
    (60,  200, 100),   # 1 green
    (80,  160, 255),   # 2 blue
    (180, 100, 255),   # 3 purple
    (255, 100, 180),   # 4 pink
    (255, 150, 100),   # 5 coral
    (255, 210,  60),   # 6 gold
    (255, 140,  30),   # 7 orange
]

def get_theme():
    idx = load_settings().get("theme", 0)
    return THEMES[max(0, min(idx, len(THEMES)-1))]

# ── Screen shake & flash ──────────────────────────────────────────────────────
shake_frames    = 0
shake_intensity = 0
flash_frames    = 0
flash_color     = (255, 255, 255)

def trigger_shake(intensity=5, frames=8):
    global shake_frames, shake_intensity
    shake_intensity = max(shake_intensity, intensity)
    shake_frames    = max(shake_frames, frames)

def trigger_flash(color, frames=3):
    global flash_frames, flash_color
    flash_color  = color
    flash_frames = frames

def get_shake_offset():
    global shake_frames, shake_intensity
    if shake_frames > 0:
        shake_frames -= 1
        ox = random.randint(-shake_intensity, shake_intensity)
        oy = random.randint(-shake_intensity, shake_intensity)
        if shake_frames == 0:
            shake_intensity = 0
        return ox, oy
    return 0, 0

# ── Floating score text ───────────────────────────────────────────────────────
class FloatText:
    def __init__(self, x, y, text, color=WHITE):
        self.x     = x
        self.y     = y
        self.text  = text
        self.color = color
        self.age   = 0
        self.life  = 50

    def update(self):
        self.y   -= 0.8
        self.age += 1

    def draw(self, surf):
        alpha = max(0, 255 - int(255 * self.age / self.life))
        t = font_sm.render(self.text, True, self.color)
        t.set_alpha(alpha)
        surf.blit(t, (int(self.x) - t.get_width() // 2, int(self.y)))

    @property
    def dead(self):
        return self.age >= self.life

float_texts = []

def spawn_float(x, y, text, color=WHITE):
    float_texts.append(FloatText(x, y, text, color))

# ── Spark particle ────────────────────────────────────────────────────────────
class Spark:
    def __init__(self, x, y, color=BULLET_COL):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(2, 6)
        self.x    = x
        self.y    = y
        self.vx   = math.cos(angle) * speed
        self.vy   = math.sin(angle) * speed
        self.life = random.randint(10, 25)
        self.age  = 0
        self.color = color

    def update(self):
        self.x  += self.vx
        self.y  += self.vy
        self.vx *= 0.9
        self.vy *= 0.9
        self.age += 1

    def draw(self, surf):
        alpha = max(0, 200 - int(200 * self.age / self.life))
        s = pygame.Surface((4, 4), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, alpha), (2, 2), 2)
        surf.blit(s, (int(self.x) - 2, int(self.y) - 2))

    @property
    def dead(self):
        return self.age >= self.life

sparks = []

def spawn_sparks(x, y, n=6, color=BULLET_COL):
    for _ in range(n):
        sparks.append(Spark(x, y, color))

# ── Arena ─────────────────────────────────────────────────────────────────────
TILE = 32
WALL = 20

def draw_arena(surf):
    surf.fill(BLACK)
    for x in range(0, WIDTH, TILE):
        pygame.draw.line(surf, GRID_COLOR, (x, 0), (x, HEIGHT))
    for y in range(0, HEIGHT, TILE):
        pygame.draw.line(surf, GRID_COLOR, (0, y), (WIDTH, y))
    pygame.draw.rect(surf, MID_GRAY, (0, 0, WIDTH, WALL))
    pygame.draw.rect(surf, MID_GRAY, (0, HEIGHT - WALL, WIDTH, WALL))
    pygame.draw.rect(surf, MID_GRAY, (0, 0, WALL, HEIGHT))
    pygame.draw.rect(surf, MID_GRAY, (WIDTH - WALL, 0, WALL, HEIGHT))
    pygame.draw.rect(surf, DARK_GRAY, (WALL, WALL, WIDTH - WALL * 2, HEIGHT - WALL * 2), 2)


# ── Blood particle ────────────────────────────────────────────────────────────
class BloodParticle:
    def __init__(self, x, y, directed_angle=None, color=None):
        if directed_angle is not None:
            angle = directed_angle + random.uniform(-0.8, 0.8)
            speed = random.uniform(2, 7)
        else:
            angle = random.uniform(0, math.tau)
            speed = random.uniform(1, 5)
        self.x     = x
        self.y     = y
        self.vx    = math.cos(angle) * speed
        self.vy    = math.sin(angle) * speed
        self.r     = random.randint(2, 6)
        self.life  = random.randint(20, 55)
        self.age   = 0
        self.color = color or BLOOD_RED

    def update(self):
        self.x  += self.vx
        self.y  += self.vy
        self.vx *= 0.88
        self.vy *= 0.88
        self.age += 1

    def draw(self, surf):
        alpha = max(0, 220 - int(220 * self.age / self.life))
        s = pygame.Surface((self.r * 2, self.r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, alpha), (self.r, self.r), self.r)
        surf.blit(s, (int(self.x) - self.r, int(self.y) - self.r))

    @property
    def dead(self):
        return self.age >= self.life


# ── Bullet ────────────────────────────────────────────────────────────────────
class Bullet:
    SPEED = 9
    SIZE  = 4

    def __init__(self, x, y, angle):
        self.x     = x
        self.y     = y
        self.vx    = math.cos(angle) * self.SPEED
        self.vy    = math.sin(angle) * self.SPEED
        self.dead  = False
        self.trail = []

    def update(self):
        self.trail.append((self.x, self.y))
        if len(self.trail) > 6:
            self.trail.pop(0)
        self.x += self.vx
        self.y += self.vy
        if not (WALL < self.x < WIDTH - WALL and WALL < self.y < HEIGHT - WALL):
            self.dead = True
            spawn_sparks(self.x, self.y, 4)

    def draw(self, surf):
        for i, (tx, ty) in enumerate(self.trail):
            alpha = int(180 * (i / len(self.trail)))
            r = max(1, self.SIZE - 2)
            s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*BULLET_COL, alpha), (r, r), r)
            surf.blit(s, (int(tx) - r, int(ty) - r))
        pygame.draw.circle(surf, BULLET_COL, (int(self.x), int(self.y)), self.SIZE)
        pygame.draw.circle(surf, WHITE,      (int(self.x), int(self.y)), self.SIZE - 2)

    def rect(self):
        return pygame.Rect(self.x - self.SIZE, self.y - self.SIZE, self.SIZE * 2, self.SIZE * 2)


# ── Melee swing ───────────────────────────────────────────────────────────────
class MeleeSwing:
    REACH     = int(60 * SCALE)
    ARC       = 110
    DURATION  = 14
    DAMAGE_HP = 2
    KNOCKBACK = int(8 * SCALE)
    COOLDOWN  = 40

    def __init__(self, cx, cy, aim_angle):
        self.cx        = cx
        self.cy        = cy
        self.aim       = aim_angle
        self.frame     = 0
        self.hit_ids   = set()
        self.particles = []

    @property
    def active(self):
        return self.frame < self.DURATION

    def check_hit(self, zombie):
        if id(zombie) in self.hit_ids:
            return False
        t       = self.frame / self.DURATION
        half    = math.radians(self.ARC / 2)
        start_a = self.aim - half
        end_a   = start_a + t * math.radians(self.ARC)
        zx, zy  = zombie.x - self.cx, zombie.y - self.cy
        dist    = math.hypot(zx, zy)
        if dist > self.REACH + zombie.SIZE:
            return False
        za = math.atan2(zy, zx)
        def adiff(a, b):
            d = (a - b) % math.tau
            return d if d < math.pi else d - math.tau
        if start_a <= za <= end_a or abs(adiff(za, (start_a + end_a) / 2)) < math.radians(self.ARC / 2 + 5):
            self.hit_ids.add(id(zombie))
            return True
        return False

    def update(self):
        self.frame += 1
        for p in self.particles[:]:
            p.update()
            if p.dead:
                self.particles.remove(p)

    def draw(self, surf):
        if not self.active and not self.particles:
            return
        for p in self.particles:
            p.draw(surf)
        if not self.active:
            return
        t       = self.frame / self.DURATION
        half    = math.radians(self.ARC / 2)
        start_a = self.aim - half
        sweep_a = t * math.radians(self.ARC)
        _, _bs = get_active_skins()
        b_col  = _bs["col"]
        b_drk  = _bs["drk"]
        b_tip  = _bs["tip"]
        for i in range(18):
            frac  = i / 18
            angle = start_a + frac * sweep_a
            alpha = int(200 * (1 - frac) * (1 - t))
            ex = self.cx + math.cos(angle) * self.REACH
            ey = self.cy + math.sin(angle) * self.REACH
            s  = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.line(s, (*b_col, alpha),
                             (int(self.cx), int(self.cy)), (int(ex), int(ey)), 5)
            surf.blit(s, (0, 0))
        lead_angle = start_a + sweep_a
        tip_x = int(self.cx + math.cos(lead_angle) * self.REACH)
        tip_y = int(self.cy + math.sin(lead_angle) * self.REACH)
        pygame.draw.circle(surf, b_tip, (tip_x, tip_y), 6)
        pygame.draw.circle(surf, WHITE, (tip_x, tip_y), 3)
        handle_x = int(self.cx + math.cos(lead_angle) * 10)
        handle_y = int(self.cy + math.sin(lead_angle) * 10)
        pygame.draw.line(surf, b_drk, (handle_x, handle_y), (tip_x, tip_y), 4)
        pygame.draw.line(surf, b_col, (handle_x, handle_y), (tip_x, tip_y), 2)

    def spawn_hit_particles(self, x, y, hit_angle, color=None):
        for _ in range(10):
            self.particles.append(BloodParticle(x, y, directed_angle=hit_angle, color=color))


# ── Zombie ────────────────────────────────────────────────────────────────────
class Zombie:
    SIZE    = 16
    MAX_HP  = 3
    DAMAGE  = 10
    SCORE   = 10
    IS_BOSS = False

    def __init__(self, wave=1):
        self._spawn_on_edge()
        self.hp           = self.MAX_HP
        self.speed        = 1.0 + 0.15 * (wave - 1)
        self.dead         = False
        self.particles    = []
        self.wobble       = random.uniform(0, math.tau)
        self.wobble_spd   = random.uniform(0.08, 0.14)
        self.knockback_vx = 0.0
        self.knockback_vy = 0.0
        self.walk_cycle   = random.uniform(0, math.tau)

    def _spawn_on_edge(self):
        edge = random.randint(0, 3)
        if edge == 0:   self.x, self.y = random.randint(WALL+20, WIDTH-WALL-20), WALL + 5
        elif edge == 1: self.x, self.y = random.randint(WALL+20, WIDTH-WALL-20), HEIGHT - WALL - 5
        elif edge == 2: self.x, self.y = WALL + 5, random.randint(WALL+20, HEIGHT-WALL-20)
        else:           self.x, self.y = WIDTH - WALL - 5, random.randint(WALL+20, HEIGHT-WALL-20)

    def update(self, player):
        dx   = player.x - self.x
        dy   = player.y - self.y
        dist = math.hypot(dx, dy)
        if dist > 0:
            self.x += (dx / dist) * self.speed
            self.y += (dy / dist) * self.speed
        self.x += self.knockback_vx
        self.y += self.knockback_vy
        self.knockback_vx *= 0.75
        self.knockback_vy *= 0.75
        self.x = max(WALL + self.SIZE, min(WIDTH  - WALL - self.SIZE, self.x))
        self.y = max(WALL + self.SIZE, min(HEIGHT - WALL - self.SIZE, self.y))
        self.wobble    += self.wobble_spd
        self.walk_cycle += 0.18
        for p in self.particles[:]:
            p.update()
            if p.dead:
                self.particles.remove(p)

    def hit(self, damage=1, knockback_angle=None, knockback_force=0):
        self.hp -= damage
        for _ in range(6):
            self.particles.append(BloodParticle(self.x, self.y))
        if knockback_angle is not None:
            self.knockback_vx = math.cos(knockback_angle) * knockback_force
            self.knockback_vy = math.sin(knockback_angle) * knockback_force
        if self.hp <= 0:
            for _ in range(14):
                self.particles.append(BloodParticle(self.x, self.y))
            self.dead = True

    def draw(self, surf):
        for p in self.particles:
            p.draw(surf)
        if self.dead:
            return
        cx  = int(self.x); cy = int(self.y)
        wc  = self.walk_cycle
        wo  = int(math.sin(self.wobble) * 1)  # gentle body sway

        # Colours from equipped skin
        _zs     = get_zombie_skin()
        z_skin  = _zs["body"]
        z_dark  = _zs["drk"]
        z_shirt = tuple(max(0, c-20) for c in _zs["body"])
        z_eye   = _zs["eye"]

        # Shadow fits SIZE=16
        pygame.draw.ellipse(surf, (5,5,5), (cx-11, cy+8+wo, 22, 7))

        # ── Legs — shuffling walk (reduced swing vs player) ──
        leg_swing = math.sin(wc) * 5
        for side, swing in ((+1, leg_swing), (-1, -leg_swing)):
            hpx = cx + side * 4
            hpy = cy + 3 + wo
            ftx = hpx + int(swing * 0.5)
            fty = hpy + 9
            pygame.draw.line(surf, z_dark, (hpx, hpy), (ftx, fty), 4)

        # ── Torso ──
        pygame.draw.rect(surf, z_shirt, (cx-5, cy-5+wo, 10, 9), border_radius=2)

        # ── Arms — outstretched zombie pose with arm-raise bob ──
        arm_bob = math.sin(wc * 0.5) * 2
        # Left arm
        pygame.draw.line(surf, z_skin, (cx-5, cy-3+wo), (cx-14, cy-6+wo+int(arm_bob)), 3)
        # Left claws
        lhx, lhy = cx-14, cy-6+wo+int(arm_bob)
        pygame.draw.line(surf, z_dark, (lhx, lhy), (lhx-3, lhy-3), 2)
        pygame.draw.line(surf, z_dark, (lhx, lhy), (lhx-4, lhy-1), 2)
        pygame.draw.line(surf, z_dark, (lhx, lhy), (lhx-2, lhy-4), 2)
        # Right arm
        pygame.draw.line(surf, z_skin, (cx+5, cy-3+wo), (cx+14, cy-5+wo-int(arm_bob)), 3)
        # Right claws
        rhx, rhy = cx+14, cy-5+wo-int(arm_bob)
        pygame.draw.line(surf, z_dark, (rhx, rhy), (rhx+3, rhy-3), 2)
        pygame.draw.line(surf, z_dark, (rhx, rhy), (rhx+4, rhy-1), 2)
        pygame.draw.line(surf, z_dark, (rhx, rhy), (rhx+2, rhy-4), 2)

        # ── Head — centred, fits within SIZE=16 ──
        pygame.draw.circle(surf, z_skin, (cx, cy-12+wo), 7)
        pygame.draw.circle(surf, z_dark, (cx, cy-12+wo), 7, 1)

        # Glowing eyes
        pygame.draw.circle(surf, z_eye,         (cx-3, cy-13+wo), 2)
        pygame.draw.circle(surf, z_eye,         (cx+3, cy-13+wo), 2)
        pygame.draw.circle(surf, (255,130,130), (cx-3, cy-13+wo), 1)
        pygame.draw.circle(surf, (255,130,130), (cx+3, cy-13+wo), 1)

        # Hair tufts
        pygame.draw.line(surf, z_dark, (cx-3, cy-18+wo), (cx-5, cy-22+wo), 2)
        pygame.draw.line(surf, z_dark, (cx,   cy-19+wo), (cx,   cy-23+wo), 2)
        pygame.draw.line(surf, z_dark, (cx+3, cy-18+wo), (cx+5, cy-22+wo), 2)

        # HP pips — just above head
        for i in range(self.MAX_HP):
            col = RED if i < self.hp else DARK_GRAY
            pygame.draw.rect(surf, col, (cx-10+i*8, cy-26+wo, 6, 4))

    def rect(self):
        s = self.SIZE
        return pygame.Rect(self.x-s//2, self.y-s//2, s, s)


# ── Boss zombie ───────────────────────────────────────────────────────────────
class BossZombie(Zombie):
    SIZE    = 36
    MAX_HP  = 30
    DAMAGE  = 25
    SCORE   = 200
    IS_BOSS = True
    CHARGE_RANGE  = 200
    CHARGE_SPEED  = 7
    CHARGE_FRAMES = 30
    CHARGE_CD     = 180

    def __init__(self, wave=1):
        super().__init__(wave)
        self.speed              = 1.2 + 0.1 * (wave - 1)
        self.hp                 = self.MAX_HP
        self.charge_timer       = 0
        self.charging           = False
        self.charge_frames_left = 0
        self.charge_vx          = 0.0
        self.charge_vy          = 0.0
        self.glow_tick          = 0
        self.wobble_spd         = 0.05
        self.walk_cycle         = 0.0

    def update(self, player):
        self.wobble    += self.wobble_spd
        self.glow_tick += 1
        self.knockback_vx *= 0.80
        self.knockback_vy *= 0.80

        if self.charging:
            self.x += self.charge_vx + self.knockback_vx
            self.y += self.charge_vy + self.knockback_vy
            self.charge_frames_left -= 1
            if self.charge_frames_left <= 0:
                self.charging     = False
                self.charge_timer = self.CHARGE_CD
        else:
            self.charge_timer = max(0, self.charge_timer - 1)
            dx   = player.x - self.x
            dy   = player.y - self.y
            dist = math.hypot(dx, dy)
            if dist > 0:
                self.x += (dx / dist) * self.speed + self.knockback_vx
                self.y += (dy / dist) * self.speed + self.knockback_vy
            if dist < self.CHARGE_RANGE and self.charge_timer == 0:
                self.charging           = True
                self.charge_frames_left = self.CHARGE_FRAMES
                self.charge_vx          = (dx / dist) * self.CHARGE_SPEED
                self.charge_vy          = (dy / dist) * self.CHARGE_SPEED
                trigger_shake(4, 6)
                play('boss_hit', 0.5)

        self.x = max(WALL+self.SIZE, min(WIDTH -WALL-self.SIZE, self.x))
        self.y = max(WALL+self.SIZE, min(HEIGHT-WALL-self.SIZE, self.y))
        self.walk_cycle += 0.12
        for p in self.particles[:]:
            p.update()
            if p.dead:
                self.particles.remove(p)

    def hit(self, damage=1, knockback_angle=None, knockback_force=0):
        self.hp -= damage
        if knockback_angle is not None:
            self.knockback_vx = math.cos(knockback_angle) * knockback_force * 0.3
            self.knockback_vy = math.sin(knockback_angle) * knockback_force * 0.3
        for _ in range(4):
            self.particles.append(BloodParticle(self.x, self.y, color=(180,40,200)))
        spawn_sparks(self.x, self.y, 8, color=BOSS_GLOW)
        if self.hp <= 0:
            for _ in range(30):
                self.particles.append(BloodParticle(self.x, self.y, color=(180,40,200)))
            spawn_sparks(self.x, self.y, 30, color=BOSS_GLOW)
            self.dead = True
            trigger_shake(14, 24)
            trigger_flash(BOSS_GLOW, 6)
            play('boss_death')

    def draw(self, surf):
        for p in self.particles:
            p.draw(surf)
        if self.dead:
            return
        cx  = int(self.x); cy = int(self.y)
        wo  = int(math.sin(self.wobble) * 2)
        eg  = int(3 + 2 * math.sin(self.glow_tick * 0.2))
        wc  = self.walk_cycle

        # Pulsing glow ring — fits SIZE=36
        glow_r = 40 + int(4 * math.sin(self.glow_tick * 0.12))
        gs = pygame.Surface((glow_r*2+4, glow_r*2+4), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*BOSS_GLOW, 55), (glow_r+2, glow_r+2), glow_r)
        surf.blit(gs, (cx-glow_r-2, cy-glow_r-2+wo))

        # Charge trail
        if self.charging:
            ts = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.circle(ts, (*BOSS_GLOW, 70), (cx, cy+wo), 40)
            surf.blit(ts, (0, 0))

        # Shadow
        pygame.draw.ellipse(surf, (5,5,5), (cx-26, cy+20+wo, 52, 12))

        # Legs — stomping walk, within SIZE=36
        leg_swing = math.sin(wc) * 9
        for side, swing in ((+1, leg_swing), (-1, -leg_swing)):
            hpx = cx + side * 9
            hpy = cy + 6 + wo
            knx = hpx + int(swing * 0.3)
            kny = hpy + 14
            ftx = hpx + int(swing * 0.8)
            fty = hpy + 26
            pygame.draw.line(surf, BOSS_DARK, (hpx, hpy), (knx, kny), 9)
            pygame.draw.line(surf, (40,20,10),(knx, kny),  (ftx, fty), 8)
            pygame.draw.ellipse(surf, (40,20,10), (ftx-8, fty-3, 16, 7))

        # Torso
        pygame.draw.rect(surf, BOSS_COL,  (cx-18, cy-14+wo, 36, 24), border_radius=5)
        pygame.draw.rect(surf, BOSS_DARK, (cx-18, cy-14+wo, 36, 24), 2, border_radius=5)
        pygame.draw.line(surf, BOSS_DARK, (cx-7, cy+wo),   (cx+7, cy+wo),   2)
        pygame.draw.line(surf, BOSS_DARK, (cx-4, cy-4+wo), (cx+4, cy-4+wo), 2)

        # Arms swing with walk
        arm_swing = math.sin(wc + math.pi) * 6
        pygame.draw.line(surf, BOSS_COL,  (cx-18, cy-8+wo), (cx-32, cy-3+wo+int(arm_swing)), 10)
        pygame.draw.line(surf, BOSS_DARK, (cx-18, cy-8+wo), (cx-32, cy-3+wo+int(arm_swing)),  2)
        lhx, lhy = cx-32, cy-3+wo+int(arm_swing)
        for dy in (-5, -1, 3):
            pygame.draw.line(surf, BOSS_EYE, (lhx, lhy), (lhx-5, lhy+dy), 2)
        pygame.draw.line(surf, BOSS_COL,  (cx+18, cy-8+wo), (cx+32, cy-3+wo-int(arm_swing)), 10)
        pygame.draw.line(surf, BOSS_DARK, (cx+18, cy-8+wo), (cx+32, cy-3+wo-int(arm_swing)),  2)
        rhx, rhy = cx+32, cy-3+wo-int(arm_swing)
        for dy in (-5, -1, 3):
            pygame.draw.line(surf, BOSS_EYE, (rhx, rhy), (rhx+5, rhy+dy), 2)

        # Neck
        pygame.draw.rect(surf, BOSS_COL, (cx-6, cy-22+wo, 12, 10), border_radius=2)

        # Head
        pygame.draw.rect(surf, BOSS_COL,  (cx-14, cy-40+wo, 28, 20), border_radius=4)
        pygame.draw.rect(surf, BOSS_DARK, (cx-14, cy-40+wo, 28, 20), 2, border_radius=4)

        # Horns
        pygame.draw.polygon(surf, BOSS_DARK, [
            (cx-8,  cy-38+wo), (cx-13, cy-52+wo), (cx-3, cy-38+wo)])
        pygame.draw.polygon(surf, BOSS_DARK, [
            (cx+8,  cy-38+wo), (cx+13, cy-52+wo), (cx+3, cy-38+wo)])

        # Glowing eyes
        for ex2 in (cx-6, cx+6):
            pygame.draw.circle(surf, BOSS_EYE,     (ex2, cy-31+wo), eg+2)
            pygame.draw.circle(surf, (255,200,50), (ex2, cy-31+wo), eg)

        # Teeth
        pygame.draw.line(surf, BOSS_DARK, (cx-7, cy-23+wo), (cx+7, cy-23+wo), 2)
        for tx in range(cx-6, cx+7, 4):
            pygame.draw.line(surf, WHITE, (tx, cy-23+wo), (tx+2, cy-19+wo), 2)

        if self.charging:
            ct = font_sm.render("CHARGE!", True, BOSS_EYE)
            surf.blit(ct, (cx - ct.get_width()//2, cy-58+wo))
    def draw_boss_hud(self, surf):
        bar_w = WIDTH - 200
        bar_h = 18
        bar_x = 100
        bar_y = HEIGHT - 68
        pygame.draw.rect(surf, DARK_GRAY, (bar_x, bar_y, bar_w, bar_h))
        fill    = int(bar_w * (self.hp / self.MAX_HP))
        pct     = self.hp / self.MAX_HP
        bar_col = (int(220*(1-pct)), int(60+140*pct), 200) if pct > 0.3 else BOSS_EYE
        pygame.draw.rect(surf, bar_col,   (bar_x, bar_y, fill, bar_h))
        pygame.draw.rect(surf, BOSS_GLOW, (bar_x, bar_y, bar_w, bar_h), 2)
        label = font_sm.render(f"BOSS  {self.hp}/{self.MAX_HP}", True, WHITE)
        surf.blit(label, (bar_x + bar_w//2 - label.get_width()//2, bar_y-18))

    def rect(self):
        s = self.SIZE
        return pygame.Rect(self.x-s//2, self.y-s//2, s, s)


# ── Player ────────────────────────────────────────────────────────────────────
class Player:
    SIZE      = 18
    SPEED     = 3
    MAX_HP    = 100
    SHOOT_CD  = 180
    MELEE_CD  = MeleeSwing.COOLDOWN

    def __init__(self):
        self.x           = WIDTH  // 2
        self.y           = HEIGHT // 2
        self.hp          = self.MAX_HP
        self.angle       = 0
        self.shoot_timer = 0
        self.melee_timer = 0
        self.bullets     = []
        self.swings      = []
        self.hurt_flash  = 0
        self.walk_cycle  = 0.0
        self.moving      = False

    def update(self, dt, mx, my):
        keys = pygame.key.get_pressed()
        dx = dy = 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:    dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += 1
        if dx and dy:
            dx *= 0.707; dy *= 0.707
        self.moving = (dx != 0 or dy != 0)
        self.x = max(WALL+self.SIZE, min(WIDTH -WALL-self.SIZE, self.x+dx*self.SPEED))
        self.y = max(WALL+self.SIZE, min(HEIGHT-WALL-self.SIZE, self.y+dy*self.SPEED))
        if self.moving:
            self.walk_cycle += 0.22
        self.angle       = math.atan2(my - self.y, mx - self.x)
        self.shoot_timer = max(0, self.shoot_timer - dt)
        self.melee_timer = max(0, self.melee_timer - 1)
        self.hurt_flash  = max(0, self.hurt_flash  - 1)
        for b in self.bullets[:]:
            b.update()
            if b.dead:
                self.bullets.remove(b)
        for sw in self.swings[:]:
            sw.update()
            if not sw.active and not sw.particles:
                self.swings.remove(sw)

    def try_shoot(self):
        if self.shoot_timer == 0:
            bx = self.x + math.cos(self.angle) * (self.SIZE + 4)
            by = self.y + math.sin(self.angle) * (self.SIZE + 4)
            self.bullets.append(Bullet(bx, by, self.angle))
            self.shoot_timer = self.SHOOT_CD
            play('shoot')
            spawn_sparks(bx, by, 4, MUZZLE)

    def try_melee(self):
        if self.melee_timer == 0:
            self.swings.append(MeleeSwing(self.x, self.y, self.angle))
            self.melee_timer = self.MELEE_CD
            trigger_shake(3, 5)
            play('swing')

    def take_damage(self, amount):
        prev_hp = self.hp
        self.hp = max(0, self.hp - amount)
        self.hurt_flash = 8
        # Only play hurt sound once per significant hit
        if int(prev_hp) != int(self.hp) and int(self.hp) % 10 == 0:
            play('hurt')
            trigger_flash(RED, 2)

    def draw(self, surf):
        for sw in self.swings:
            sw.draw(surf)
        for b in self.bullets:
            b.draw(surf)

        cx  = int(self.x);  cy = int(self.y)
        a   = self.angle
        wc  = self.walk_cycle
        hurt = self.hurt_flash > 0

        # Perp axis (left/right of character, always screen-aligned)
        # We draw the character top-down: torso centred at cx,cy
        # legs hang below (cy+), head above (cy-)

        _ps, _bs  = get_active_skins()
        skin      = _ps["skin"]
        hair      = _ps["hair"]
        shirt_col = (200, 50, 50) if hurt else _ps["shirt"]
        shirt_drk = (150, 30, 30) if hurt else _ps["shirt_drk"]
        pants_col = _ps["pants"]
        pants_drk = _ps["pants_drk"]
        boot_col  = _ps["boot"]
        gun_col   = (140, 140, 140)
        gun_drk   = (80,  80,  80)

        # ── Shadow ──
        pygame.draw.ellipse(surf, (0,0,0,) , (cx-13, cy+8, 26, 9))
        s_surf = pygame.Surface((26,9), pygame.SRCALPHA)
        pygame.draw.ellipse(s_surf, (0,0,0,90), (0,0,26,9))
        surf.blit(s_surf, (cx-13, cy+8))

        # ── Walk cycle values ──
        ls  = math.sin(wc) * 8       if self.moving else 0   # left leg swing
        rs  = math.sin(wc + math.pi) * 8 if self.moving else 0   # right leg swing
        ab  = math.sin(wc + math.pi) * 4 if self.moving else 0   # arm bob

        # ── Left leg ──
        l_hip_x, l_hip_y  = cx - 5,  cy + 5
        l_knee_x, l_knee_y = cx - 6, cy + 11 + int(ls * 0.3)
        l_foot_x, l_foot_y = cx - 5, cy + 17 + int(ls)
        pygame.draw.line(surf, pants_col, (l_hip_x,  l_hip_y),  (l_knee_x, l_knee_y), 5)
        pygame.draw.line(surf, pants_drk, (l_hip_x,  l_hip_y),  (l_knee_x, l_knee_y), 1)
        pygame.draw.line(surf, boot_col,  (l_knee_x, l_knee_y), (l_foot_x, l_foot_y), 5)
        pygame.draw.ellipse(surf, boot_col, (l_foot_x-4, l_foot_y-2, 9, 6))

        # ── Right leg ──
        r_hip_x, r_hip_y  = cx + 5,  cy + 5
        r_knee_x, r_knee_y = cx + 6, cy + 11 + int(rs * 0.3)
        r_foot_x, r_foot_y = cx + 5, cy + 17 + int(rs)
        pygame.draw.line(surf, pants_col, (r_hip_x,  r_hip_y),  (r_knee_x, r_knee_y), 5)
        pygame.draw.line(surf, pants_drk, (r_hip_x,  r_hip_y),  (r_knee_x, r_knee_y), 1)
        pygame.draw.line(surf, boot_col,  (r_knee_x, r_knee_y), (r_foot_x, r_foot_y), 5)
        pygame.draw.ellipse(surf, boot_col, (r_foot_x-4, r_foot_y-2, 9, 6))

        # ── Torso ──
        torso_rect = pygame.Rect(cx-8, cy-8, 16, 14)
        pygame.draw.rect(surf, shirt_col, torso_rect, border_radius=3)
        pygame.draw.rect(surf, shirt_drk, torso_rect, 1, border_radius=3)
        # Collar detail
        pygame.draw.line(surf, shirt_drk, (cx-3, cy-8), (cx+3, cy-8), 2)

        # ── Off arm (left) — swings naturally while walking ──
        la_sx, la_sy = cx - 8, cy - 4
        la_ex = la_sx - 4 + int(ab * 0.4)
        la_ey = la_sy + 10 + int(ab)
        la_hx = la_ex - 2
        la_hy = la_ey + 4
        pygame.draw.line(surf, skin, (la_sx, la_sy), (la_ex, la_ey), 4)
        pygame.draw.line(surf, skin, (la_ex, la_ey), (la_hx, la_hy), 3)
        pygame.draw.circle(surf, skin, (la_hx, la_hy), 3)

        # ── Gun arm (right) — rotates toward aim angle ──
        # Shoulder fixed to torso right side
        ga_sx = cx + 8
        ga_sy = cy - 4
        # Elbow follows aim but slightly lagged (2/3 toward aim)
        elbow_dist = 9
        ga_ex = ga_sx + int(math.cos(a) * elbow_dist)
        ga_ey = ga_sy + int(math.sin(a) * elbow_dist)
        # Hand at full extension
        ga_hx = ga_sx + int(math.cos(a) * 15)
        ga_hy = ga_sy + int(math.sin(a) * 15)
        pygame.draw.line(surf, skin,    (ga_sx, ga_sy), (ga_ex, ga_ey), 4)
        pygame.draw.line(surf, skin,    (ga_ex, ga_ey), (ga_hx, ga_hy), 3)

        # ── Gun — extends from hand toward aim ──
        # Grip
        grip_x = ga_hx + int(math.cos(a) * 2)
        grip_y = ga_hy + int(math.sin(a) * 2)
        # Barrel tip
        tip_x  = ga_hx + int(math.cos(a) * 14)
        tip_y  = ga_hy + int(math.sin(a) * 14)
        # Gun body (slightly wider line)
        pygame.draw.line(surf, gun_drk, (grip_x, grip_y), (tip_x, tip_y), 5)
        pygame.draw.line(surf, gun_col, (grip_x, grip_y), (tip_x, tip_y), 3)
        # Barrel highlight
        perp_x = int(math.cos(a + math.pi/2) * 1)
        perp_y = int(math.sin(a + math.pi/2) * 1)
        pygame.draw.line(surf, (200,200,200),
                         (grip_x + perp_x, grip_y + perp_y),
                         (tip_x  + perp_x, tip_y  + perp_y), 1)

        # ── Head (top-down, centred above torso) ──
        hx, hy = cx, cy - 12
        # Neck
        pygame.draw.line(surf, skin, (cx, cy-8), (hx, hy+7), 5)

        # Head circle
        pygame.draw.circle(surf, skin,          (hx, hy), 9)
        pygame.draw.circle(surf, (175, 125, 72),(hx, hy), 9, 1)

        # Hair — top of head, shaped cap
        hair_pts = [
            (hx-9, hy-1), (hx-7, hy-7), (hx-3, hy-10),
            (hx+3, hy-10),(hx+7, hy-7),  (hx+9, hy-1),
            (hx+6, hy+2), (hx-6, hy+2)
        ]
        pygame.draw.polygon(surf, hair, hair_pts)

        # Eyes — two dots positioned toward aim direction
        eye_offset = 4
        eye_side   = 3
        # Right eye (gun side)
        re_x = hx + int(math.cos(a) * eye_offset) + int(math.cos(a + math.pi/2) * eye_side)
        re_y = hy + int(math.sin(a) * eye_offset) + int(math.sin(a + math.pi/2) * eye_side)
        # Left eye
        le_x = hx + int(math.cos(a) * eye_offset) - int(math.cos(a + math.pi/2) * eye_side)
        le_y = hy + int(math.sin(a) * eye_offset) - int(math.sin(a + math.pi/2) * eye_side)
        pygame.draw.circle(surf, (255,255,255), (re_x, re_y), 2)
        pygame.draw.circle(surf, (255,255,255), (le_x, le_y), 2)
        pygame.draw.circle(surf, (30, 30,  80), (re_x, re_y), 1)
        pygame.draw.circle(surf, (30, 30,  80), (le_x, le_y), 1)

        # Ear nubs
        pygame.draw.circle(surf, skin, (hx - int(math.cos(a+math.pi/2)*9), hy - int(math.sin(a+math.pi/2)*9)), 3)
        pygame.draw.circle(surf, skin, (hx + int(math.cos(a+math.pi/2)*9), hy + int(math.sin(a+math.pi/2)*9)), 3)

        # ── Muzzle flash ──
        if self.shoot_timer > self.SHOOT_CD * 0.6:
            mfx = tip_x + int(math.cos(a) * 4)
            mfy = tip_y + int(math.sin(a) * 4)
            pygame.draw.circle(surf, MUZZLE, (mfx, mfy), 6)
            pygame.draw.circle(surf, WHITE,  (mfx, mfy), 3)
            # Cross flare
            for fa in (0, math.pi/2):
                pygame.draw.line(surf, MUZZLE,
                    (mfx + int(math.cos(a+fa)*2), mfy + int(math.sin(a+fa)*2)),
                    (mfx + int(math.cos(a+fa)*8), mfy + int(math.sin(a+fa)*8)), 2)
                pygame.draw.line(surf, MUZZLE,
                    (mfx - int(math.cos(a+fa)*2), mfy - int(math.sin(a+fa)*2)),
                    (mfx - int(math.cos(a+fa)*8), mfy - int(math.sin(a+fa)*8)), 2)

    def draw_hud(self, surf):
        bar_x, bar_y, bar_w, bar_h = 30, HEIGHT-40, 200, 16
        pygame.draw.rect(surf, DARK_GRAY, (bar_x, bar_y, bar_w, bar_h))
        fill = int(bar_w * (self.hp / self.MAX_HP))
        col  = HUD_GREEN if self.hp > 40 else (220,160,40) if self.hp > 20 else RED
        pygame.draw.rect(surf, col, (bar_x, bar_y, fill, bar_h))
        pygame.draw.rect(surf, MID_GRAY, (bar_x, bar_y, bar_w, bar_h), 1)
        surf.blit(font_sm.render(f"HP  {self.hp}/{self.MAX_HP}", True, WHITE), (bar_x, bar_y-18))

        slot_w, slot_h, slot_gap = 70, 48, 8
        base_x = WIDTH - (slot_w*2+slot_gap) - 20
        base_y = HEIGHT - slot_h - 14
        for i, (bind, name) in enumerate([("LMB","GUN"),("RMB","BAT")]):
            sx     = base_x + i*(slot_w+slot_gap)
            active = (name=="BAT" and self.melee_timer>0) or (name=="GUN" and self.shoot_timer>0)
            pygame.draw.rect(surf, (40,40,40) if active else (20,20,20), (sx,base_y,slot_w,slot_h), border_radius=4)
            pygame.draw.rect(surf, HUD_GREEN if active else MID_GRAY,    (sx,base_y,slot_w,slot_h), 2, border_radius=4)
            if active:
                pygame.draw.rect(surf, HUD_GREEN, (sx, base_y+6, 4, slot_h-12), border_radius=2)
            surf.blit(font_sm.render(bind, True, (120,120,120)), (sx+slot_w//2-font_sm.size(bind)[0]//2, base_y+6))
            surf.blit(font_sm.render(name, True, WHITE if active else (130,130,130)), (sx+slot_w//2-font_sm.size(name)[0]//2, base_y+26))
            if name=="GUN" and self.shoot_timer>0:
                pygame.draw.rect(surf, HUD_GREEN, (sx+4, base_y+slot_h-6, int((slot_w-8)*(1-self.shoot_timer/self.SHOOT_CD)), 4))
            if name=="BAT" and self.melee_timer>0:
                pygame.draw.rect(surf, BAT_COL,   (sx+4, base_y+slot_h-6, int((slot_w-8)*(1-self.melee_timer/self.MELEE_CD)), 4))

    def rect(self):
        s = self.SIZE
        return pygame.Rect(self.x-s//2, self.y-s//2, s, s)

    def active_swings(self):
        return [sw for sw in self.swings if sw.active]


# ── Wave manager ──────────────────────────────────────────────────────────────
class WaveManager:
    BASE_COUNT  = 5
    COUNT_STEP  = 3
    BETWEEN_MS  = 3000
    BOSS_EVERY  = 5

    def __init__(self):
        self.wave           = 0
        self.zombies        = []
        self.spawned        = 0
        self.to_spawn       = 0
        self.spawn_timer    = 0
        self.spawn_delay    = 800
        self.between        = False
        self.between_timer  = 0
        self.announce_timer = 0
        self.is_boss_wave   = False
        self.just_cleared   = False
        self._start_next_wave()

    def _start_next_wave(self):
        self.wave          += 1
        self.is_boss_wave   = (self.wave % self.BOSS_EVERY == 0)
        self.to_spawn       = 1 if self.is_boss_wave else self.BASE_COUNT+(self.wave-1)*self.COUNT_STEP
        self.spawned        = 0
        self.spawn_timer    = 0
        self.between        = False
        self.announce_timer = 210
        self.just_cleared   = False

    def update(self, dt, player):
        self.announce_timer = max(0, self.announce_timer-1)

        if self.between:
            self.between_timer -= dt
            if self.between_timer <= 0:
                self._start_next_wave()
            return

        if self.spawned < self.to_spawn:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                self.zombies.append(BossZombie(wave=self.wave) if self.is_boss_wave else Zombie(wave=self.wave))
                self.spawned     += 1
                self.spawn_timer  = self.spawn_delay

        for z in self.zombies[:]:
            z.update(player)
            if z.rect().colliderect(player.rect()):
                player.take_damage(z.DAMAGE * dt / 1000)
            if z.dead and not z.particles:
                self.zombies.remove(z)

        if self.spawned >= self.to_spawn and all(z.dead for z in self.zombies) and not self.just_cleared:
            self.just_cleared  = True
            self.between       = True
            self.between_timer = self.BETWEEN_MS
            play('wave_clear')
            trigger_flash(HUD_GREEN, 4)

    def draw(self, surf):
        for z in self.zombies:
            z.draw(surf)
        for z in self.zombies:
            if z.IS_BOSS and not z.dead:
                z.draw_boss_hud(surf)

    def remaining(self):
        return sum(1 for z in self.zombies if not z.dead) + (self.to_spawn - self.spawned)

    def boss(self):
        for z in self.zombies:
            if z.IS_BOSS and not z.dead:
                return z
        return None


# ── HUD helpers ───────────────────────────────────────────────────────────────
def draw_crosshair(surf, mx, my):
    L = 10; G = 3
    pygame.draw.line(surf, (200,200,200), (mx-L,my), (mx-G,my), 1)
    pygame.draw.line(surf, (200,200,200), (mx+G,my), (mx+L,my), 1)
    pygame.draw.line(surf, (200,200,200), (mx,my-L), (mx,my-G), 1)
    pygame.draw.line(surf, (200,200,200), (mx,my+G), (mx,my+L), 1)
    pygame.draw.circle(surf, (200,200,200), (mx,my), 4, 1)



def draw_pause_btn(surf, mx, my):
    hovered = PAUSE_BTN_RECT.collidepoint(mx, my)
    col_bg  = (60, 60, 60) if hovered else (30, 30, 30)
    col_border = WHITE if hovered else MID_GRAY
    pygame.draw.rect(surf, col_bg,     PAUSE_BTN_RECT, border_radius=4)
    pygame.draw.rect(surf, col_border, PAUSE_BTN_RECT, 1, border_radius=4)
    # Two pause bars
    bx = PAUSE_BTN_RECT.x + 12
    by = PAUSE_BTN_RECT.y + 7
    pygame.draw.rect(surf, col_border, (bx,      by, 5, 14))
    pygame.draw.rect(surf, col_border, (bx + 9,  by, 5, 14))

def draw_top_hud(surf, wave, score, remaining, between, between_timer, is_boss_wave):
    col    = BOSS_GLOW if is_boss_wave else HUD_GREEN
    w_text = font_md.render(f"WAVE  {wave}", True, col)
    surf.blit(w_text, (WIDTH//2 - w_text.get_width()//2, 26))
    s_text = font_sm.render(f"SCORE  {score:06}", True, WHITE)
    surf.blit(s_text, (WIDTH - s_text.get_width() - 80, 26))
    r_text = font_sm.render(f"REMAINING  {remaining}", True, (180,180,180))
    surf.blit(r_text, (30, 26))
    if between:
        secs = math.ceil(between_timer / 1000)
        msg  = font_lg.render(f"WAVE {wave+1} IN  {secs}...", True, HUD_GREEN)
        bg   = pygame.Surface((msg.get_width()+20, 50), pygame.SRCALPHA)
        bg.fill((0,0,0,160))
        surf.blit(bg,  (WIDTH//2-bg.get_width()//2,  HEIGHT//2-30))
        surf.blit(msg, (WIDTH//2-msg.get_width()//2, HEIGHT//2-22))


def draw_wave_banner(surf, wave, timer, is_boss_wave):
    if timer <= 0:
        return
    alpha = min(255, timer * 3)
    if is_boss_wave:
        msg = font_lg.render(f"!! BOSS WAVE {wave} !!", True, BOSS_EYE)
        bg  = pygame.Surface((msg.get_width()+40, 60), pygame.SRCALPHA)
        bg.fill((60, 0, 80, min(200, alpha)))
        tmp = msg.copy(); tmp.set_alpha(alpha)
        bg.blit(tmp, (20, 14))
        surf.blit(bg, (WIDTH//2-bg.get_width()//2, HEIGHT//2-80))
        sub = font_sm.render("A HUGE ZOMBIE APPROACHES", True, BOSS_GLOW)
        sub.set_alpha(alpha)
        surf.blit(sub, (WIDTH//2-sub.get_width()//2, HEIGHT//2-10))
    else:
        msg = font_lg.render(f"-- WAVE {wave} --", True, RED)
        bg  = pygame.Surface((msg.get_width()+40, 60), pygame.SRCALPHA)
        bg.fill((0,0,0,min(180, alpha)))
        tmp = msg.copy(); tmp.set_alpha(alpha)
        bg.blit(tmp, (20, 14))
        surf.blit(bg, (WIDTH//2-bg.get_width()//2, HEIGHT//2-80))


def draw_vignette(surf, player_hp, boss_alive=False):
    if player_hp <= 40:
        intensity = int(180 * (1 - player_hp / 40))
        vig = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for thick in range(60, 0, -4):
            a = max(0, intensity - thick*2)
            pygame.draw.rect(vig, (180,0,0,a), (thick,thick,WIDTH-thick*2,HEIGHT-thick*2), 4)
        surf.blit(vig, (0,0))
    if boss_alive:
        vig2 = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for thick in range(80, 40, -8):
            pygame.draw.rect(vig2, (100,0,120,8), (thick,thick,WIDTH-thick*2,HEIGHT-thick*2), 6)
        surf.blit(vig2, (0,0))


def draw_flash(surf):
    global flash_frames
    if flash_frames <= 0:
        return
    alpha = int(120 * flash_frames / 6)
    f = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    f.fill((*flash_color, alpha))
    surf.blit(f, (0, 0))
    flash_frames -= 1


def draw_sparks(surf):
    for sp in sparks[:]:
        sp.update()
        sp.draw(surf)
        if sp.dead:
            sparks.remove(sp)


def draw_float_texts(surf):
    for ft in float_texts[:]:
        ft.update()
        ft.draw(surf)
        if ft.dead:
            float_texts.remove(ft)


# ── Menu helpers ──────────────────────────────────────────────────────────────
class BloodSplat:
    def __init__(self):
        self.reset()

    def reset(self):
        self.x     = random.randint(WALL+20, WIDTH -WALL-20)
        self.y     = random.randint(WALL+20, HEIGHT-WALL-20)
        self.r     = random.randint(3, 10)
        self.alpha = random.randint(60, 140)
        self.age   = 0
        self.life  = random.randint(180, 400)

    def update(self):
        self.age += 1
        if self.age > self.life:
            self.reset()

    def draw(self, surf):
        fade = max(0, self.alpha - int(self.alpha * self.age / self.life))
        s = pygame.Surface((self.r*2, self.r*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*BLOOD_RED, fade), (self.r,self.r), self.r)
        surf.blit(s, (self.x-self.r, self.y-self.r))


class MenuButton:
    W, H = 260, 48

    def __init__(self, label, y):
        self.label   = label
        self.x       = WIDTH//2 - self.W//2
        self.y       = y
        self.hovered = False

    def update(self, mx, my):
        self.hovered = (self.x <= mx <= self.x+self.W and self.y <= my <= self.y+self.H)

    def draw(self, surf):
        col_bg     = (45,45,45)  if self.hovered else (25,25,25)
        col_border = HUD_GREEN   if self.hovered else MID_GRAY
        col_text   = WHITE       if self.hovered else (160,160,160)
        pygame.draw.rect(surf, col_bg,     (self.x,self.y,self.W,self.H), border_radius=4)
        pygame.draw.rect(surf, col_border, (self.x,self.y,self.W,self.H), 2, border_radius=4)
        if self.hovered:
            pygame.draw.rect(surf, HUD_GREEN, (self.x,self.y+6,4,self.H-12), border_radius=2)
        t = font_md.render(self.label, True, col_text)
        surf.blit(t, (self.x+self.W//2-t.get_width()//2, self.y+self.H//2-t.get_height()//2))

    def clicked(self, cx=None, cy=None):
        if cx is not None and cy is not None:
            return self.x <= cx <= self.x + self.W and self.y <= cy <= self.y + self.H
        return self.hovered



# ── Skin preview renderer ─────────────────────────────────────────────────────
def draw_skin_preview(surf, cx, cy, pskin, bskin, tick=0):
    """Draws a miniature version of the player using given skin at cx,cy."""
    wc    = tick * 0.06
    skin  = pskin["skin"]
    hair  = pskin["hair"]
    shirt = pskin["shirt"]
    shdrk = pskin["shirt_drk"]
    pants = pskin["pants"]
    pdrk  = pskin["pants_drk"]
    boot  = pskin["boot"]
    scale = 0.75   # slightly smaller for preview

    def s(v): return int(v * scale)

    # Legs — idle pose
    for side in (-1, 1):
        hpx, hpy = cx + s(side*5), cy + s(5)
        ftx, fty = cx + s(side*5), cy + s(17)
        pygame.draw.line(surf, pants, (hpx, hpy), (ftx, fty-s(6)), s(5))
        pygame.draw.line(surf, boot,  (hpx, hpy+s(6)), (ftx, fty), s(5))
        pygame.draw.ellipse(surf, boot, (ftx-s(4), fty-s(2), s(9), s(5)))

    # Torso
    pygame.draw.rect(surf, shirt, (cx-s(8), cy-s(8), s(16), s(14)), border_radius=s(3))
    pygame.draw.rect(surf, shdrk, (cx-s(8), cy-s(8), s(16), s(14)), 1, border_radius=s(3))

    # Left arm
    pygame.draw.line(surf, skin, (cx-s(8), cy-s(3)), (cx-s(13), cy+s(7)), s(4))
    # Right arm (holds bat if bskin not wood, else just arm)
    pygame.draw.line(surf, skin, (cx+s(8), cy-s(3)), (cx+s(14), cy+s(4)), s(4))
    # Guards — ensure correct dict types before access
    if "skin" not in pskin:
        pskin = PLAYER_SKINS[0]
        skin  = pskin["skin"]
        hair  = pskin["hair"]
        shirt = pskin["shirt"]
        shdrk = pskin["shirt_drk"]
        pants = pskin["pants"]
        pdrk  = pskin["pants_drk"]
        boot  = pskin["boot"]
    if "col" not in bskin:
        bskin = BAT_SKINS[0]
    bc = bskin["col"]; bd = bskin["drk"]
    pygame.draw.line(surf, bd, (cx+s(14), cy+s(2)), (cx+s(22), cy-s(10)), s(5))
    pygame.draw.line(surf, bc, (cx+s(14), cy+s(2)), (cx+s(22), cy-s(10)), s(3))
    pygame.draw.circle(surf, bskin["tip"], (cx+s(22), cy-s(10)), s(4))

    # Neck
    pygame.draw.line(surf, skin, (cx, cy-s(8)), (cx, cy-s(13)), s(4))
    # Head
    pygame.draw.circle(surf, skin, (cx, cy-s(18)), s(9))
    pygame.draw.circle(surf, (int(skin[0]*0.75), int(skin[1]*0.75), int(skin[2]*0.75)),
                       (cx, cy-s(18)), s(9), 1)
    # Hair
    hair_pts = [(cx-s(9), cy-s(19)), (cx-s(7), cy-s(25)),
                (cx, cy-s(27)),      (cx+s(7), cy-s(25)),
                (cx+s(9), cy-s(19)), (cx+s(6), cy-s(17)),
                (cx-s(6), cy-s(17))]
    pygame.draw.polygon(surf, hair, hair_pts)
    # Eyes
    pygame.draw.circle(surf, WHITE,       (cx-s(3), cy-s(19)), s(2))
    pygame.draw.circle(surf, WHITE,       (cx+s(3), cy-s(19)), s(2))
    pygame.draw.circle(surf, (30,30,80),  (cx-s(3), cy-s(19)), s(1))
    pygame.draw.circle(surf, (30,30,80),  (cx+s(3), cy-s(19)), s(1))


# ── Shop screen ───────────────────────────────────────────────────────────────
def shop_screen():
    data      = load_shop()
    scanlines = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for y in range(0, HEIGHT, 2):
        pygame.draw.line(scanlines, (0,0,0,30), (0,y), (WIDTH,y))
    btn_back  = MenuButton("< BACK", HEIGHT - 58)

    tab        = 0     # 0=player, 1=bat, 2=zombie
    scroll_y   = 0
    dragging   = False
    drag_start = 0

    TAB_Y    = 58
    GRID_TOP = 108     # where cards start
    GRID_BOT = HEIGHT - 80   # leave room for back button
    GRID_H   = GRID_BOT - GRID_TOP

    COLS     = 3
    CARD_W   = 210
    CARD_H   = 160
    GAP      = 10
    GRID_W   = COLS * CARD_W + (COLS-1) * GAP
    GRID_X   = WIDTH//2 - GRID_W//2

    tab_rects = [
        pygame.Rect(WIDTH//2 - 310, TAB_Y, 190, 36),
        pygame.Rect(WIDTH//2 - 95,  TAB_Y, 190, 36),
        pygame.Rect(WIDTH//2 + 120, TAB_Y, 190, 36),
    ]

    # Clip surface for the scrollable grid area
    clip_rect = pygame.Rect(0, GRID_TOP, WIDTH, GRID_H)

    while True:
        HUD_GREEN = get_theme()
        clock.tick(FPS)
        mx, my = pygame.mouse.get_pos()
        _sw, _sh = screen.get_size()
        mx = int(mx * WIDTH / _sw)
        my = int(my * HEIGHT / _sh)

        data      = load_shop()
        total     = data.get("total_score", 0)
        if tab == 0:
            items, ukey, ekey, udefault = PLAYER_SKINS, "unlocked_players", "player_skin",  "classic"
        elif tab == 1:
            items, ukey, ekey, udefault = BAT_SKINS,    "unlocked_bats",    "bat_skin",     "wood"
        else:
            items, ukey, ekey, udefault = ZOMBIE_SKINS, "unlocked_zombies", "zombie_skin",  "classic"
        unlocked  = data.get(ukey, [udefault])

        # Total content height
        rows         = math.ceil(len(items) / COLS)
        content_h    = rows * CARD_H + (rows-1) * GAP + 20
        max_scroll   = max(0, content_h - GRID_H)

        btn_back.update(mx, my)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: return
            if event.type == pygame.MOUSEWHEEL:
                scroll_y = max(0, min(max_scroll, scroll_y - event.y * 20))
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                cx = int(event.pos[0] * WIDTH / _sw)
                cy = int(event.pos[1] * HEIGHT / _sh)
                if btn_back.clicked(cx, cy): return
                # Tab switch
                for ti, tr in enumerate(tab_rects):
                    if tr.collidepoint(cx, cy):
                        tab = ti
                        scroll_y = 0
                # Card click (only if in grid area)
                if GRID_TOP <= cy <= GRID_BOT:
                    gy = cy - GRID_TOP + scroll_y
                    for i, item in enumerate(items):
                        col  = i % COLS
                        row  = i // COLS
                        crx  = GRID_X + col * (CARD_W + GAP)
                        cry  = row * (CARD_H + GAP)
                        cr   = pygame.Rect(crx, cry, CARD_W, CARD_H)
                        if cr.collidepoint(cx - 0, gy):
                            if item["id"] in unlocked:
                                data[ekey] = item["id"]
                                save_shop(data)

        # ── Draw ──
        draw_arena(canvas)
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0,0,0,155))
        canvas.blit(dim, (0,0))

        # Title
        title = font_lg.render("SHOP", True, HUD_GREEN)
        canvas.blit(title, (WIDTH//2 - title.get_width()//2, 16))
        ts_txt = font_sm.render(f"TOTAL SCORE:  {total}", True, (150,150,150))
        canvas.blit(ts_txt, (WIDTH//2 - ts_txt.get_width()//2, 40))

        # Tabs
        for ti, (tr, label) in enumerate(zip(tab_rects, ["PLAYER SKINS", "BAT SKINS", "ZOMBIE SKINS"])):
            active = (ti == tab)
            pygame.draw.rect(canvas, (40,60,40) if active else (20,20,20), tr, border_radius=4)
            pygame.draw.rect(canvas, HUD_GREEN  if active else MID_GRAY,   tr, 2, border_radius=4)
            t = font_sm.render(label, True, WHITE if active else (120,120,120))
            canvas.blit(t, (tr.x + tr.w//2 - t.get_width()//2,
                            tr.y + tr.h//2 - t.get_height()//2))

        # ── Scrollable grid ──
        # Draw to offscreen surface then clip-blit
        grid_surf = pygame.Surface((WIDTH, content_h + 40))
        grid_surf.fill((0,0,0,0))
        grid_surf.set_colorkey((1,2,3))  # won't use colorkey, just draw

        for i, item in enumerate(items):
            col  = i % COLS
            row  = i // COLS
            crx  = GRID_X + col * (CARD_W + GAP)
            cry  = row * (CARD_H + GAP)
            cr   = pygame.Rect(crx, cry, CARD_W, CARD_H)

            is_unlocked = item["id"] in unlocked
            is_equipped = data.get(ekey) == item["id"]
            hovered     = (cr.collidepoint(mx, GRID_TOP + cry - scroll_y + scroll_y)
                           and GRID_TOP <= my <= GRID_BOT
                           and cr.collidepoint(mx, my - GRID_TOP + scroll_y))

            # Card bg
            if is_equipped:
                bg = (25,55,25); border = HUD_GREEN
            elif is_unlocked:
                bg = (35,35,45) if hovered else (22,22,30)
                border = WHITE if hovered else (55,55,65)
            else:
                bg = (22,18,18); border = (55,35,35)

            pygame.draw.rect(grid_surf, bg,     cr, border_radius=8)
            pygame.draw.rect(grid_surf, border, cr, 2, border_radius=8)

            # Name — centred, clipped to card width
            name_col = WHITE if is_unlocked else (80,60,60)
            nt = font_md.render(item["name"], True, name_col)
            nx = crx + CARD_W//2 - nt.get_width()//2
            grid_surf.blit(nt, (nx, cry + 10))

            # Equipped badge
            if is_equipped:
                eq = font_sm.render("EQUIPPED", True, HUD_GREEN)
                grid_surf.blit(eq, (crx + 8, cry + 10))

            # Preview or lock
            if is_unlocked:
                active_pskin = next((s for s in PLAYER_SKINS if s["id"]==data.get("player_skin","classic")), PLAYER_SKINS[0])
                active_bskin = next((s for s in BAT_SKINS    if s["id"]==data.get("bat_skin","wood")),       BAT_SKINS[0])
                pskin = None
                bskin = active_bskin
                if tab == 0:
                    pskin = item; bskin = active_bskin
                elif tab == 1:
                    pskin = active_pskin; bskin = item
                else:
                    # Draw a zombie preview — always use a safe zombie skin dict
                    zs = next((s for s in ZOMBIE_SKINS if "body" in s and s.get("id") == item.get("id")), ZOMBIE_SKINS[0])
                    zx, zy = crx + CARD_W//2, cry + CARD_H//2 + 10
                    zbody = zs["body"]; zdrk = zs["drk"]; zeye = zs["eye"]
                    zshirt = tuple(max(0,c-20) for c in zbody)
                    pygame.draw.ellipse(grid_surf, (5,5,5), (zx-12, zy+9, 22, 7))
                    for side in (-1,1):
                        pygame.draw.line(grid_surf, zdrk, (zx+side*4, zy+3), (zx+side*5, zy+12), 4)
                    pygame.draw.rect(grid_surf, zshirt, (zx-5, zy-5, 10, 9), border_radius=2)
                    pygame.draw.line(grid_surf, zbody, (zx-5, zy-3), (zx-14, zy-7), 3)
                    pygame.draw.line(grid_surf, zbody, (zx+5, zy-3), (zx+14, zy-6), 3)
                    pygame.draw.circle(grid_surf, zbody, (zx, zy-12), 7)
                    pygame.draw.circle(grid_surf, zdrk,  (zx, zy-12), 7, 1)
                    pygame.draw.circle(grid_surf, zeye, (zx-3, zy-13), 2)
                    pygame.draw.circle(grid_surf, zeye, (zx+3, zy-13), 2)
                    pskin = None
                if pskin is not None:
                    if "skin" not in pskin: pskin = PLAYER_SKINS[0]
                    if "col"  not in bskin: bskin = BAT_SKINS[0]
                    draw_skin_preview(grid_surf, crx + 60, cry + CARD_H//2 + 14, pskin, bskin)
            else:
                # Lock icon
                lx, ly = crx + CARD_W//2, cry + CARD_H//2 - 4
                pygame.draw.rect(grid_surf, (70,55,30), (lx-14, ly-4, 28, 22), border_radius=3)
                pygame.draw.arc(grid_surf,  (70,55,30), (lx-12, ly-18, 24, 26), 0, math.pi, 4)
                pygame.draw.rect(grid_surf, (50,38,18), (lx-14, ly-4, 28, 22), 1, border_radius=3)

            # Cost / equip hint — always inside card
            if is_unlocked:
                if not is_equipped:
                    hint_col = (100,200,100) if hovered else (60,110,60)
                    ht = font_sm.render("CLICK TO EQUIP", True, hint_col)
                    hx = crx + CARD_W//2 - ht.get_width()//2
                    grid_surf.blit(ht, (hx, cry + CARD_H - 22))
            else:
                need  = max(0, item["cost"] - total)
                lt_str = f"NEED {need} PTS"
                lt = font_sm.render(lt_str, True, (150,70,70))
                # Shrink text if it overflows
                if lt.get_width() > CARD_W - 16:
                    lt = font_sm.render(f"{need} PTS", True, (150,70,70))
                lx2 = crx + CARD_W//2 - lt.get_width()//2
                grid_surf.blit(lt, (lx2, cry + CARD_H - 22))

        # Blit clipped grid onto canvas
        canvas.blit(grid_surf, (0, GRID_TOP), (0, scroll_y, WIDTH, GRID_H))

        # Scroll indicator
        if max_scroll > 0:
            bar_h    = max(30, int(GRID_H * GRID_H / content_h))
            bar_y    = GRID_TOP + int((GRID_H - bar_h) * scroll_y / max_scroll)
            pygame.draw.rect(canvas, (50,50,50),  (WIDTH-8, GRID_TOP, 4, GRID_H), border_radius=2)
            pygame.draw.rect(canvas, (120,120,120),(WIDTH-8, bar_y,   4, bar_h),  border_radius=2)

        # Bottom bar
        pygame.draw.rect(canvas, (15,15,15), (0, GRID_BOT, WIDTH, HEIGHT - GRID_BOT))
        pygame.draw.line(canvas, (40,40,40), (0, GRID_BOT), (WIDTH, GRID_BOT), 1)

        btn_back.draw(canvas)
        canvas.blit(scanlines, (0,0))
        pygame.mouse.set_visible(True)
        _sc = pygame.transform.scale(canvas, screen.get_size())
        screen.blit(_sc, (0, 0))
        pygame.display.flip()



# ── Reset account confirm popup ───────────────────────────────────────────────
def reset_account_popup():
    tick = 0
    while True:
        HUD_GREEN = get_theme()
        clock.tick(FPS)
        tick += 1
        mx, my = pygame.mouse.get_pos()
        _sw, _sh = screen.get_size()
        mx = int(mx * WIDTH / _sw)
        my = int(my * HEIGHT / _sh)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                cx = int(event.pos[0] * WIDTH / _sw)
                cy = int(event.pos[1] * HEIGHT / _sh)
                bw, bh = 160, 44
                conf_x = WIDTH//2 - bw - 10
                conf_y = HEIGHT//2 + 30
                if conf_x <= cx <= conf_x+bw and conf_y <= cy <= conf_y+bh:
                    return True
                canc_x = WIDTH//2 + 10
                canc_y = HEIGHT//2 + 30
                if canc_x <= cx <= canc_x+bw and canc_y <= cy <= canc_y+bh:
                    return False

        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        canvas.blit(overlay, (0, 0))

        bw2, bh2 = 420, 200
        bx, by = WIDTH//2 - bw2//2, HEIGHT//2 - bh2//2
        pygame.draw.rect(canvas, (25, 18, 18), (bx, by, bw2, bh2), border_radius=8)
        pygame.draw.rect(canvas, RED,           (bx, by, bw2, bh2), 2, border_radius=8)

        t1 = font_lg.render("RESET ACCOUNT?", True, RED)
        canvas.blit(t1, (WIDTH//2 - t1.get_width()//2, by + 20))
        t2 = font_sm.render("This will delete ALL progress,", True, (180,180,180))
        t3 = font_sm.render("scores, skins and settings.", True, (180,180,180))
        canvas.blit(t2, (WIDTH//2 - t2.get_width()//2, by + 72))
        canvas.blit(t3, (WIDTH//2 - t3.get_width()//2, by + 94))

        bw, bh = 160, 44
        conf_x = WIDTH//2 - bw - 10
        conf_y = HEIGHT//2 + 30
        conf_hov = conf_x <= mx <= conf_x+bw and conf_y <= my <= conf_y+bh
        pygame.draw.rect(canvas, (80,10,10) if conf_hov else (50,5,5), (conf_x, conf_y, bw, bh), border_radius=6)
        pygame.draw.rect(canvas, RED, (conf_x, conf_y, bw, bh), 2, border_radius=6)
        ct = font_md.render("RESET", True, WHITE)
        canvas.blit(ct, (conf_x + bw//2 - ct.get_width()//2, conf_y + bh//2 - ct.get_height()//2))

        canc_x = WIDTH//2 + 10
        canc_y = HEIGHT//2 + 30
        canc_hov = canc_x <= mx <= canc_x+bw and canc_y <= my <= canc_y+bh
        pygame.draw.rect(canvas, (40,40,40) if canc_hov else (25,25,25), (canc_x, canc_y, bw, bh), border_radius=6)
        pygame.draw.rect(canvas, MID_GRAY, (canc_x, canc_y, bw, bh), 2, border_radius=6)
        ct2 = font_md.render("CANCEL", True, WHITE)
        canvas.blit(ct2, (canc_x + bw//2 - ct2.get_width()//2, canc_y + bh//2 - ct2.get_height()//2))

        _sc = pygame.transform.scale(canvas, screen.get_size())
        screen.blit(_sc, (0, 0))
        pygame.display.flip()


# ── Settings screen ───────────────────────────────────────────────────────────
def settings_screen():
    data      = load_settings()
    scanlines = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for y in range(0, HEIGHT, 2):
        pygame.draw.line(scanlines, (0,0,0,30), (0,y), (WIDTH,y))
    btn_back  = MenuButton("< BACK", 530)
    dragging  = None

    CARD_X, CARD_Y, CARD_W, CARD_H, CARD_R = WIDTH//2-200, 90, 400, 310, 12
    SLDR_X  = CARD_X + 20
    SLDR_W  = CARD_W - 60
    MUS_Y   = CARD_Y + 100
    SFX_Y   = CARD_Y + 180

    def draw_slider(surf, y, label, value, active):
        lt = font_sm.render(label, True, WHITE)
        surf.blit(lt, (SLDR_X, y - 22))
        pygame.draw.rect(surf, (50,50,50), (SLDR_X, y, SLDR_W, 6), border_radius=3)
        fill_w = int(SLDR_W * value)
        pygame.draw.rect(surf, HUD_GREEN if active else (60,180,100), (SLDR_X, y, fill_w, 6), border_radius=3)
        kx = SLDR_X + fill_w
        pygame.draw.circle(surf, WHITE,    (kx, y+3), 10)
        pygame.draw.circle(surf, HUD_GREEN if active else MID_GRAY, (kx, y+3), 10, 2)
        vt = font_sm.render(f"{int(value*100)}%", True, (150,150,150))
        surf.blit(vt, (SLDR_X + SLDR_W + 10, y - 6))

    while True:
        HUD_GREEN = get_theme()
        clock.tick(FPS)
        mx, my = pygame.mouse.get_pos()
        _sw, _sh = screen.get_size()
        mx = int(mx * WIDTH / _sw)
        my = int(my * HEIGHT / _sh)

        btn_back.update(mx, my)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    save_settings(data); apply_settings(data); return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                cx = int(event.pos[0] * WIDTH / _sw)
                cy = int(event.pos[1] * HEIGHT / _sh)
                if btn_back.clicked(cx, cy):
                    save_settings(data); apply_settings(data); return
                # Reset account button
                reset_rect2 = pygame.Rect(CARD_X + 20, CARD_Y + CARD_H + 16, CARD_W - 40, 38)
                if reset_rect2.collidepoint(cx, cy):
                    if reset_account_popup():
                        # Delete all save files
                        for f in (SCORES_FILE, SHOP_FILE, SETTINGS_FILE):
                            try: os.remove(f)
                            except: pass
                        data = load_settings()
                        return
                if abs(cy - MUS_Y - 3) < 16 and SLDR_X <= cx <= SLDR_X + SLDR_W + 20:
                    dragging = "music"
                elif abs(cy - SFX_Y - 3) < 16 and SLDR_X <= cx <= SLDR_X + SLDR_W + 20:
                    dragging = "sfx"
                # Theme dot click
                dot_r    = 14
                dot_gap  = 8
                dots_w   = len(THEMES) * (dot_r*2 + dot_gap) - dot_gap
                dot_start= CARD_X + CARD_W//2 - dots_w//2
                for ti in range(len(THEMES)):
                    dx = dot_start + ti * (dot_r*2 + dot_gap) + dot_r
                    dy = CARD_Y + 282
                    if math.hypot(cx - dx, cy - dy) <= dot_r + 4:
                        data["theme"] = ti
                        save_settings(data)
                        break
            if event.type == pygame.MOUSEBUTTONUP:
                dragging = None
            if event.type == pygame.MOUSEMOTION and dragging:
                raw_cx = int(pygame.mouse.get_pos()[0] * WIDTH / _sw)
                val = max(0.0, min(1.0, (raw_cx - SLDR_X) / SLDR_W))
                if dragging == "music":
                    data["music_vol"] = round(val, 2)
                    if MUSIC_FILE: pygame.mixer.music.set_volume(val)
                elif dragging == "sfx":
                    data["sfx_vol"] = round(val, 2)
                    for snd in SOUNDS.values(): snd.set_volume(val)

        # ── Draw ──
        draw_arena(canvas)
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0,0,0,160))
        canvas.blit(dim, (0,0))

        title = font_lg.render("SETTINGS", True, WHITE)
        canvas.blit(title, (WIDTH//2 - title.get_width()//2, 30))
        pygame.draw.rect(canvas, MID_GRAY, (WIDTH//2-100, 65, 200, 1))

        # Card
        card_surf = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
        card_surf.fill((20, 22, 28, 220))
        canvas.blit(card_surf, (CARD_X, CARD_Y))
        pygame.draw.rect(canvas, (45,47,55), (CARD_X, CARD_Y, CARD_W, CARD_H), 2, border_radius=CARD_R)

        ct = font_md.render("Audio", True, WHITE)
        canvas.blit(ct, (CARD_X + 20, CARD_Y + 18))
        pygame.draw.rect(canvas, (45,47,55), (CARD_X + 10, CARD_Y + 50, CARD_W - 20, 1))

        draw_slider(canvas, MUS_Y, "Music Volume", data.get("music_vol", 0.4), dragging=="music")
        draw_slider(canvas, SFX_Y, "SFX Volume",   data.get("sfx_vol",   0.35), dragging=="sfx")

        # Theme row
        pygame.draw.rect(canvas, (45,47,55), (CARD_X + 10, CARD_Y + 230, CARD_W - 20, 1))
        tt = font_sm.render("App Theme", True, WHITE)
        canvas.blit(tt, (CARD_X + 20, CARD_Y + 250))
        cur_theme = data.get("theme", 0)
        dot_r     = 14
        dot_gap   = 8
        dots_w    = len(THEMES) * (dot_r*2 + dot_gap) - dot_gap
        dot_start = CARD_X + CARD_W//2 - dots_w//2
        for ti, tcol in enumerate(THEMES):
            dx = dot_start + ti * (dot_r*2 + dot_gap) + dot_r
            dy = CARD_Y + 282
            pygame.draw.circle(canvas, tcol, (dx, dy), dot_r)
            if ti == cur_theme:
                pygame.draw.circle(canvas, WHITE, (dx, dy), dot_r, 3)

        # Reset account button
        reset_rect = pygame.Rect(CARD_X + 20, CARD_Y + CARD_H + 16, CARD_W - 40, 38)
        reset_hov  = reset_rect.collidepoint(mx, my)
        pygame.draw.rect(canvas, (60,15,15) if reset_hov else (35,10,10), reset_rect, border_radius=6)
        pygame.draw.rect(canvas, RED if reset_hov else (100,30,30), reset_rect, 2, border_radius=6)
        rt = font_sm.render("RESET ACCOUNT", True, RED if reset_hov else (120,50,50))
        canvas.blit(rt, (reset_rect.x + reset_rect.w//2 - rt.get_width()//2,
                         reset_rect.y + reset_rect.h//2 - rt.get_height()//2))

        credit = font_sm.render("Made by Milos Mitrovic", True, (60,60,60))
        canvas.blit(credit, (WIDTH//2 - credit.get_width()//2, HEIGHT - 22))

        btn_back.draw(canvas)
        canvas.blit(scanlines, (0,0))
        pygame.mouse.set_visible(True)
        _sc = pygame.transform.scale(canvas, screen.get_size())
        screen.blit(_sc, (0, 0))
        pygame.display.flip()


# ── Help screen ───────────────────────────────────────────────────────────────
def help_screen():
    scanlines = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for y in range(0, HEIGHT, 2):
        pygame.draw.line(scanlines, (0,0,0,30), (0,y), (WIDTH,y))
    btn_back = MenuButton("< BACK", 530)

    sections = [
        ("OBJECTIVE",  ["Survive endless waves of zombies.",
                        "Each wave gets faster and bigger.",
                        "Every 5th wave spawns a BOSS."]),
        ("CONTROLS",   ["WASD        —  Move",
                        "MOUSE       —  Aim",
                        "LEFT CLICK  —  Shoot",
                        "RIGHT CLICK —  Bat swing",
                        "P           —  Pause"]),
        ("SCORING",    ["Gun kill    —  10pts x wave",
                        "Bat kill    —  20pts x wave  (2x bonus!)",
                        "Boss kill   —  200pts x wave",
                        "Score unlocks skins in the Shop."]),
        ("TIPS",       ["Bat kills score double — get close!",
                        "Boss charges when within 200px.",
                        "Red vignette means low HP."]),
    ]

    while True:
        HUD_GREEN = get_theme()
        clock.tick(FPS)
        mx, my = pygame.mouse.get_pos()
        _sw, _sh = screen.get_size()
        mx = int(mx * WIDTH / _sw)
        my = int(my * HEIGHT / _sh)

        btn_back.update(mx, my)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                cx = int(event.pos[0] * WIDTH / _sw)
                cy = int(event.pos[1] * HEIGHT / _sh)
                if btn_back.clicked(cx, cy): return

        draw_arena(canvas)
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0,0,0,160))
        canvas.blit(dim, (0,0))

        title = font_lg.render("HOW TO PLAY", True, HUD_GREEN)
        canvas.blit(title, (WIDTH//2 - title.get_width()//2, 22))
        pygame.draw.rect(canvas, HUD_GREEN, (WIDTH//2-120, 60, 240, 2))

        col_x = [60, 420]
        col_y = [76, 76]
        for si, (heading, lines2) in enumerate(sections):
            cx2 = col_x[si % 2]
            cy2 = col_y[si % 2]
            ht = font_md.render(heading, True, HUD_GREEN)
            canvas.blit(ht, (cx2, cy2))
            pygame.draw.rect(canvas, HUD_GREEN, (cx2, cy2 + ht.get_height() + 2, 140, 1))
            for li, line in enumerate(lines2):
                lt = font_sm.render(line, True, (180,180,180))
                canvas.blit(lt, (cx2 + 6, cy2 + ht.get_height() + 10 + li * 22))
            col_y[si % 2] += ht.get_height() + 10 + len(lines2) * 22 + 24

        pygame.draw.line(canvas, (50,50,50), (WIDTH//2, 70), (WIDTH//2, 490), 1)

        btn_back.draw(canvas)

        credit = font_sm.render("Made by Milos Mitrovic", True, (70,70,70))
        canvas.blit(credit, (WIDTH//2 - credit.get_width()//2, HEIGHT - 20))

        canvas.blit(scanlines, (0,0))
        pygame.mouse.set_visible(True)
        _sc = pygame.transform.scale(canvas, screen.get_size())
        screen.blit(_sc, (0, 0))
        pygame.display.flip()


# ── Main Menu ─────────────────────────────────────────────────────────────────
def main_menu():
    splats    = [BloodSplat() for _ in range(18)]
    play_menu_music()
    btn_play    = MenuButton("PLAY",     210)
    btn_scores  = MenuButton("SCORES",   268)
    btn_shop    = MenuButton("SHOP",     326)
    btn_settings= MenuButton("SETTINGS", 384)
    btn_quit    = MenuButton("QUIT",     442)
    scanlines = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for y in range(0, HEIGHT, 2):
        pygame.draw.line(scanlines, (0,0,0,30), (0,y), (WIDTH,y))
    title_tick = 0

    while True:
        dt = clock.tick(FPS)
        HUD_GREEN = get_theme()
        mx, my = pygame.mouse.get_pos()
        _sw, _sh = screen.get_size()
        mx = int(mx * WIDTH / _sw)
        my = int(my * HEIGHT / _sh)
        title_tick += dt

        btn_play.update(mx, my)
        btn_scores.update(mx, my)
        btn_shop.update(mx, my)
        btn_settings.update(mx, my)
        btn_quit.update(mx, my)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                cx = int(event.pos[0] * WIDTH / _sw)
                cy = int(event.pos[1] * HEIGHT / _sh)
                btn_play.update(cx, cy)
                btn_scores.update(cx, cy)
                btn_shop.update(cx, cy)
                btn_settings.update(cx, cy)
                btn_quit.update(cx, cy)
                if HELP_BTN_RECT.collidepoint(cx, cy): help_screen()
                elif btn_play.clicked(cx,cy):     stop_menu_music(); return
                elif btn_scores.clicked(cx,cy):   leaderboard_screen()
                elif btn_shop.clicked(cx,cy):     shop_screen()
                elif btn_settings.clicked(cx,cy): settings_screen()
                elif btn_quit.clicked(cx,cy):     pygame.quit(); sys.exit()
        for sp in splats: sp.update()

        draw_arena(canvas)
        for sp in splats: sp.draw(canvas)
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0,0,0,140))
        canvas.blit(dim, (0,0))
        pulse = int(4 * math.sin(title_tick / 400))
        ts = font_xl.render("ZOMBIE RUNNER", True, HUD_GREEN)
        canvas.blit(ts, (WIDTH//2-ts.get_width()//2, 110+pulse))
        pygame.draw.rect(canvas, HUD_GREEN, (WIDTH//2-140, 178, 280, 3))
        sub = font_sm.render("ZOMBIE WAVE SURVIVAL", True, MID_GRAY)
        canvas.blit(sub, (WIDTH//2-sub.get_width()//2, 188))
        btn_play.draw(canvas)
        btn_scores.draw(canvas)
        btn_shop.draw(canvas)
        btn_settings.draw(canvas)
        btn_quit.draw(canvas)
        ver = font_sm.render("v0.8", True, (40,40,40))
        canvas.blit(ver, (WIDTH-ver.get_width()-12, HEIGHT-22))
        credit = font_sm.render("Made by Milos Mitrovic", True, (55,55,55))
        canvas.blit(credit, (WIDTH//2 - credit.get_width()//2, HEIGHT-22))
        canvas.blit(scanlines, (0,0))
        # ? help button — drawn on top of everything
        _hov = HELP_BTN_RECT.collidepoint(mx, my)
        _hcx = HELP_BTN_RECT.centerx
        _hcy = HELP_BTN_RECT.centery
        _hr  = HELP_BTN_RECT.w // 2
        pygame.draw.circle(canvas, (80,80,80) if _hov else (50,50,50), (_hcx,_hcy), _hr)
        pygame.draw.circle(canvas, HUD_GREEN  if _hov else WHITE,       (_hcx,_hcy), _hr, 2)
        _qt = font_md.render("?", True, WHITE)
        canvas.blit(_qt, (_hcx - _qt.get_width()//2, _hcy - _qt.get_height()//2))
        pygame.mouse.set_visible(True)
        _sc = pygame.transform.scale(canvas, screen.get_size())
        screen.blit(_sc, (0, 0))
        pygame.display.flip()


# ── Name entry ────────────────────────────────────────────────────────────────
def name_entry_screen(score, wave):
    """Type up to 5-letter name then confirm. Returns name string."""
    name      = []
    splats    = [BloodSplat() for _ in range(24)]
    scanlines = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for y in range(0, HEIGHT, 2):
        pygame.draw.line(scanlines, (0,0,0,30), (0,y), (WIDTH,y))
    cursor_tick = 0

    while True:
        clock.tick(FPS)
        HUD_GREEN = get_theme()
        cursor_tick += 1

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "AAAAA"
                if event.key == pygame.K_BACKSPACE and name:
                    name.pop()
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and len(name) >= 1:
                    return "".join(name)
                elif len(name) < 5:
                    ch = event.unicode.upper()
                    if ch.isalpha() or ch.isdigit():
                        name.append(ch)

        for sp in splats: sp.update()

        draw_arena(canvas)
        for sp in splats: sp.draw(canvas)
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0,0,0,160))
        canvas.blit(dim, (0,0))

        go = font_xl.render("YOU DIED", True, RED)
        canvas.blit(go, (WIDTH//2 - go.get_width()//2, 80))
        pygame.draw.rect(canvas, BLOOD_RED, (WIDTH//2-120, 148, 240, 3))

        sc = font_md.render(f"SCORE  {score:06}", True, WHITE)
        canvas.blit(sc, (WIDTH//2 - sc.get_width()//2, 165))
        wv = font_md.render(f"WAVE  {wave}", True, (160,160,160))
        canvas.blit(wv, (WIDTH//2 - wv.get_width()//2, 195))

        rank = get_rank(score)
        rk = font_md.render(f"RANK  #{rank}", True, HUD_GREEN if rank <= 3 else WHITE)
        canvas.blit(rk, (WIDTH//2 - rk.get_width()//2, 225))

        # Name input box
        prompt = font_sm.render("ENTER YOUR NAME  (UP TO 5 LETTERS)", True, MID_GRAY)
        canvas.blit(prompt, (WIDTH//2 - prompt.get_width()//2, 268))

        box_x, box_y, box_w, box_h = WIDTH//2 - 110, 288, 220, 52
        pygame.draw.rect(canvas, DARK_GRAY, (box_x, box_y, box_w, box_h), border_radius=4)
        pygame.draw.rect(canvas, HUD_GREEN, (box_x, box_y, box_w, box_h), 2, border_radius=4)

        # 5 letter slots
        slot_w2 = (box_w - 20) // 5
        for i in range(5):
            sx = box_x + 10 + i * slot_w2
            ch = name[i] if i < len(name) else ""
            if i == len(name) and cursor_tick % 60 < 30:
                pygame.draw.rect(canvas, HUD_GREEN, (sx + 4, box_y + 12, slot_w2 - 8, 3))
            lt = font_lg.render(ch, True, WHITE)
            canvas.blit(lt, (sx + slot_w2//2 - lt.get_width()//2, box_y + 8))

        if len(name) >= 1:
            conf = font_sm.render("PRESS ENTER TO CONFIRM", True, HUD_GREEN)
            canvas.blit(conf, (WIDTH//2 - conf.get_width()//2, 352))
        else:
            conf = font_sm.render("BACKSPACE TO DELETE", True, (60,60,60))
            canvas.blit(conf, (WIDTH//2 - conf.get_width()//2, 352))

        canvas.blit(scanlines, (0,0))
        pygame.mouse.set_visible(True)
        _sc = pygame.transform.scale(canvas, screen.get_size())
        screen.blit(_sc, (0, 0))
        pygame.display.flip()


# ── Delete confirm popup ─────────────────────────────────────────────────────
def delete_confirm_popup(entry_name, entry_score):
    """Returns True if user confirms delete, False otherwise."""
    typed  = []
    tick   = 0
    msg    = f"TYPE YOUR NAME TO DELETE  ({entry_name}  {entry_score:06})"

    while True:
        clock.tick(FPS)
        tick += 1
        mx, my = pygame.mouse.get_pos()
        _sw, _sh = screen.get_size()
        mx = int(mx * WIDTH / _sw)
        my = int(my * HEIGHT / _sh)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key == pygame.K_BACKSPACE and typed:
                    typed.pop()
                elif event.key == pygame.K_RETURN:
                    if "".join(typed).upper() == entry_name.upper():
                        return True
                    return False
                elif len(typed) < 5:
                    ch = event.unicode.upper()
                    if ch.isalpha() or ch.isdigit():
                        typed.append(ch)

        # Dim overlay
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        canvas.blit(overlay, (0, 0))

        # Popup box
        bw, bh = 440, 180
        bx, by = WIDTH//2 - bw//2, HEIGHT//2 - bh//2
        pygame.draw.rect(canvas, (25, 25, 25),  (bx, by, bw, bh), border_radius=6)
        pygame.draw.rect(canvas, RED,            (bx, by, bw, bh), 2, border_radius=6)

        t1 = font_sm.render("DELETE SCORE?", True, RED)
        canvas.blit(t1, (WIDTH//2 - t1.get_width()//2, by + 16))

        t2 = font_sm.render(msg, True, (130, 130, 130))
        canvas.blit(t2, (WIDTH//2 - t2.get_width()//2, by + 44))

        # Input box
        ibx, iby = WIDTH//2 - 60, by + 72
        pygame.draw.rect(canvas, DARK_GRAY, (ibx, iby, 120, 40), border_radius=4)
        pygame.draw.rect(canvas, RED,       (ibx, iby, 120, 40), 1, border_radius=4)
        typed_str = "".join(typed)
        # cursor blink
        display_str = typed_str + ("|" if tick % 60 < 30 else " ")
        it = font_lg.render(display_str, True, WHITE)
        canvas.blit(it, (WIDTH//2 - it.get_width()//2, iby + 5))

        hint1 = font_sm.render("ENTER to confirm   ESC to cancel", True, (60, 60, 60))
        canvas.blit(hint1, (WIDTH//2 - hint1.get_width()//2, by + 126))

        # Live match feedback
        if typed_str:
            match = typed_str.upper() == entry_name.upper()[:len(typed_str)]
            col   = HUD_GREEN if match else RED
            fb    = font_sm.render("OK MATCH" if len(typed_str)==len(entry_name) and match else ("..." if match else "XX WRONG"), True, col)
            canvas.blit(fb, (WIDTH//2 - fb.get_width()//2, by + 148))

        _sc = pygame.transform.scale(canvas, screen.get_size())
        screen.blit(_sc, (0, 0))
        pygame.display.flip()


# ── Leaderboard screen ────────────────────────────────────────────────────────
def leaderboard_screen(highlight_name=None, highlight_score=None):
    splats       = [BloodSplat() for _ in range(16)]
    btn_menu     = MenuButton("< MAIN MENU", 510)
    scanlines    = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for y in range(0, HEIGHT, 2):
        pygame.draw.line(scanlines, (0,0,0,30), (0,y), (WIDTH,y))
    scores       = load_scores()
    hovered_del  = -1   # index of row whose delete btn is hovered

    # Pre-build delete button rects per row
    def del_rects():
        return [pygame.Rect(660, 110 + i*34, 30, 22) for i in range(len(scores[:10]))]

    while True:
        clock.tick(FPS)
        HUD_GREEN = get_theme()
        mx, my = pygame.mouse.get_pos()
        _sw, _sh = screen.get_size()
        mx = int(mx * WIDTH / _sw)
        my = int(my * HEIGHT / _sh)
        drects = del_rects()

        # Hover detection
        hovered_del = -1
        for i, dr in enumerate(drects):
            if dr.collidepoint(mx, my):
                hovered_del = i

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:   return "menu"
                if event.key == pygame.K_RETURN:   return "retry"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                cx = int(event.pos[0] * WIDTH / _sw)
                cy = int(event.pos[1] * HEIGHT / _sh)
                if btn_menu.clicked(cx,cy):  return "menu"
                # Delete button clicked?
                for i, dr in enumerate(drects):
                    if dr.collidepoint(mx, my) and i < len(scores):
                        entry = scores[i]
                        if delete_confirm_popup(entry["name"], entry["score"]):
                            scores.pop(i)
                            with open(SCORES_FILE, "w") as f:
                                json.dump(scores, f)
                            # Reset highlight if deleted entry was the new one
                            if (entry["score"] == highlight_score and
                                    entry["name"] == highlight_name):
                                highlight_score = None
                                highlight_name  = None
                        break

        btn_menu.update(mx, my)
        for sp in splats: sp.update()

        draw_arena(canvas)
        for sp in splats: sp.draw(canvas)
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0,0,0,155))
        canvas.blit(dim, (0,0))

        title = font_lg.render("HIGH SCORES", True, HUD_GREEN)
        canvas.blit(title, (WIDTH//2 - title.get_width()//2, 30))
        pygame.draw.rect(canvas, HUD_GREEN, (WIDTH//2-120, 68, 240, 2))

        # Column headers
        canvas.blit(font_sm.render("RANK",  True, MID_GRAY), (120, 85))
        canvas.blit(font_sm.render("NAME",  True, MID_GRAY), (220, 85))
        canvas.blit(font_sm.render("SCORE", True, MID_GRAY), (340, 85))
        canvas.blit(font_sm.render("WAVE",  True, MID_GRAY), (500, 85))
        pygame.draw.rect(canvas, MID_GRAY, (100, 102, 600, 1))

        rank_colors = [(255,210,50),(180,180,180),(200,140,80)]

        drects = del_rects()
        for i, entry in enumerate(scores[:10]):
            row_y   = 112 + i * 34
            is_new  = (highlight_score is not None and
                       entry["score"] == highlight_score and
                       entry["name"]  == highlight_name)
            row_col = rank_colors[i] if i < 3 else (WHITE if is_new else (140,140,140))

            if is_new:
                pygame.draw.rect(canvas, (30,60,30), (100, row_y-2, 560, 30), border_radius=3)
                pygame.draw.rect(canvas, HUD_GREEN,  (100, row_y-2, 560, 30), 1, border_radius=3)

            canvas.blit(font_sm.render(f"#{i+1}",             True, row_col), (120, row_y))
            canvas.blit(font_md.render(entry["name"],          True, row_col), (214, row_y-2))
            canvas.blit(font_md.render(f"{entry['score']:06}", True, row_col), (334, row_y-2))
            canvas.blit(font_sm.render(f"W{entry['wave']}",   True, row_col), (500, row_y))

            # Delete button
            dr      = drects[i]
            del_hov = (hovered_del == i)
            pygame.draw.rect(canvas, (60,20,20) if del_hov else (35,15,15), dr, border_radius=3)
            pygame.draw.rect(canvas, RED if del_hov else (80,30,30),         dr, 1, border_radius=3)
            xt = font_sm.render("X", True, RED if del_hov else (100,50,50))
            canvas.blit(xt, (dr.x + dr.w//2 - xt.get_width()//2,
                             dr.y + dr.h//2 - xt.get_height()//2))

        if not scores:
            empty = font_md.render("NO SCORES YET — BE THE FIRST!", True, MID_GRAY)
            canvas.blit(empty, (WIDTH//2 - empty.get_width()//2, 200))

        btn_menu.draw(canvas)
        canvas.blit(scanlines, (0,0))
        pygame.mouse.set_visible(True)
        _sc = pygame.transform.scale(canvas, screen.get_size())
        screen.blit(_sc, (0, 0))
        pygame.display.flip()


# ── Game Over ─────────────────────────────────────────────────────────────────
def game_over_screen(score, wave):
    player_name = name_entry_screen(score, wave)
    save_score(player_name, score, wave)
    return leaderboard_screen(highlight_name=player_name, highlight_score=score)


# ── Pause screen ─────────────────────────────────────────────────────────────
def pause_screen():
    btn_resume = MenuButton("> RESUME",   260)
    btn_menu   = MenuButton("< MAIN MENU", 325)
    scanlines  = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for y in range(0, HEIGHT, 2):
        pygame.draw.line(scanlines, (0,0,0,30), (0,y), (WIDTH,y))

    while True:
        clock.tick(FPS)
        HUD_GREEN = get_theme()
        mx, my = pygame.mouse.get_pos()
        _sw, _sh = screen.get_size()
        mx = int(mx * WIDTH / _sw)
        my = int(my * HEIGHT / _sh)

        btn_resume.update(mx, my)
        btn_menu.update(mx, my)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_p:
                    return "resume"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                cx = int(event.pos[0] * WIDTH / _sw)
                cy = int(event.pos[1] * HEIGHT / _sh)
                if btn_resume.clicked(cx,cy): return "resume"
                if btn_menu.clicked(cx,cy):   return "menu"

        # Dim overlay over the frozen game world
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 160))
        canvas.blit(dim, (0, 0))

        title = font_lg.render("PAUSED", True, WHITE)
        canvas.blit(title, (WIDTH//2 - title.get_width()//2, 170))
        pygame.draw.rect(canvas, MID_GRAY, (WIDTH//2 - 80, 208, 160, 2))

        btn_resume.draw(canvas)
        btn_menu.draw(canvas)

        hint = font_sm.render("ESC or P to resume", True, (55,55,55))
        canvas.blit(hint, (WIDTH//2 - hint.get_width()//2, HEIGHT - 28))
        canvas.blit(scanlines, (0, 0))
        pygame.mouse.set_visible(True)
        _sc = pygame.transform.scale(canvas, screen.get_size())
        screen.blit(_sc, (0, 0))
        pygame.display.flip()


# ── Game ──────────────────────────────────────────────────────────────────────
def game():
    global sparks, float_texts
    sparks      = []
    float_texts = []

    player = Player()
    waves  = WaveManager()
    score  = 0
    pygame.mouse.set_visible(False)
    world  = pygame.Surface((WIDTH, HEIGHT))

    while True:
        dt = clock.tick(FPS)
        HUD_GREEN = get_theme()
        mx, my = pygame.mouse.get_pos()
        _sw, _sh = screen.get_size()
        mx = int(mx * WIDTH / _sw)
        my = int(my * HEIGHT / _sh)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.mouse.set_visible(True)
                    return "menu"
                if event.key == pygame.K_p:
                    draw_arena(world)
                    waves.draw(world)
                    draw_sparks(world)
                    player.draw(world)
                    draw_float_texts(world)
                    player.draw_hud(world)
                    draw_top_hud(world, waves.wave, score, waves.remaining(),
                                 waves.between, waves.between_timer, waves.is_boss_wave)
                    canvas.fill(BLACK)
                    canvas.blit(world, (0, 0))
                    result = pause_screen()
                    pygame.mouse.set_visible(False)
                    if result == "menu":
                        return "menu"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if PAUSE_BTN_RECT.collidepoint(int(event.pos[0]*WIDTH/screen.get_width()), int(event.pos[1]*HEIGHT/screen.get_height())):
                    draw_arena(world)
                    waves.draw(world)
                    draw_sparks(world)
                    player.draw(world)
                    draw_float_texts(world)
                    player.draw_hud(world)
                    draw_top_hud(world, waves.wave, score, waves.remaining(),
                                 waves.between, waves.between_timer, waves.is_boss_wave)
                    canvas.fill(BLACK)
                    canvas.blit(world, (0, 0))
                    result = pause_screen()
                    pygame.mouse.set_visible(False)
                    if result == "menu":
                        return "menu"
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and not PAUSE_BTN_RECT.collidepoint(mx, my):
                    player.try_shoot()
                if event.button == 3: player.try_melee()

        if pygame.mouse.get_pressed()[0]:
            player.try_shoot()

        player.update(dt, mx, my)
        waves.update(dt, player)

        # Bullet ↔ zombie
        for b in player.bullets[:]:
            for z in waves.zombies:
                if not z.dead and b.rect().colliderect(z.rect()):
                    b.dead = True
                    angle  = math.atan2(z.y-player.y, z.x-player.x)
                    z.hit(damage=1, knockback_angle=angle, knockback_force=2)
                    spawn_sparks(z.x, z.y, 5, BLOOD_RED)
                    play('boss_hit' if z.IS_BOSS else 'hit')
                    if z.dead:
                        pts = z.SCORE * waves.wave
                        score += pts
                        spawn_float(z.x, z.y-20, f"+{pts}", HUD_GREEN)
                        play('death')
                        trigger_shake(2, 4)

        # Melee ↔ zombie
        for sw in player.active_swings():
            for z in waves.zombies:
                if not z.dead and sw.check_hit(z):
                    angle = math.atan2(z.y-sw.cy, z.x-sw.cx)
                    col   = (180,40,200) if z.IS_BOSS else None
                    z.hit(damage=MeleeSwing.DAMAGE_HP, knockback_angle=angle, knockback_force=MeleeSwing.KNOCKBACK)
                    sw.spawn_hit_particles(z.x, z.y, angle, color=col)
                    spawn_sparks(z.x, z.y, 6, col or BLOOD_RED)
                    play('boss_hit' if z.IS_BOSS else 'hit')
                    trigger_shake(5, 7)
                    if z.dead:
                        pts = z.SCORE * waves.wave * 2
                        score += pts
                        spawn_float(z.x, z.y-20, f"+{pts} BAT!", BAT_COL)
                        play('death')

        if player.hp <= 0:
            add_score_to_shop(score)
            pygame.mouse.set_visible(True)
            return game_over_screen(score, waves.wave)

        boss = waves.boss()

        # Draw
        draw_arena(world)
        waves.draw(world)
        draw_sparks(world)
        player.draw(world)
        draw_float_texts(world)
        player.draw_hud(world)
        draw_top_hud(world, waves.wave, score, waves.remaining(),
                     waves.between, waves.between_timer, waves.is_boss_wave)
        draw_wave_banner(world, waves.wave, waves.announce_timer, waves.is_boss_wave)
        draw_vignette(world, player.hp, boss_alive=boss is not None)
        draw_flash(world)
        draw_pause_btn(world, mx, my)
        draw_crosshair(world, mx, my)

        ox, oy = get_shake_offset()
        canvas.fill(BLACK)
        canvas.blit(world, (ox, oy))
        _sc = pygame.transform.scale(canvas, screen.get_size())
        screen.blit(_sc, (0, 0))
        pygame.display.flip()


# ── Entry ─────────────────────────────────────────────────────────────────────
def main():
    state = "menu"
    while True:
        if state == "menu":
            main_menu()
            state = "game"
        elif state == "game":
            stop_menu_music()
            result = game()
            state  = result if result in ("menu",) else "menu"

if __name__ == "__main__":
    apply_settings(load_settings())
    main()