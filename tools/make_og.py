"""Share-preview image (site/og.png, 1200x630) with the current odds.

Run after the forecast: python tools/make_og.py. Messaging apps cache previews,
so the image carries its own "updated" date.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BG, INK, MUTED, LINE = (15, 21, 38), (233, 237, 247), (143, 154, 184), (41, 52, 90)
DEM, REP = (111, 155, 255), (255, 118, 114)


def font(name, size, weight=None):
    f = ImageFont.truetype(str(ROOT / "assets" / "fonts" / name), size)
    if weight:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


def pct(p):
    return ">99%" if p >= 0.995 else "<1%" if p <= 0.005 else f"{round(p * 100)}%"


def main() -> Path:
    f = json.loads((ROOT / "site" / "data" / "forecast.json").read_text())
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    title = font("BarlowCondensed-Bold.ttf", 92)
    big = font("BarlowCondensed-Bold.ttf", 120)
    lab = font("PublicSans.ttf", 30, 600)
    small = font("PublicSans.ttf", 24, 400)

    face = Image.open(ROOT / "site" / "face.webp").convert("RGBA").resize((210, 210), Image.LANCZOS)
    im.paste(face, ((W - 210) // 2, 28), face)
    d.text((W // 2 - 130, 133), "MAXIMUM", font=title, fill=DEM, anchor="rm")
    d.text((W // 2 + 130, 133), "LIKELIHOOD", font=title, fill=REP, anchor="lm")

    d.text((W // 2, 280), "Chance Democrats win control, 2026", font=lab, fill=MUTED, anchor="mm")
    cols = [("Senate", f["senate"]), ("House", f["house"])]
    if f.get("governor"):
        cols.append(("Governors", f["governor"]))
    cw = W // len(cols)
    for i, (name, s) in enumerate(cols):
        x = cw * i + cw // 2
        p = s["p_dem_control"]
        d.text((x, 395), pct(p), font=big, fill=DEM if p >= 0.5 else REP, anchor="mm")
        d.text((x, 478), name, font=lab, fill=INK, anchor="mm")
        if i:
            d.line([(cw * i, 320), (cw * i, 500)], fill=LINE, width=2)
    upd = datetime.fromisoformat(f["generated_utc"].replace("Z", "+00:00")).strftime("%b %-d, %Y")
    d.line([(60, 548), (W - 60, 548)], fill=LINE, width=2)
    d.text((60, 585), "Odds from public polls, every pollster graded on its record", font=small, fill=MUTED, anchor="lm")
    d.text((W - 60, 585), f"Updated {upd}", font=small, fill=MUTED, anchor="rm")
    out = ROOT / "site" / "og.png"
    im.save(out, optimize=True)
    return out


if __name__ == "__main__":
    print(main())
