"""Generate the Aegis (灵盾) shield icon: favicon.png + favicon.ico.

Design: rounded-square indigo->violet gradient tile with a crisp white shield
(aegis = the shield of Zeus). Drawn at 4x then downscaled for smooth edges.
"""

import math
from PIL import Image, ImageDraw

S = 4  # supersample factor
W = 128 * S  # 512 base canvas


def lerp(a, b, t):
    return a + (b - a) * t


def shade(p):
    """Indigo -> violet gradient colour at normalized y in [0,1]."""
    # #8b7cff -> #6b4ee8 (135deg, so blend x and y together)
    t = max(0.0, min(1.0, (p[0] / W + p[1] / W) / 2.0))
    return (
        int(lerp(0x8B, 0x6B, t)),
        int(lerp(0x7C, 0x4E, t)),
        int(lerp(0xFF, 0xE8, t)),
    )


img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
px = img.load()

# Gradient rounded-square tile (radius ~ 26% of size).
r = int(W * 0.26)
for y in range(W):
    for x in range(W):
        # Rounded-rect distance field: outside -> transparent.
        cx = min(max(x, r), W - r)
        cy = min(max(y, r), W - r)
        dx, dy = x - cx, y - cy
        d = math.hypot(dx, dy)
        if d > r:
            continue
        # Soft edge: 2px AA ramp.
        if d > r - 2:
            a = max(0.0, (r - d) / 2.0)
            col = shade((x, y))
            px[x, y] = (col[0], col[1], col[2], int(255 * a))
        else:
            col = shade((x, y))
            px[x, y] = (col[0], col[1], col[2], 255)

# Inner highlight arc at the top (subtle glass shine) — clipped to the tile
# so the rounded corners stay fully transparent.
from PIL import ImageChops
tile = img.copy()
shine = Image.new("RGBA", (W, W), (0, 0, 0, 0))
sd = ImageDraw.Draw(shine)
sd.ellipse([-W * 0.15, -W * 0.35, W * 1.15, W * 0.45], fill=(255, 255, 255, 26))
shine.putalpha(ImageChops.multiply(shine.split()[3], tile.split()[3]))
img = Image.alpha_composite(tile, shine)

# Shield glyph — centred, white rim with the gradient tile showing through.
def shield_poly(cx, cy, s):
    """Classic shield: wide top, tapered flanks, pointed bottom."""
    return [
        (cx - 0.34 * s, cy - 0.38 * s),
        (cx + 0.34 * s, cy - 0.38 * s),
        (cx + 0.46 * s, cy + 0.05 * s),
        (cx + 0.20 * s, cy + 0.38 * s),
        (cx, cy + 0.46 * s),
        (cx - 0.20 * s, cy + 0.38 * s),
        (cx - 0.46 * s, cy + 0.05 * s),
    ]


cx, cy = W * 0.5, W * 0.52
s = W * 0.56

# Shield on its own layer, composited over the tile so the cut-out shows the
# gradient through it (instead of punching a transparent hole to the page).
shield_l = Image.new("RGBA", (W, W), (0, 0, 0, 0))
sl = ImageDraw.Draw(shield_l)
sl.polygon(shield_poly(cx, cy, s), fill=(255, 255, 255, 255))
# Crisp white ring at the cut-out edge.
sl.polygon(shield_poly(cx, cy - W * 0.01, s * 0.78), outline=(255, 255, 255, 255), width=int(W * 0.008))
img = Image.alpha_composite(img, shield_l)

# Aegis spark: small indigo dot at the shield's core.
draw = ImageDraw.Draw(img)
dot_r = W * 0.055
draw.ellipse(
    [cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r],
    fill=(0x6B, 0x4E, 0xE8, 255),
)

# Downscale to target sizes.
WEB = "src/aegis/app/assets/web"
base = img.resize((96, 96), Image.LANCZOS)
base.save(f"{WEB}/images/favicon.png")

# Multi-res .ico.
ico = img.resize((256, 256), Image.LANCZOS)
ico.save(f"{WEB}/icons/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

print("OK — favicon.png 96x96, favicon.ico 16/32/48")
