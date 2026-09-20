"""Draws app.ico: the target from the app's page (a ring with four ticks) on a dark tile,
with the pointer sitting in it, in Auto Clicker's yellow.

    python make_icon.py

Every size is drawn on its own, 8x and downsampled, so 16px stays readable: below 32px the
ticks and the pointer's outline are dropped rather than turned into mud.
"""
from PIL import Image, ImageDraw

ACCENT = (255, 197, 51, 255)
TILE_TOP = (30, 26, 16, 255)
TILE_BOTTOM = (13, 12, 10, 255)
SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
S = 8  # supersampling


def tile(d, n, r):
    """Rounded square with a vertical gradient, drawn as rows clipped by the rounded mask."""
    grad = Image.new('RGBA', (n, n))
    g = ImageDraw.Draw(grad)
    for y in range(n):
        f = y / max(n - 1, 1)
        g.line([(0, y), (n, y)], fill=tuple(round(a + (b - a) * f) for a, b in zip(TILE_TOP, TILE_BOTTOM)))
    mask = Image.new('L', (n, n), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, n - 1, n - 1], radius=r, fill=255)
    d.paste(grad, (0, 0), mask)


def draw(size):
    n = size * S
    img = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    tile(img, n, round(n * 0.22))
    d = ImageDraw.Draw(img)

    cx = cy = n / 2
    ring = n * 0.255           # radius of the target ring; the ticks reach 0.41n, inside the tile
    w = max(n * 0.055, S)      # stroke

    d.ellipse([cx - ring, cy - ring, cx + ring, cy + ring], outline=ACCENT, width=round(w))

    # The four ticks read as a target; under 32px they merge with the ring, so they are dropped.
    if size >= 32:
        inner, outer = ring * 1.30, ring * 1.62
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            d.line([cx + dx * inner, cy + dy * inner, cx + dx * outer, cy + dy * outer],
                   fill=ACCENT, width=round(w))

    # The pointer, tip at the centre of the ring: what the app moves and clicks.
    tip = (cx - n * 0.055, cy - n * 0.085)
    k = n * 0.30
    arrow = [(0, 0), (0, 0.80), (0.22, 0.60), (0.37, 0.95), (0.52, 0.88), (0.37, 0.54), (0.64, 0.50)]
    pts = [(tip[0] + x * k, tip[1] + y * k) for x, y in arrow]
    if size >= 32:
        d.polygon(pts, fill=(255, 255, 255, 255), outline=(20, 18, 12, 255), width=round(w * 0.55))
    else:
        d.polygon(pts, fill=(255, 255, 255, 255))

    return img.resize((size, size), Image.LANCZOS)


if __name__ == '__main__':
    frames = [draw(s) for s in SIZES]
    frames[-1].save('app.ico', sizes=[(s, s) for s in SIZES],
                    append_images=frames[:-1], format='ICO')
    frames[-1].save('site/screenshots/icon-256.png')
    print('app.ico:', ', '.join(f'{s}px' for s in SIZES))
