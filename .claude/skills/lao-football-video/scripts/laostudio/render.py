"""ຕັດຕໍ່ ແລະ render ວີດີໂອ: ທຸກເຟຣມຄຳນວນຈາກເວລາ t ແບບຕາຍຕົວ (deterministic), render ຂະໜານຫຼາຍ process.

Look of the format (see references/style-guide.md): beige notebook paper, the picture in a rounded card,
yellow name labels, stat cards, quote bands, chapter cards revealed by a torn-paper wipe, a channel tag
under the card and (our addition) word-by-word Lao captions, chapter chip and progress bar.
"""
import bisect, functools, hashlib, multiprocessing as mp, os, subprocess

from PIL import Image, ImageDraw, ImageFilter

from . import gfx, laotext
from .footage import VID_EXT

LAYOUT = {
    "16:9": dict(W=1920, H=1080, card=(312, 100, 1296, 729), cap_y=966, cap_size=54, cap_w=1560, cap_lines=1,
                 logo_w=150, logo_xy=(1714, 40), badge_xy=(56, 40), handle_y=846, title_size=108, title_w=1560,
                 title_y=500, label_size=46, stat_num=150, stat_cap=42, chapter_size=120, margin=56),
    "9:16": dict(W=1080, H=1920, card=(54, 440, 972, 729), cap_y=1338, cap_size=60, cap_w=950, cap_lines=2,
                 logo_w=150, logo_xy=(876, 236), badge_xy=(54, 246), handle_y=1188, title_size=96, title_w=960,
                 title_y=800, label_size=46, stat_num=140, stat_cap=42, chapter_size=104, margin=54),
}
KB = ["in", "left", "out", "right"]


def is_video(p):
    return bool(p) and p.lower().endswith(VID_EXT)


def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


class VideoReader:
    """Sequential frame reader (ffmpeg pipe) for one clip window, already cropped to the target size."""

    def __init__(self, path, start, w, h, fps):
        self.args, self.w, self.h, self.k, self.proc, self.last = (path, start, fps), w, h, -1, None, None

    def _open(self):
        path, start, fps = self.args
        if self.proc:
            self.proc.kill()
        self.proc = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-i", path, "-an", "-vf",
             f"scale={self.w}:{self.h}:force_original_aspect_ratio=increase,crop={self.w}:{self.h},fps={fps}",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.k = -1

    def frame(self, k):
        if self.proc is None or k < self.k:
            self._open()
        n = self.w * self.h * 3
        while self.k < k:
            buf = self.proc.stdout.read(n)
            if len(buf) < n:
                break                                       # clip ended: hold the last frame
            self.last = Image.frombuffer("RGB", (self.w, self.h), buf, "raw", "RGB", 0, 1)
            self.k += 1
        return self.last or Image.new("RGB", (self.w, self.h), (20, 20, 24))

    def close(self):
        if self.proc:
            self.proc.kill(); self.proc = None


class Renderer:
    def __init__(self, tl, meta, theme, project_dir):
        self.tl, self.meta, self.th, self.dir = tl, meta, theme, project_dir
        self.L = L = LAYOUT[meta["aspect"] if meta["aspect"] in LAYOUT else "16:9"]
        self.W, self.H, self.fps = L["W"], L["H"], int(meta["fps"])
        self.total = tl["total"]
        self.nframes = int(round(self.total * self.fps))
        self.shots = tl["shots"]
        self.starts = [s["start"] for s in self.shots]
        self.ink, self.acc = gfx.rgb(theme["ink"]), gfx.rgb(theme["accent"])
        self.say = meta.get("say", {})
        self.edge = gfx.torn_edge(self.H)
        self.prep_dir = os.path.join(project_dir, ".cache", "prep")
        os.makedirs(self.prep_dir, exist_ok=True)
        self._readers, self._prev = {}, {}
        self._build_static()
        self._build_captions()
        self._plan_layouts()

    # ---------------------------------------------------------------- static layers
    def _logo(self, width):
        p = self.th.get("logo")
        if p and os.path.isfile(p):
            im = Image.open(p).convert("RGBA")
            bb = im.getbbox()
            im = im.crop(bb) if bb else im
            return im.resize((width, max(1, int(im.size[1] * width / im.size[0]))), Image.LANCZOS)
        name = self.th.get("name", "ALL IN")
        size = 10
        while gfx.text_w(name, size + 2) < width * 0.74 and size < width:
            size += 2
        box = gfx.rounded((width, int(size * 1.75)), int(size * 0.4), gfx.rgb(self.th["ink"]) + (255,))
        d = ImageDraw.Draw(box)
        x = (width - gfx.text_w(name, size)) / 2
        gfx.draw_text(d, x, int(size * 1.34), name, size, gfx.rgb(self.th["lime"]))
        return box

    def _build_static(self):
        L, th = self.L, self.th
        self.paper = gfx.paper(self.W, self.H, th)
        cx, cy, cw, ch = L["card"]
        self.card_mask = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(self.card_mask).rounded_rectangle((0, 0, cw - 1, ch - 1), 14, fill=255)
        self.ui = []                                         # (sprite, x, y) drawn on every frame
        logo = self._logo(L["logo_w"])
        self.logo = logo
        self.ui.append((logo, L["logo_xy"][0], L["logo_xy"][1]))
        if self.meta.get("show"):
            badge = gfx.pill(str(self.meta["show"]), 34, gfx.rgb(th["white"]), gfx.rgb(th["accent"]) + (255,),
                             say=self.say)
            self.ui.append((badge, L["badge_xy"][0], L["badge_xy"][1]))
            self.badge_h = badge.size[1]
            self.badge_w = badge.size[0]
        else:
            self.badge_h = self.badge_w = 0
        handle = str(self.meta.get("handle") or th.get("handle") or "")
        self.handle = gfx.pill(handle, 26, (255, 255, 255), (16, 16, 20, 235), pad_x=18, pad_y=5, radius=6) \
            if handle else None
        # card base: paper + soft shadow where the card sits + handle tag under it
        base = self.paper.copy()
        sh = Image.new("RGBA", (cw + 120, ch + 120), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((60, 66, cw + 60, ch + 66), 16, fill=(20, 22, 40, 120))
        sh = sh.filter(ImageFilter.GaussianBlur(20))
        base.paste(sh, (cx - 60, cy - 60), sh)
        if self.handle:
            gfx.paste(base, self.handle, self.W / 2 - self.handle.size[0] / 2, L["handle_y"])
        self.base_card = base
        grad = Image.new("L", (1, self.H), 0)
        for y in range(self.H):
            v = (y - self.H * 0.52) / (self.H * 0.48)
            grad.putpixel((0, y), int(190 * gfx.clamp(v) ** 1.4))
        self.bottom_grad = Image.merge("RGBA", [Image.new("L", (self.W, self.H), 8)] * 3 +
                                       [grad.resize((self.W, self.H))])
        # chapter chips (shown next to the show badge)
        self.chips = []
        n = 0
        for c in self.tl["chapters"]:
            if c["title"]:
                n += 1
                self.chips.append(gfx.pill(c["title"], 30, self.ink, gfx.rgb(th["label_bg"]) + (255,), say=self.say))
            else:
                self.chips.append(None)

    # ---------------------------------------------------------------- captions
    def _build_captions(self):
        """captions: key  -> only the *starred* key phrases pop up while they are spoken (default)
                     full -> the whole narration, word-by-word highlight
                     off  -> nothing"""
        L = self.L
        mode = self.meta.get("captions", "key")
        mode = "full" if mode is True else "off" if mode in (False, None, "none", "off") else str(mode)
        self.caps = []                                       # [start, end, sentence, lines, flags, timed, style]
        for si, s in enumerate(self.tl["sentences"]):
            if s.get("nocap") or mode == "off":
                continue
            toks = s["tokens_all"]
            timed, ti = [], 0                                # display token -> its timing (None = silent)
            for t in toks:
                if ti < len(s["tokens"]) and s["tokens"][ti]["t"] == t:
                    timed.append(s["tokens"][ti]); ti += 1
                else:
                    timed.append(None)
            if mode == "key":
                flags = gfx.key_flags(toks, s["keys"], numbers=False)
                size = int(L["cap_size"] * 1.18)
                j = 0
                while j < len(toks):
                    if not flags[j]:
                        j += 1
                        continue
                    k = j
                    while k + 1 < len(toks) and (flags[k + 1] or (toks[k + 1].strip() == "" and k + 2 < len(toks)
                                                                    and flags[k + 2])):
                        k += 1
                    run = list(range(j, k + 1))
                    tt = [timed[x] for x in run if timed[x]]
                    if tt:
                        pairs = [(toks[x], x) for x in run]
                        lines, cur = [], []
                        for tok, x in pairs:                 # wrap long key phrases
                            if cur and gfx.text_w("".join(toks[y] for y in cur) + tok, size) > L["cap_w"] - 80:
                                lines.append(cur); cur = []
                            if cur or tok.strip():
                                cur.append(x)
                        if cur:
                            lines.append(cur)
                        self.caps.append([s["start"] + max(0.0, tt[0]["a"] - 0.08), s["start"] + tt[-1]["b"] + 1.1,
                                          si, lines[:2], [True] * len(toks), timed, "key"])
                    j = k + 1
                continue
            lines = laotext.wrap_tokens(toks, lambda x: gfx.text_w(x, L["cap_size"]), L["cap_w"] - 80)
            flags_all = gfx.key_flags(toks, s["keys"])
            pos, chunks = 0, []
            for i in range(0, len(lines), L["cap_lines"]):
                grp = lines[i:i + L["cap_lines"]]
                idx = []
                for line in grp:
                    while pos < len(toks) and toks[pos].strip() == "" and (not line or toks[pos] != line[0]):
                        pos += 1
                    idx.append(list(range(pos, pos + len(line)))); pos += len(line)
                chunks.append(idx)
            for ci, idx in enumerate(chunks):
                flat = [j for line in idx for j in line]
                first = next((timed[j]["a"] for j in flat if timed[j]), None)
                if first is None:
                    continue
                a = s["start"] + (0.0 if ci == 0 else first)
                self.caps.append([a, s["end"] + 0.12, si, idx, flags_all, timed, "full"])
        self.caps.sort(key=lambda c: c[0])
        for i in range(len(self.caps) - 1):
            if self.caps[i + 1][0] < self.caps[i][1]:
                self.caps[i][1] = self.caps[i + 1][0]
        self.cap_starts = [c[0] for c in self.caps]

    @functools.lru_cache(maxsize=256)
    def _cap_sprite(self, ci, active):
        a, b, si, idx, flags, timed, style = self.caps[ci]
        toks = self.tl["sentences"][si]["tokens_all"]
        size, th = (int(self.L["cap_size"] * 1.18) if style == "key" else self.L["cap_size"]), self.th
        lh = int(size * 1.5)
        widths = [gfx.text_w("".join(toks[j] for j in line), size) for line in idx]
        px, py = 34, 10
        W, H = int(max(widths)) + 2 * px, lh * len(idx) + 2 * py
        box = gfx.rounded((W, H), 18, gfx.rgb(th["paper"]) + (246,), outline=self.ink + (255,), width=3)
        d = ImageDraw.Draw(box)
        for li, line in enumerate(idx):
            x = px + (W - 2 * px - widths[li]) / 2
            base = py + li * lh + int(size * 1.08)
            for j in line:
                t = toks[j]
                w = gfx.text_w(t, size)
                if j == active and t.strip():
                    d.rounded_rectangle((x - 5, base - size * 0.98, x + w + 5, base + size * 0.36), 9,
                                        fill=gfx.rgb(th["hl"]))
                gfx.draw_text(d, x, base, t, size, self.acc if flags[j] else self.ink)
                x += w
        return gfx.shadowed(box, blur=8, offset=(0, 5), alpha=70)

    def _draw_caption(self, frame, t):
        i = bisect.bisect_right(self.cap_starts, t) - 1
        if i < 0 or t >= self.caps[i][1]:
            return
        a, b, si, idx, flags, timed, style = self.caps[i]
        rel = t - self.tl["sentences"][si]["start"]
        active = -1
        if style == "full":
            for line in idx:
                for j in line:
                    if timed[j] and timed[j]["a"] <= rel:
                        active = j
        sp, m = self._cap_sprite(i, active)
        p = gfx.ease_out((t - a) / 0.14)
        out = gfx.clamp((b - t) / 0.18) if style == "key" else 1.0
        scale = (0.86 + 0.14 * gfx.back(p)) if style == "key" else 1.0
        gfx.paste(frame, sp, self.W / 2, self.L["cap_y"] + (1 - p) * 10, alpha=min(p, out), scale=scale, anchor="c")

    # ---------------------------------------------------------------- media
    def _plan_layouts(self):
        k = 0
        for sh in self.shots:
            if sh["kind"] != "media":
                continue
            p = sh.get("asset")
            if not sh.get("layout"):
                wide = False
                if p and not is_video(p):
                    try:
                        with Image.open(p) as im:
                            wide = im.size[0] >= 1500 and im.size[0] / im.size[1] >= 1.3
                    except Exception:
                        pass
                sh["layout"] = "full" if (sh["i"] == 0 or (wide and k % 5 == 3)) else "card"
            if not sh.get("kb"):
                sh["kb"] = "punch" if sh.get("flash") else KB[k % 4]
            if is_video(p) and "clip_start" not in sh:
                d = probe_duration(p)
                st = (sh.get("media") or {}).get("at")
                sh["clip_start"] = float(st) if st is not None else max(0.0, (d - (sh["end"] - sh["start"])) / 2)
            k += 1

    def _box(self, sh):
        return (self.W, self.H) if sh["layout"] == "full" else self.L["card"][2:]

    def prep_path(self, sh):
        w, h = self._box(sh)
        key = hashlib.sha1(f"{sh['asset']}|{w}x{h}|{os.path.getmtime(sh['asset'])}".encode()).hexdigest()[:18]
        return os.path.join(self.prep_dir, key + ".jpg")

    def prepare(self):
        """Pre-scale every still once (main process) so render workers only load small JPEGs."""
        for sh in self.shots:
            p = sh.get("asset")
            if sh["kind"] != "media" or not p or is_video(p):
                continue
            out = self.prep_path(sh)
            if not os.path.exists(out):
                w, h = self._box(sh)
                im = Image.open(p)
                im.draft("RGB", (w * 2, h * 2))
                im = gfx.cover_fit(im.convert("RGB"), int(w * 1.18), int(h * 1.18))
                im.save(out, quality=93)

    @functools.lru_cache(maxsize=10)
    def _prep(self, path):
        im = Image.open(path); im.load()
        return im

    def _placeholder(self, sh, w, h):
        im = Image.new("RGB", (w, h), gfx.rgb(self.th["ink"]))
        q = (sh.get("media") or {}).get("q", "")
        t = gfx.text_block(sh.get("label") or q or "…", 64, (255, 255, 255), w - 160, say=self.say)
        gfx.paste(im, t, w / 2, h / 2, anchor="c")
        return im

    def _media(self, sh, t):
        w, h = self._box(sh)
        p = sh.get("asset")
        lt, dur = t - sh["start"], max(0.05, sh["end"] - sh["start"])
        if not p:
            return self._placeholder(sh, w, h)
        if is_video(p):
            r = self._readers.get(sh["i"])
            if r is None:
                for rr in self._readers.values():
                    rr.close()
                self._readers.clear()
                r = self._readers[sh["i"]] = VideoReader(p, sh["clip_start"], w, h, self.fps)
            k = int(round(lt * self.fps))
            return r.frame(k // 2 if sh.get("slow") else k)
        return gfx.ken_burns(self._prep(self.prep_path(sh)), w, h, lt / dur, sh["kb"])

    # ---------------------------------------------------------------- overlays inside a shot
    @functools.lru_cache(maxsize=64)
    def _label(self, text):
        sp = gfx.pill(text, self.L["label_size"], gfx.rgb(self.th["label_fg"]), gfx.rgb(self.th["label_bg"]) + (255,),
                      radius=8, say=self.say)
        return gfx.shadowed(sp, blur=8, offset=(0, 5), alpha=90)

    @functools.lru_cache(maxsize=64)
    def _stat(self, text):
        num, _, cap = text.partition("=")
        L = self.L
        n = gfx.text_block(num.strip(), L["stat_num"], self.acc, 900, pad=0, line_h=1.25, say=self.say)
        c = gfx.text_block(cap.strip(), L["stat_cap"], self.ink, max(560, n.size[0] + 80), pad=0, say=self.say) \
            if cap.strip() else None
        w = max(n.size[0], c.size[0] if c else 0) + 80
        h = n.size[1] + (c.size[1] if c else 0) + 44
        box = gfx.rounded((w, h), 18, (255, 253, 247, 255), outline=self.ink + (255,), width=5)
        box.alpha_composite(n, ((w - n.size[0]) // 2, 14))
        if c:
            box.alpha_composite(c, ((w - c.size[0]) // 2, 14 + n.size[1]))
        box = box.rotate(-3, expand=True, resample=Image.BICUBIC)
        return gfx.shadowed(box, blur=12, offset=(0, 8), alpha=110)

    @functools.lru_cache(maxsize=32)
    def _quote(self, text, w):
        q, _, who = text.partition("—")
        q = q.strip().strip('"“”')
        body = gfx.text_block("“" + q + "”", int(self.L["label_size"] * 1.06), (255, 255, 255), w - 120,
                              pad=0, say=self.say)
        whos = gfx.text_block("— " + who.strip(), int(self.L["label_size"] * 0.78), gfx.rgb(self.th["label_bg"]),
                              w - 120, pad=0, say=self.say) if who.strip() else None
        h = body.size[1] + (whos.size[1] if whos else 0) + 44
        band = gfx.rounded((w, h), 14, self.ink + (228,))
        band.alpha_composite(body, ((w - body.size[0]) // 2, 20))
        if whos:
            band.alpha_composite(whos, ((w - whos.size[0]) // 2, 20 + body.size[1]))
        return band

    def _overlays(self, frame, sh, lt, region):
        x, y, w, h = region
        if sh.get("label"):
            sp, m = self._label(sh["label"])
            p = (lt - 0.22) / 0.22
            gfx.paste(frame, sp, x + 30 - m, y + h - 30 - sp.size[1] + m + (1 - gfx.ease_out(p)) * 26,
                      alpha=gfx.clamp(p))
        if sh.get("stat"):
            sp, m = self._stat(sh["stat"])
            p = 1.0 if sh.get("stat_hold") else (lt - 0.3) / 0.3
            if p > 0:
                iw, ih = sp.size[0] - 2 * m, sp.size[1] - 2 * m
                if self.meta["aspect"] == "9:16":             # sits on the card's top edge
                    cx_, cy_ = x + w - 20 - iw / 2, y + ih * 0.2
                else:                                         # hangs off the card's right edge (clear of faces)
                    cx_, cy_ = min(self.W - 30 - iw / 2, x + w + 96 - iw / 2), y + 34 + ih / 2
                gfx.paste(frame, sp, cx_, cy_, alpha=gfx.clamp(p * 2), scale=0.55 + 0.45 * gfx.back(p), anchor="c")
        if sh.get("quote"):
            sp = self._quote(sh["quote"], w - 80)
            p = (lt - 0.15) / 0.25
            gfx.paste(frame, sp, x + 40, y + h - sp.size[1] - 34 + (1 - gfx.ease_out(p)) * 30, alpha=gfx.clamp(p))

    # ---------------------------------------------------------------- shot kinds
    def _shot(self, sh, t):
        lt = t - sh["start"]
        kind = sh["kind"]
        if kind == "media":
            cx, cy, cw, ch = self.L["card"]
            if sh["layout"] == "full":
                frame = self._media(sh, t).copy()
                frame.paste(self.bottom_grad, (0, 0), self.bottom_grad)
                m = self.L["margin"]
                self._overlays(frame, sh, lt, (m, cy, self.W - 2 * m, ch))
                return frame
            frame = self.base_card.copy()
            img = self._media(sh, t)
            tr, p = sh.get("tr"), lt / 0.24
            if tr == "pop" and p < 1:
                s = 0.93 + 0.07 * gfx.back(p)
                w, h = int(cw * s), int(ch * s)
                frame.paste(img.resize((w, h), Image.BILINEAR), (cx + (cw - w) // 2, cy + (ch - h) // 2),
                            self.card_mask.resize((w, h)))
            elif tr == "slide" and p < 1:
                off = int((1 - gfx.ease_out(p)) * 150)
                frame.paste(img, (cx + off, cy), self.card_mask.point(lambda v: int(v * gfx.clamp(p * 1.6))))
            else:
                frame.paste(img, (cx, cy), self.card_mask)
            self._overlays(frame, sh, lt, self.L["card"])
            return frame
        frame = self.paper.copy()
        if kind == "text":
            sp = self._big_text(sh.get("text") or sh.get("quote") or "", self.L["title_size"])
            p = lt / 0.3
            gfx.paste(frame, sp, self.W / 2, self.L["card"][1] + self.L["card"][3] / 2, alpha=gfx.clamp(p * 2),
                      scale=0.8 + 0.2 * gfx.back(p), anchor="c")
        elif kind == "chapter":
            self._chapter(frame, sh, lt)
        elif kind == "outro":
            self._outro(frame, lt)
        return frame

    @functools.lru_cache(maxsize=32)
    def _big_text(self, text, size, color=None):
        plain, keys = laotext.clean_markup(text)
        return gfx.text_block(plain, size, color or self.ink, self.L["title_w"], keys=keys, key_color=self.acc,
                              say=self.say)

    def _chapter(self, frame, sh, lt):
        no = sum(1 for c in self.tl["chapters"][:sh["chapter"] + 1] if c["title"])
        tag = gfx.pill(f"ບົດທີ {no}", 44, (255, 255, 255), self.acc + (255,))
        title = self._big_text(sh["title"], self.L["chapter_size"])
        cy = self.H * 0.47
        p = (lt - 0.25) / 0.3
        gfx.paste(frame, tag, self.W / 2, cy - title.size[1] / 2 - 46, alpha=gfx.clamp(p * 2), anchor="c")
        gfx.paste(frame, title, self.W / 2, cy + 20 + (1 - gfx.ease_out(p)) * 30, alpha=gfx.clamp(p * 1.5), anchor="c")
        w = int((title.size[0] - 80) * gfx.ease_out((lt - 0.45) / 0.4))
        if w > 4:
            y = int(cy + 20 + title.size[1] / 2 + 6)
            ImageDraw.Draw(frame).rounded_rectangle((self.W / 2 - w / 2, y, self.W / 2 + w / 2, y + 12), 6,
                                                    fill=gfx.rgb(self.th["label_bg"]))

    def _outro(self, frame, lt):
        th, cy = self.th, self.H * 0.44
        big = self._logo(int(self.L["logo_w"] * 2.4))
        p = (lt - 0.3) / 0.35
        gfx.paste(frame, big, self.W / 2, cy - 190, alpha=gfx.clamp(p * 2), scale=0.6 + 0.4 * gfx.back(p), anchor="c")
        btn = gfx.pill(th.get("follow", "ກົດຕິດຕາມ") + "  +", 76, (255, 255, 255), self.acc + (255,), pad_x=64,
                       pad_y=16, radius=60)
        btn, m = gfx.shadowed(btn, blur=14, offset=(0, 10), alpha=120)
        p2 = (lt - 1.0) / 0.35
        pulse = 1 + 0.03 * __import__("math").sin(7 * lt) if p2 >= 1 else 1
        gfx.paste(frame, btn, self.W / 2, cy + 40, alpha=gfx.clamp(p2 * 2), scale=(0.5 + 0.5 * gfx.back(p2)) * pulse,
                  anchor="c")
        cta = gfx.text_block(str(self.meta.get("cta", "")), 50, self.ink, self.L["title_w"], say=self.say)
        gfx.paste(frame, cta, self.W / 2, cy + 200, alpha=gfx.clamp((lt - 1.4) / 0.3), anchor="c")
        note = self.meta.get("_credit_line", "")
        if note:
            sm = gfx.text_block(note, 28, (90, 90, 100), self.L["title_w"], say=self.say)
            gfx.paste(frame, sm, self.W / 2, cy + 320, alpha=gfx.clamp((lt - 1.8) / 0.3), anchor="c")

    # ---------------------------------------------------------------- frame
    def _hook(self, frame, t):
        end = self.meta.get("_hook_end", 3.4)
        if t >= end or not self.meta.get("title_plain"):
            return
        fade = gfx.clamp((end - t) / 0.3)
        sp = self._hook_sprite()
        p = (t - 0.12) / 0.4
        veil = Image.new("RGBA", (self.W, self.H), (8, 10, 24, int(120 * fade * gfx.clamp(t / 0.2))))
        frame.paste(veil, (0, 0), veil)
        gfx.paste(frame, sp, self.W / 2, self.L["title_y"] - (1 - gfx.ease_out(p)) * 70,
                  alpha=gfx.clamp(p * 2) * fade, scale=1.12 - 0.12 * gfx.ease_out(p), anchor="c")

    @functools.lru_cache(maxsize=1)
    def _hook_sprite(self):
        return gfx.text_block(self.meta["title_plain"], self.L["title_size"], (255, 255, 255), self.L["title_w"],
                              keys=self.meta.get("title_keys", []), key_color=gfx.rgb(self.th["hl"]), stroke=10,
                              stroke_fill=self.ink, say=self.say)

    def frame(self, f):
        t = f / self.fps
        i = max(0, bisect.bisect_right(self.starts, t) - 1)
        sh = self.shots[i]
        lt = t - sh["start"]
        frame = self._shot(sh, t)
        tr = sh.get("tr")
        if i > 0 and tr in ("tear", "whip") and lt < (0.5 if tr == "tear" else 0.22):
            if i not in self._prev:
                self._prev = {i: self._shot(self.shots[i - 1], sh["start"] - 1.0 / self.fps)}
            old = self._prev[i]
            frame = gfx.tear(old, frame, lt / 0.5, self.edge) if tr == "tear" else gfx.whip(old, frame, lt / 0.22)
        if sh.get("flash") and lt < 0.3:
            frame = Image.blend(frame, Image.new("RGB", frame.size, (255, 255, 255)), 0.75 * (1 - lt / 0.3))
        if t < 0.25:                                           # opening flash
            frame = Image.blend(frame, Image.new("RGB", frame.size, (255, 255, 255)), 0.9 * (1 - t / 0.25))
        self._hook(frame, t)
        for sp, x, y in self.ui:
            gfx.paste(frame, sp, x, y)
        if sh["kind"] in ("media", "text"):
            chip = self.chips[sh["chapter"]] if sh.get("chapter") is not None else None
            if chip is not None:
                x0, y0 = self.L["badge_xy"]
                if self.meta["aspect"] == "9:16":
                    gfx.paste(frame, chip, x0, y0 + self.badge_h + 12)
                else:
                    gfx.paste(frame, chip, x0 + self.badge_w + 14, y0 + (self.badge_h - chip.size[1]) / 2)
            if sh["kind"] == "media" and sh["layout"] == "full" and self.handle:
                gfx.paste(frame, self.handle, self.W / 2 - self.handle.size[0] / 2, self.L["handle_y"])
            self._draw_caption(frame, t)
        d = ImageDraw.Draw(frame)
        y = 0 if self.meta["aspect"] == "9:16" else self.H - 10
        d.rectangle((0, y, int(self.W * t / self.total), y + 10), fill=self.acc)
        return frame

    def cover(self):
        """Thumbnail: first picture full-bleed + the hook title inside the picture + logo."""
        sh = next((s for s in self.shots if s["kind"] == "media"), self.shots[0])
        frame = self._shot(sh, sh["start"] + min(1.2, (sh["end"] - sh["start"]) * 0.8)).copy()
        veil = Image.new("RGBA", (self.W, self.H), (8, 10, 24, 120))
        frame.paste(veil, (0, 0), veil)
        if self.meta.get("title_plain"):
            gfx.paste(frame, self._hook_sprite(), self.W / 2, self.L["title_y"], anchor="c")
        for sp, x, y in self.ui:
            gfx.paste(frame, sp, x, y)
        return frame

    def close(self):
        for r in self._readers.values():
            r.close()


# -------------------------------------------------------------------- parallel encode
_RD = None                                                    # shared with forked workers (no pickling)


def _worker(args):
    a, b, out, crf = args
    rd = _RD
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{rd.W}x{rd.H}", "-r",
         str(rd.fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p",
         "-g", str(rd.fps * 2), out], stdin=subprocess.PIPE)
    try:
        for f in range(a, b):
            proc.stdin.write(rd.frame(f).tobytes())
    finally:
        proc.stdin.close(); proc.wait(); rd.close()
    return out


def render(rd, out_path, workers=None, crf=21, tmp_dir=None):
    """Render all frames with `workers` processes and join the parts (video only, no audio)."""
    workers = workers or max(1, os.cpu_count() or 2)
    tmp_dir = tmp_dir or os.path.join(rd.dir, ".cache", "parts")
    os.makedirs(tmp_dir, exist_ok=True)
    rd.prepare()
    # cut the job at shot boundaries so no video reader has to seek into the middle of a clip
    bounds = [0]
    for k in range(1, workers):
        target = rd.nframes * k / workers
        st = min((int(round(s * rd.fps)) for s in rd.starts), key=lambda x: abs(x - target))
        if st > bounds[-1]:
            bounds.append(st)
    bounds.append(rd.nframes)
    jobs = [(bounds[i], bounds[i + 1], os.path.join(tmp_dir, f"part{i:02d}.mp4"), crf)
            for i in range(len(bounds) - 1)]
    global _RD
    _RD = rd
    ctx = mp.get_context("fork")
    with ctx.Pool(len(jobs)) as pool:
        parts = pool.map(_worker, jobs)
    lst = os.path.join(tmp_dir, "parts.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in parts)
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out_path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("concat failed: " + r.stderr[-400:])
    return out_path
