"""ເຄື່ອງມືຂໍ້ຄວາມລາວ: ຕັດຄຳ, ອ່ານຕົວເລກເປັນຄຳລາວ, ກຽມຂໍ້ຄວາມສຳລັບສຽງພາກ.

Lao text helpers: word segmentation, number -> Lao words, and the mapping between
what is SHOWN on screen (display tokens) and what is SPOKEN by the voice engine.
"""
import re

LAO = re.compile(r"[຀-໿]")
LATIN = re.compile(r"[A-Za-z]")
DIG = ["ສູນ", "ໜຶ່ງ", "ສອງ", "ສາມ", "ສີ່", "ຫ້າ", "ຫົກ", "ເຈັດ", "ແປດ", "ເກົ້າ"]
LAO_DIGITS = str.maketrans("໐໑໒໓໔໕໖໗໘໙", "0123456789")


def is_lao(s):
    return bool(LAO.search(s))


def _below_1000(n):
    out = ""
    h, r = divmod(n, 100)
    if h:
        out += DIG[h] + "ຮ້ອຍ"
    t, u = divmod(r, 10)
    if t == 1:
        out += "ສິບ"
    elif t == 2:
        out += "ຊາວ"
    elif t:
        out += DIG[t] + "ສິບ"
    if u:
        out += "ເອັດ" if (u == 1 and t >= 1) else DIG[u]
    return out


def int_words(n):
    """12345 -> ໜຶ່ງໝື່ນສອງພັນສາມຮ້ອຍສີ່ສິບຫ້າ"""
    n = int(n)
    if n == 0:
        return DIG[0]
    if n < 0:
        return "ລົບ" + int_words(-n)
    out = ""
    for value, name in ((10 ** 9, "ຕື້"), (10 ** 6, "ລ້ານ")):
        q, n = divmod(n, value)
        if q:
            out += int_words(q) + name
    for value, name in ((100000, "ແສນ"), (10000, "ໝື່ນ"), (1000, "ພັນ")):
        q, n = divmod(n, value)
        if q:
            out += DIG[q] + name
    return out + _below_1000(n)


def number_words(tok):
    """'52.6' -> ຫ້າສິບສອງຈຸດຫົກ · '35,000' -> ສາມໝື່ນຫ້າພັນ · '2-1' -> ສອງຕໍ່ໜຶ່ງ · '74%' -> ...ເປີເຊັນ"""
    tok = tok.translate(LAO_DIGITS)
    pct = tok.endswith("%")
    tok = tok.rstrip("%")
    m = re.fullmatch(r"(\d+)[-–:](\d+)", tok)
    if m:                                             # score line
        return int_words(m.group(1)) + " ຕໍ່ " + int_words(m.group(2))
    tok = tok.replace(",", "")
    if "." in tok:
        a, b = tok.split(".", 1)
        w = int_words(a or 0) + "ຈຸດ" + "".join(DIG[int(c)] for c in b if c.isdigit())
    else:
        w = int_words(tok)
    return w + (" ເປີເຊັນ" if pct else "")


NUM = re.compile(r"[\d໐-໙][\d໐-໙,]*(?:\.[\d໐-໙]+)?(?:[-–:][\d໐-໙]+)?%?")
_seg = None


def _lao_words(s):
    """Segment a run of Lao text into words (laonlp; falls back to cluster-ish chunks)."""
    global _seg
    if _seg is None:
        try:
            from laonlp.tokenize import word_tokenize
            _seg = word_tokenize
        except Exception:                               # pragma: no cover
            _seg = lambda t: re.findall(r"[຀-໿]{1,6}|[^຀-໿]+", t)
    return [w for w in _seg(s) if w]


def tokenize(text, say=None):
    """Split display text into tokens: Lao words, Latin words/names, numbers, spaces, punctuation.
    Multi-word names listed in `say` stay as ONE token so they can be highlighted and pronounced."""
    say = say or {}
    out = []
    keys = sorted(say, key=len, reverse=True)
    pat = "|".join(re.escape(k) for k in keys)
    rx = re.compile(f"({pat})|({NUM.pattern})|([A-Za-z][A-Za-z'’.\\-]*)|(\\s+)" if pat
                    else f"(\\b\\B)|({NUM.pattern})|([A-Za-z][A-Za-z'’.\\-]*)|(\\s+)")
    pos = 0
    for m in rx.finditer(text):
        if m.start() > pos:
            out += _lao_or_punct(text[pos:m.start()])
        if m.group(0):
            out.append(m.group(0) if not m.group(4) else " ")
        pos = m.end()
    if pos < len(text):
        out += _lao_or_punct(text[pos:])
    return [t for t in out if t]


def _lao_or_punct(s):
    out = []
    for part in re.findall(r"[຀-໿]+|[^຀-໿]+", s):
        out += _lao_words(part) if is_lao(part) else [part]
    return out


PAUSE = "…"                                       # marks a dramatic pause ("..." in the script)


def spoken_form(tok, say=None, prev="", english=False, punct=False):
    """What the voice says for one display token ('' = silent). Returns (text, ok).
    english=True: Latin words are passed on unchanged so a bilingual voice reads them as real English;
    a `say:` entry still wins when its value is itself Latin (a respelling such as Neuer -> Noy-er)."""
    say = say or {}
    if tok in say and not (english and LATIN.search(tok) and is_lao(say[tok])):
        return say[tok], True
    if tok.strip() == "":
        return " ", True
    if tok == "ໆ":
        return prev, True                               # repeat mark
    if NUM.fullmatch(tok):
        return number_words(tok), True
    if is_lao(tok):
        if tok.endswith("ໆ") and len(tok) > 1:          # ແທ້ໆ -> ແທ້ແທ້
            base = tok.rstrip("ໆ")
            return base + base, True
        return tok.replace("ໆ", ""), True
    if LATIN.search(tok):
        if english:
            return tok, True
        low = {k.lower(): v for k, v in say.items()}
        if tok.lower() in low:
            return low[tok.lower()], True
        return "", False                                # unknown Latin word -> needs a `say:` entry
    if "..." in tok or "…" in tok:
        return " " + PAUSE + " ", True                  # dramatic pause: the voice really stops here
    if (english or punct) and tok.strip() and tok.strip()[-1] in ",.!?":
        return tok.strip()[-1] + " ", True              # expressive voices use punctuation for intonation
    return " ", True                                    # punctuation -> pause


def speech_plan(text, say=None, english=False, punct=False):
    """-> (tokens, spoken, spans, missing). spans[i] = (start, end) char range of token i inside `spoken`."""
    toks = tokenize(text, say)
    spoken, spans, missing, prev = "", [], [], ""
    for t in toks:
        s, ok = spoken_form(t, say, prev, english, punct)
        if not ok:
            missing.append(t)
        if s.strip():
            prev = s
            if spoken and not spoken.endswith(" ") and not is_lao(t):
                spoken += " "                           # numbers / names are separated from the word before
        a = len(spoken)
        spoken += s
        spans.append((a, len(spoken)))
        if s.strip() and not is_lao(t):
            spoken += " "
    return toks, spoken, spans, missing


def clean_markup(text):
    """Remove *key word* stars; return (plain_text, set_of_key_phrases)."""
    keys = [k.strip() for k in re.findall(r"\*([^*]+)\*", text)]
    return text.replace("*", ""), keys


def wrap_tokens(tokens, measure, max_width):
    """Greedy line wrap on token boundaries. `measure(str)` -> pixel width. Returns list of token lists."""
    lines, cur = [], []
    for t in tokens:
        if t == "\n":
            lines.append(cur); cur = []
            continue
        trial = "".join(cur + [t])
        if cur and measure(trial.rstrip()) > max_width:
            lines.append(cur)
            cur = [] if t.strip() == "" else [t]
        else:
            cur.append(t)
    if cur:
        lines.append(cur)
    return [l for l in ([_strip(l) for l in lines]) if l]


def _strip(line):
    while line and line[0].strip() == "":
        line = line[1:]
    while line and line[-1].strip() == "":
        line = line[:-1]
    return line
