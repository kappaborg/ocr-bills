"""
Generate the ExTaSy app icon: cyan→emerald gradient with the brand ◈
glyph centered. 1024x1024 master — flutter_launcher_icons fans this
out to all platform sizes.

Draws the diamond geometrically (four lines + an inner filled diamond)
instead of relying on font availability for ◈ — the glyph is in U+25C8
which not every Mac font ships, and shape primitives give us crisper
edges at small sizes anyway.
"""
from PIL import Image, ImageDraw

SIZE = 1024
CYAN = (34, 211, 238)      # #22D3EE  — gradient start
EMERALD = (52, 211, 153)   # #34D399  — gradient end
SLATE = (2, 6, 23)         # #020617  — diamond color


def gradient_image(w: int, h: int) -> Image.Image:
    """Diagonal cyan→emerald gradient (~135deg, matches the website CTA)."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            # Normalize diagonal position; gives the same direction as
            # `linear-gradient(135deg, cyan, emerald)` on the web.
            t = (x + y) / (w + h - 2)
            r = round(CYAN[0] * (1 - t) + EMERALD[0] * t)
            g = round(CYAN[1] * (1 - t) + EMERALD[1] * t)
            b = round(CYAN[2] * (1 - t) + EMERALD[2] * t)
            px[x, y] = (r, g, b)
    return img


def draw_diamond(img: Image.Image) -> None:
    """Draw the ◈ shape — outer diamond outline + inner filled diamond.
    Coordinates are relative to image size so we can re-render at any
    resolution without manual tweaks."""
    w, h = img.size
    cx, cy = w / 2, h / 2

    # Outer diamond: square rotated 45°, takes ~62% of the icon.
    outer_radius = w * 0.31
    outer = [(cx, cy - outer_radius), (cx + outer_radius, cy),
             (cx, cy + outer_radius), (cx - outer_radius, cy)]

    # Inner diamond ~38% of outer — proportions of the Unicode glyph.
    inner_radius = outer_radius * 0.38
    inner = [(cx, cy - inner_radius), (cx + inner_radius, cy),
             (cx, cy + inner_radius), (cx - inner_radius, cy)]

    draw = ImageDraw.Draw(img)
    stroke = max(8, int(w * 0.035))
    draw.polygon(outer, outline=SLATE, fill=None, width=stroke)
    draw.polygon(inner, fill=SLATE)


if __name__ == "__main__":
    img = gradient_image(SIZE, SIZE)
    draw_diamond(img)
    img.save("/tmp/extasy-icon.png", "PNG")
    print("wrote /tmp/extasy-icon.png", SIZE, "x", SIZE)
