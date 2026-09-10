"""Generate every Aegis icon from the brand master art.

Source of truth: docs/brand/ai-aegis-logo-master.png (1254x1254 RGBA).

The artwork is a vertical lockup: the shield mark on top (y 88-926) and the
"AI Aegis" wordmark below it (y 940-1186). Icon slots get the mark alone —
at 16-96 px the wordmark collapses into an illegible smudge, and the README
slot is only 40x40.

Previously this script drew a different icon procedurally (an indigo tile
with a white shield). That mark is gone; re-running the old version would
have reverted every icon in the product, so it is replaced rather than kept.

Run from the repo root:

    python i18n-build/gen_icon.py
"""

import base64
import io
import os
import sys

from PIL import Image

MASTER = os.path.join("docs", "brand", "ai-aegis-logo-master.png")

# Bands in the master art, measured from the alpha channel.
MARK_BOX = (252, 88, 1004, 927)     # shield, 752x839
LOCKUP_BOX = (134, 88, 1114, 1187)  # shield + wordmark, 980x1099

WEB = os.path.join("src", "aegis", "app", "assets", "web")
ASSETS = os.path.join("src", "aegis", "app", "assets")

ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def square(im, box, margin, size):
    """Crop `box`, centre it on a square transparent canvas, resize to `size`.

    Icons need a square canvas with even breathing room; the shield's own
    bounding box is 752x839, so pasting it straight into a square slot would
    otherwise sit off-centre.
    """
    l, t, r, b = box
    cw, ch = r - l, b - t
    side = int(max(cw, ch) * (1 + margin * 2))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    piece = im.crop(box)
    canvas.paste(piece, ((side - cw) // 2, (side - ch) // 2), piece)
    return canvas.resize((size, size), Image.LANCZOS)


def save_png(img, path, size):
    img.resize((size, size), Image.LANCZOS).save(path, "PNG", optimize=True)
    print(f"  {path:<52} {size}x{size}  {os.path.getsize(path):>8,} bytes")


def save_ico(img, path):
    img.resize((256, 256), Image.LANCZOS).save(path, sizes=ICO_SIZES)
    dims = "/".join(str(s[0]) for s in ICO_SIZES)
    print(f"  {path:<52} ico {dims}  {os.path.getsize(path):>8,} bytes")


def main():
    if not os.path.exists(MASTER):
        sys.exit(f"master art not found: {MASTER}\nrun this from the repo root")

    master = Image.open(MASTER).convert("RGBA")
    mark = square(master, MARK_BOX, 0.06, 1254)   # full-res square mark
    lockup = square(master, LOCKUP_BOX, 0.04, 1254)

    print("mark + wordmark lockup:")
    save_png(lockup, os.path.join("docs", "logo.png"), 512)

    print("\nmark alone (README, Gitee repo icon):")
    save_png(mark, os.path.join("docs", "favicon.png"), 128)
    save_png(mark, os.path.join("docs", "logo-mark.png"), 512)

    print("\ninstaller / desktop icons:")
    # 256 because build-installers.yml copies this into
    # share/icons/hicolor/256x256/apps/ — the old 42x42 was a mismatch.
    save_png(mark, os.path.join(ASSETS, "favicon.png"), 256)
    save_ico(mark, os.path.join(ASSETS, "favicon.ico"))
    save_ico(mark, os.path.join("src", "aegis", "plugins", "cursor", "favicon.ico"))

    print("\nin-app web UI (sidebar, top nav, browser tab):")
    # 96 matches the previous asset; redactions.js fetches this and inlines it
    # as base64 into exported PDFs, so growing it would bloat those payloads.
    save_png(mark, os.path.join(WEB, "images", "favicon.png"), 96)
    save_ico(mark, os.path.join(WEB, "icons", "favicon.ico"))

    print("\nSVG wrapper:")
    # Kept as a self-contained SVG with the raster embedded, exactly as
    # before. The declared 42x42 outer size is unchanged so any consumer
    # sizing off it sees no difference; the embedded raster is now 96x96.
    buf = io.BytesIO()
    mark.resize((96, 96), Image.LANCZOS).save(buf, "PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    svg = (
        '<svg width="42" height="42" viewBox="0 0 42 42" '
        'xmlns="http://www.w3.org/2000/svg">\n'
        f'  <image x="0" y="0" width="42" height="42" '
        f'href="data:image/png;base64,{b64}"/>\n'
        "</svg>\n"
    )
    svg_path = os.path.join(ASSETS, "favicon.svg")
    with open(svg_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(svg)
    print(f"  {svg_path:<52} 42x42 (96x96 embedded)  {os.path.getsize(svg_path):>8,} bytes")


if __name__ == "__main__":
    main()
