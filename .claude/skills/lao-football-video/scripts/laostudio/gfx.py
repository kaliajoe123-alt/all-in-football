"""ກຣາຟິກ: ຂໍ້ຄວາມລາວ (Phetsarath + Oswald), ພື້ນເຈ້ຍ, ປ້າຍ, ກາດ, ເອັບເຟັກ.

Graphics primitives. Lao text is shaped with raqm (HarfBuzz) so vowels / tone marks stack correctly;
Phetsarath has no Latin, digits or punctuation, so every string is split into runs and the
non-Lao runs are drawn with Oswald on the same baseline.
"""
import functools, json, math, os, re

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

from . import laotext

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # the skill folder
FONTS = os.path.join(ROOT, "assets", "fonts")
RAQM = ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC
LAO_RUN = re.compile(r"[຀-໿]+(?:[ ]+(?=[຀-໿]))?|[^຀-໿]+")

THEME = {
    "paper": "#EFE6D3", "grid": "#DFD3BA", "ink": "#101A3A", "accent": "#E4252A", "label_bg": "#F4C430",
    "label_fg": "#101A3A", "hl": "#FFD21F", "white": "#FFFFFF", "brand": "#1F4FFF", "lime": "#C4F21A",
    "name": "ALL IN", "handle": "", "logo": "", "follow": "ກົດຕິດຕາມ",
}


def load_brand(name, project_dir=None):
    """Brand kit: <project>/brand.json  >  a path  >  assets/brand/<name>.json inside the skill."""
    t = dict(THEME)
    local = os.path.join(project_dir, "brand.json") if project_dir else ""
    p = local if os.path.isfile(local) else name if os.path.isfile(name) else \
        os.path.join(ROOT, "assets", "brand", name + ".json")
    if os.path.isfile(p):
        t.update(json.load(open(p, encoding="utf-8")))
        if t.get("logo") and not os.path.isabs(t["logo"]):
            t["logo"] = os.path.join(os.path.dirname(p), t["logo"])
    return t


def rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


@functools.lru_cache(maxsize=256)
def font(kind, size):
    if kind == "lao":
        return ImageFont.truetype(os.path.join(FONTS, "Phetsarath-Bold.ttf"), size, layout_engine=RAQM)
    f = ImageFont.truetype(os.path.join(FONTS, "Oswald.ttf"), size)
    try:
        f.set_variation_by_name("Bold")
    except Exception:
        pass
    return f


def runs(text):
    return [(m.group(0), "lao" if laotext.is_lao(m.group(0)) else "lat") for m in LAO_RUN.finditer(text)]


@functools.lru_cache(maxsize=8192)
def text_w(text, size):
    return sum(font(k, size if k == "lao" else int(size * 1.04)).getlength(s) for s, k in runs(text))


def draw_text(d, x, base, text, size, fill, stroke=0, stroke_fill=None):
    """Draw one line with its left edge at x and its baseline at `base`. Returns the new x."""
    for s, k in runs(text):
        f = font(k, size if k == "lao" else int(size * 1.04))
        d.text((x, base), s, font=f, fill=fill, anchor="ls", stroke_width=stroke, stroke_fill=stroke_fill)
        x += f.getlength(s)
    return x


def key_flags(tokens, keys, numbers=True):
    """Which tokens are key words: inside a *starred* phrase, or (optionally) a number."""
    text = "".join(tokens)
    marks = [False] * len(text)
    for k in keys:
        for m in re.finditer(re.escape(k), text):
            for i in range(m.start(), m.end()):
                marks[i] = True
    out, pos = [], 0
    for t in tokens:
        out.append(bool(t.strip()) and (any(marks[pos:pos + len(t)]) or (numbers and bool(laotext.NUM.fullmatch(t)))))
        pos += len(t)
    return out


def text_block(text, size, color, max_w, keys=(), key_color=None, align="center", stroke=0, stroke_fill=None,
               line_h=1.5, say=None, pad=None):
    """Wrapped multi-line RGBA text sprite. '//' or newline in `text` forces a line break."""
    key_color = key_color or color
    lines = []                                               # each line = list of (token, is_key)
    for part in re.split(r"\n|//", text):
        toks = laotext.tokenize(part.strip(), say)
        pairs = list(zip(toks, key_flags(toks, keys)))       # flags BEFORE wrapping: a key phrase may wrap
        lines += wrap_pairs(pairs, size, max_w) or [[]]
    pad = stroke + int(size * 0.2) if pad is None else pad
    lh = int(size * line_h)
    widths = [text_w("".join(t for t, _ in l), size) for l in lines]
    W = int(max(widths + [1])) + 2 * pad
    H = lh * len(lines) + 2 * pad
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, line in enumerate(lines):
        x = pad + (0 if align == "left" else (W - 2 * pad - widths[i]) / 2)
        base = pad + i * lh + int(size * 1.08)
        for t, fl in line:
            x = draw_text(d, x, base, t, size, key_color if fl else color, stroke, stroke_fill)
    return im


def wrap_pairs(pairs, size, max_w):
    """Greedy wrap of (token, flag) pairs on token boundaries; never leaves one short word alone at the end."""
    lines, cur = [], []
    for tok, fl in pairs:
        trial = "".join(t for t, _ in cur) + tok
        if cur and text_w(trial.rstrip(), size) > max_w:
            lines.append(cur)
            cur = [] if tok.strip() == "" else [(tok, fl)]
        else:
            cur.append((tok, fl))
    if cur:
        lines.append(cur)
    out = []
    for l in lines:
        while l and l[0][0].strip() == "":
            l = l[1:]
        while l and l[-1][0].strip() == "":
            l = l[:-1]
        if l:
            out.append(l)
    if len(out) >= 2 and sum(len(t) for t, _ in out[-1]) <= 5:        # orphan: pull one word down
        prev = out[-2]
        k = len(prev) - 1
        while k > 0 and prev[k][0].strip() == "":
            k -= 1
        if k > 1:
            moved = prev[k:]
            cand = moved + [(" ", False)] * (0 if laotext.is_lao(moved[-1][0]) and laotext.is_lao(out[-1][0][0]) else 1) + out[-1]
            if text_w("".join(t for t, _ in cand), size) <= max_w:
                out[-2] = [x for x in prev[:k]]
                while out[-2] and out[-2][-1][0].strip() == "":
                    out[-2] = out[-2][:-1]
                out[-1] = cand
    return out


def rounded(size, radius, fill, outline=None, width=0):
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=fill, outline=outline,
                                         width=width)
    return im


def shadowed(sprite, blur=14, offset=(0, 8), alpha=110):
    """Add a soft drop shadow around an RGBA sprite (returns a larger sprite + its inner offset)."""
    m = blur * 2
    W, H = sprite.size[0] + 2 * m, sprite.size[1] + 2 * m
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    a = sprite.split()[3].point(lambda v: v * alpha // 255)
    sh.paste((10, 14, 30, 255), (m + offset[0], m + offset[1]), a)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    sh.alpha_composite(sprite, (m, m))
    return sh, m


def pill(text, size, fg, bg, pad_x=None, pad_y=None, radius=None, max_w=4000, keys=(), key_color=None, say=None):
    t = text_block(text, size, fg, max_w, keys=keys, key_color=key_color, pad=0, say=say)
    px = int(size * 0.55) if pad_x is None else pad_x
    py = int(size * 0.12) if pad_y is None else pad_y
    box = rounded((t.size[0] + 2 * px, t.size[1] + 2 * py), int(size * 0.28) if radius is None else radius, bg)
    box.alpha_composite(t, (px, py))
    return box


def paste(frame, sprite, x, y, alpha=1.0, scale=1.0, anchor="lt"):
    """Composite an RGBA sprite on an RGB frame; alpha/scale animate it. anchor 'c' = (x, y) is the centre."""
    if alpha <= 0.004:
        return
    if scale != 1.0:
        w, h = max(1, int(sprite.size[0] * scale)), max(1, int(sprite.size[1] * scale))
        sprite = sprite.resize((w, h), Image.BILINEAR)
    if anchor == "c":
        x, y = x - sprite.size[0] / 2, y - sprite.size[1] / 2
    mask = sprite.split()[3]
    if alpha < 0.996:
        mask = mask.point(lambda v: int(v * alpha))
    frame.paste(sprite, (int(round(x)), int(round(y))), mask)


# ------------------------------------------------------------------ easing
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease_out(p):
    p = clamp(p); return 1 - (1 - p) ** 3


def ease_io(p):
    p = clamp(p); return 0.5 - 0.5 * math.cos(math.pi * p)


def back(p, s=1.70158):
    p = clamp(p) - 1; return p * p * ((s + 1) * p + s) + 1


# ------------------------------------------------------------------ paper + masks
def paper(w, h, theme, seed=7):
    """Beige notebook paper: fine grain, faint grid and a soft vignette (the format's signature background)."""
    rng = np.random.default_rng(seed)
    base = np.array(rgb(theme["paper"]), np.float32)
    grid = np.array(rgb(theme["grid"]), np.float32)
    a = np.ones((h, w, 3), np.float32) * base
    step = max(36, round(w / 36))
    for x in range(step // 2, w, step):
        a[:, x:x + 2] = grid
    for y in range(step // 2, h, step):
        a[y:y + 2, :] = grid
    a += rng.normal(0, 1.8, (h, w, 1)).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    a *= (1 - 0.07 * np.clip(r - 0.55, 0, 1))[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def torn_edge(h, seed=3, amp=46):
    rng = np.random.default_rng(seed)
    walk = np.cumsum(rng.normal(0, 1, h))
    k = np.ones(31) / 31
    smooth = np.convolve(walk - walk.mean(), k, mode="same")
    smooth = smooth / (np.abs(smooth).max() + 1e-6) * amp
    return (smooth + rng.normal(0, 2.2, h)).astype(np.float32)


def tear(old, new, p, edge, paper_rgb=(250, 246, 236)):
    """Torn-paper wipe: `new` is revealed from the left behind a ragged white paper edge."""
    A, B = np.asarray(old), np.asarray(new)
    h, w = A.shape[:2]
    X = np.arange(w, dtype=np.float32)[None, :]
    bx = (-80 + ease_io(p) * (w + 200) + edge)[:, None]
    out = np.where((X < bx)[..., None], B, A)
    band = (X >= bx) & (X < bx + 18)
    out[band] = paper_rgb
    sh = (X >= bx + 18) & (X < bx + 60)
    f = np.where(sh, 0.55 + 0.45 * (X - bx - 18) / 42, 1.0)[..., None]
    return Image.fromarray((out * f).astype(np.uint8), "RGB")


def whip(old, new, p):
    """Fast horizontal slide with motion blur."""
    w, h = old.size
    q = ease_io(p)
    canvas = Image.new("RGB", (w, h))
    off = int(q * w)
    canvas.paste(old, (-off, 0)); canvas.paste(new, (w - off, 0))
    k = 1 - abs(2 * q - 1)                                   # strongest blur in the middle
    if k > 0.05:
        small = canvas.resize((max(8, int(w / (1 + 22 * k))), h), Image.BILINEAR)
        canvas = small.resize((w, h), Image.BILINEAR)
    return canvas


# ------------------------------------------------------------------ media preparation
def cover_fit(im, w, h, focus_y=0.42):
    """Resize + crop to fill w x h. Narrow (portrait) pictures are shown whole over a blurred copy."""
    iw, ih = im.size
    if iw / ih < (w / h) * 0.72:                             # much narrower than the box
        bg = cover_fit_plain(im, w, h, 0.3).filter(ImageFilter.GaussianBlur(28))
        bg = Image.eval(bg, lambda v: int(v * 0.55))
        s = h / ih
        fg = im.resize((max(1, int(iw * s)), h), Image.LANCZOS)
        bg.paste(fg, ((w - fg.size[0]) // 2, 0))
        return bg
    return cover_fit_plain(im, w, h, focus_y)


def cover_fit_plain(im, w, h, focus_y=0.42):
    iw, ih = im.size
    s = max(w / iw, h / ih)
    nw, nh = max(w, int(round(iw * s))), max(h, int(round(ih * s)))
    im = im.resize((nw, nh), Image.LANCZOS)
    x = (nw - w) // 2
    y = int((nh - h) * focus_y)
    return im.crop((x, y, x + w, y + h))


def ken_burns(prep, w, h, p, style):
    """Smooth sub-pixel zoom/pan on a prepared picture that is 1.18x the target size."""
    pw, ph = prep.size
    e = ease_io(p)
    if style == "out":
        z, cx, cy = 1.13 - 0.12 * e, 0.5, 0.5
    elif style == "left":
        z, cx, cy = 1.1, 0.535 - 0.07 * e, 0.5
    elif style == "right":
        z, cx, cy = 1.1, 0.465 + 0.07 * e, 0.5
    elif style == "punch":
        z, cx, cy = 1.16 - 0.1 * ease_out(p * 6) + 0.05 * e, 0.5, 0.48
    else:
        z, cx, cy = 1.01 + 0.12 * e, 0.5, 0.48
    cw, ch = pw / z, ph / z
    x0 = clamp(cx * pw - cw / 2, 0, pw - cw); y0 = clamp(cy * ph - ch / 2, 0, ph - ch)
    return prep.resize((w, h), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
