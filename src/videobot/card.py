"""The title card shown while the title is read: a white rounded card with avatar, channel
name, a grey info line, the title and (optionally) real engagement numbers.

Drawn at 2x and scaled down, so corners and text edges are smooth.
"""

from __future__ import annotations

import random
from importlib import resources
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

S = 2                      # supersampling factor
WIDTH, PAD, RADIUS = 864, 40, 30
BLUE, GREY, BLACK = (47, 104, 254), (164, 164, 164), (0, 0, 0)


def _font(size: int, weight: str = "Regular") -> ImageFont.FreeTypeFont:
    path = resources.files("videobot").joinpath("fonts/Inter.ttf")
    font = ImageFont.truetype(str(path), size * S)
    font.set_variation_by_name(weight)
    return font


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=font) <= width or not line:
            line = test
        else:
            lines.append(line)
            line = word
    return lines + [line] if line else lines


def _avatar(path: str, name: str, size: int) -> Image.Image:
    if path and Path(path).expanduser().exists():
        img = ImageOps.fit(Image.open(Path(path).expanduser()).convert("RGB"), (size, size))
    else:  # no picture: a coloured circle with the channel's first letter
        img = Image.new("RGB", (size, size), BLUE)
        d = ImageDraw.Draw(img)
        d.text((size / 2, size / 2), (name[:1] or "?").upper(), font=_font(size // S // 2, "Bold"),
                fill="white", anchor="mm")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    img.putalpha(mask)
    return img


def _icon(draw: ImageDraw.ImageDraw, kind: str, x: int, y: int, s: int, color) -> None:
    """Small line icons: upvote arrow, speech bubble, share arrow (s = icon size)."""
    w = max(2, s // 9)
    if kind == "up":
        draw.polygon([(x + s / 2, y), (x + s, y + s * .55), (x + s * .7, y + s * .55), (x + s * .7, y + s),
                      (x + s * .3, y + s), (x + s * .3, y + s * .55), (x, y + s * .55)], outline=color, width=w)
    elif kind == "comment":
        draw.rounded_rectangle((x, y, x + s, y + s * .78), radius=s * .25, outline=color, width=w)
        draw.polygon([(x + s * .25, y + s * .74), (x + s * .2, y + s), (x + s * .5, y + s * .76)], fill=color)
    else:  # share
        draw.line([(x + s * .1, y + s * .9), (x + s * .1, y + s * .45), (x + s * .85, y + s * .45)], fill=color, width=w)
        draw.polygon([(x + s, y + s * .45), (x + s * .62, y + s * .15), (x + s * .62, y + s * .75)], fill=color)


def make_card(title: str, name: str, info: str = "", avatar: str = "",
              stats: dict[str, str] | None = None) -> Image.Image:
    """Render the card (RGBA, ~864 px wide). `stats` e.g. {"up": "12k", "comment": "340", "share": "88"}
    is only drawn when given - use real numbers or leave it out."""
    title_font, name_font, info_font, stat_font = _font(54, "Bold"), _font(36, "Bold"), _font(28), _font(36)
    tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    inner = (WIDTH - 2 * PAD) * S
    lines = _wrap(tmp, title, title_font, inner)
    av = 110 * S
    height = PAD * S + av + 28 * S + len(lines) * 67 * S + (76 * S if stats else 0) + PAD * S

    card = Image.new("RGBA", (WIDTH * S, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, WIDTH * S - 1, height - 1), radius=RADIUS * S, fill="white",
                        outline=(245, 245, 245), width=4 * S)
    x = y = PAD * S
    card.alpha_composite(_avatar(avatar, name, av), (x, y))
    tx = x + av + 25 * S
    if info:
        d.text((tx, y + av / 2 - 6 * S), name, font=name_font, fill=BLACK, anchor="ls")
        d.text((tx, y + av / 2 + 12 * S), info, font=info_font, fill=GREY, anchor="lt")
    else:
        d.text((tx, y + av / 2), name, font=name_font, fill=BLACK, anchor="lm")
    y += av + 28 * S
    for line in lines:
        d.text((x, y + 67 * S / 2), line, font=title_font, fill=BLACK, anchor="lm")
        y += 67 * S
    if stats:
        y += 30 * S
        for kind in ("up", "comment", "share"):
            if kind in stats:
                color = BLUE if kind == "up" else GREY
                _icon(d, kind, x, y, 34 * S, color)
                d.text((x + 50 * S, y + 17 * S), stats[kind], font=stat_font, fill=color, anchor="lm")
                x += 50 * S + d.textlength(stats[kind], font=stat_font) + 40 * S

    card = card.resize((WIDTH, height // S), Image.LANCZOS)
    # soft shadow so the card lifts off bright backgrounds
    shadow = Image.new("RGBA", (card.width + 40, card.height + 40), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 70), (20, 26), card.getchannel("A"))
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    shadow.alpha_composite(card, (20, 20))
    return shadow


def simulated_stats(seed: int) -> tuple[str, dict[str, str]]:
    """Made-up engagement numbers for the card, for the classic story-video look.

    These are NOT real figures. Distributions as in the original channel setup:
    views 200k-1.7M, upvotes ~2 % of views, comments ~0.7 % and shares ~0.3 % of upvotes.
    Returns (views text, stats dict for `make_card`)."""
    rnd = random.Random(seed)
    views = rnd.randint(200_000, 1_700_000)
    up = max(1, int(views * max(0.002, rnd.normalvariate(0.02, 0.0075))))
    comments = max(1, int(up * max(0.001, rnd.normalvariate(0.007, 0.0025))))
    shares = max(1, int(up * max(0.0005, rnd.normalvariate(0.003, 0.001))))
    return f"{compact(views)} views", {"up": compact(up), "comment": compact(comments), "share": compact(shares)}


def compact(n: int) -> str:
    """12_345 -> '12.3k', 1_200_000 -> '1.2M'."""
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1000:.1f}".rstrip("0").rstrip(".") + "k"
    return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
