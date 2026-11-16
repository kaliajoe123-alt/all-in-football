"""ອ່ານ script.md (storyboard) ແລ້ວສ້າງ timeline ຂອງຊັອດ.

script.md =  YAML front matter  +  chapters (# ຫົວຂໍ້)  +  one spoken sentence per line:
    [img: Manuel Neuer 2014 | label: Manuel Neuer | stat: 52.6% = ຈ່າຍບານສຳເລັດ] ຂໍ້ຄວາມທີ່ພາກ ມີ *ຄຳສຳຄັນ*
See references/script-format.md in the skill for every directive.
"""
import math, os, re

import yaml

from . import laotext

DEFAULTS = {"aspect": "16:9", "voice": "vox:mun", "speed": 1.0, "music": "tension", "fps": 30, "captions": "key",
            "show": "", "handle": "", "narrator": "", "say": {}, "gap": 0.26, "chapter_cards": True,
            "max_shot": 4.4, "cta": "ກົດຕິດຕາມ ແລ້ວຄອມເມັ້ນບອກແດ່!", "brand": "allin"}
FLAGS = {"full", "card", "slow", "flash", "nocap"}
KEYS = {"img", "clip", "video", "label", "stat", "quote", "text", "sfx", "tr", "src", "kb", "emo"}


class ScriptError(Exception):
    pass


def parse(path):
    raw = open(path, encoding="utf-8").read().replace("\r\n", "\n")
    meta = dict(DEFAULTS)
    m = re.match(r"^---\n(.*?)\n---\n", raw, re.S)
    off = 0
    if m:
        meta.update(yaml.safe_load(m.group(1)) or {})
        off = raw[:m.end()].count("\n")
        raw = raw[m.end():]
    meta["say"] = {str(k): str(v) for k, v in (meta.get("say") or {}).items()}
    chapters, cur, problems = [], None, []
    for no, line in enumerate(raw.split("\n"), 1 + off):
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("<!--"):
            continue
        if line.startswith("#"):
            cur = {"title": line.lstrip("#").strip(), "lines": []}
            chapters.append(cur)
            continue
        if cur is None:
            cur = {"title": "", "lines": []}
            chapters.append(cur)
        d, text = {}, line
        m = re.match(r"^\[(.*?)\]\s*(.*)$", line)
        if m:
            text = m.group(2)
            for part in m.group(1).split("|"):
                part = part.strip()
                if not part:
                    continue
                if ":" in part and part.split(":", 1)[0].strip().lower() in KEYS:
                    k, v = part.split(":", 1)
                    d[k.strip().lower()] = v.strip()
                elif part.lower() in FLAGS:
                    d[part.lower()] = True
                else:
                    problems.append(f"ແຖວ {no}: ບໍ່ຮູ້ຈັກຄຳສັ່ງ '{part}'")
        plain, keys = laotext.clean_markup(text)
        if not plain.strip():
            problems.append(f"ແຖວ {no}: ບໍ່ມີຂໍ້ຄວາມພາກ")
            continue
        cur["lines"].append({"no": no, "text": plain.strip(), "keys": keys, "d": d})
    if not any(c["lines"] for c in chapters):
        raise ScriptError("script.md ບໍ່ມີແຖວພາກສຽງ")
    title, tkeys = laotext.clean_markup(str(meta.get("title", "")))
    meta["title_plain"], meta["title_keys"] = title, tkeys
    return {"meta": meta, "chapters": [c for c in chapters if c["lines"]], "problems": problems}


def check(doc):
    """Problems a writer must fix before rendering (Latin words with no Lao reading, missing visuals...)."""
    probs, say = list(doc["problems"]), doc["meta"]["say"]
    n_no_visual, total = 0, 0
    for c in doc["chapters"]:
        for l in c["lines"]:
            total += 1
            v = str(doc["meta"].get("voice", ""))
            english = v.startswith("vox") and str(doc["meta"].get("english", "lao")) == "native"
            miss = laotext.speech_plan(l["text"], say, english)[3]
            try:
                from .voice import emotion
                emotion(l["d"].get("emo"))
            except ValueError as e:
                probs.append(f"ແຖວ {l['no']}: {e}")
            if miss and not v.startswith("file"):
                probs.append(f"ແຖວ {l['no']}: ຕ້ອງເພີ່ມຄຳອ່ານລາວໃນ `say:` ສຳລັບ {', '.join(sorted(set(miss)))}")
            if not any(k in l["d"] for k in ("img", "clip", "video", "text", "quote")):
                n_no_visual += 1
    if not doc["meta"].get("title"):
        probs.append("front matter: ຕ້ອງມີ title (hook)")
    notes = []
    if n_no_visual:
        notes.append(f"{n_no_visual}/{total} ແຖວບໍ່ມີ img/clip — ຈະໃຊ້ຮູບຕໍ່ຈາກແຖວກ່ອນໜ້າ")
    return probs, notes


def _media_list(d):
    out = []
    for kind in ("clip", "video", "img"):
        if kind in d:
            for q in d[kind].split(";"):
                q = q.strip()
                if q:
                    n, at = 1, None
                    m = re.search(r"@([\d.]+)$", q)             # clip start in seconds: goal.mp4@12.5
                    if m:
                        at, q = float(m.group(1)), q[:m.start()].strip()
                    m = re.search(r"#(\d+)$", q)                # nth search result: Ederson #3
                    if m:
                        n, q = int(m.group(1)), q[:m.start()].strip()
                    out.append({"kind": kind, "q": q, "n": n, "at": at})
    return out


def build_timeline(doc, sents):
    """sents: voice.synth_sentences output in document order (may carry absolute 'start' for recordings).
    Returns dict(total, shots, sentences, chapters, events)."""
    meta = doc["meta"]
    fixed = sents and "start" in sents[0]
    gap, max_shot = float(meta["gap"]), float(meta["max_shot"])
    t = 0.35
    shots, sentences, chapters, events = [], [], [], []
    si, last_media, auto_n = 0, None, {}
    for ci, ch in enumerate(doc["chapters"]):
        card = bool(meta["chapter_cards"]) and ci > 0 and ch["title"] and not fixed
        if card:
            shots.append({"kind": "chapter", "start": t, "end": t + 1.7, "title": ch["title"], "chapter": ci,
                          "tr": "tear"})
            events.append({"t": t, "sfx": "tear"})
            t += 1.7
        chapters.append({"title": ch["title"], "start": sents[si]["start"] if fixed else t, "banner": bool(ch["title"]) and ci > 0 and not card})
        for l in ch["lines"]:
            s = sents[si]; si += 1
            if fixed:
                t = s["start"]
            d, dur = l["d"], s["dur"]
            a, b = t, t + dur
            sentences.append({"start": a, "end": b, "text": l["text"], "keys": l["keys"], "tokens": s["tokens"],
                              "tokens_all": s["tokens_all"], "nocap": bool(d.get("nocap")), "chapter": ci})
            media = _media_list(d)
            if "text" in d or ("quote" in d and not media):
                media = media or [None]
            if not media:
                if last_media:
                    auto_n[last_media["q"]] = auto_n.get(last_media["q"], last_media["n"]) + 1
                    media = [dict(last_media, n=auto_n[last_media["q"]], auto=True)]
                else:
                    media = [None]
            gap = float(s.get("gap", meta["gap"]))             # the emotion decides how long we breathe after it
            span = dur + (0 if fixed else gap)
            n = 1 if media == [None] else max(len(media), int(math.ceil(span / max_shot)))
            while len(media) < n:                        # long sentence: more pictures of the same subject
                base = next((m for m in reversed(media) if m), None)
                if base is None:
                    media.append(None); continue
                auto_n[base["q"]] = auto_n.get(base["q"], base["n"]) + 1
                media.append(dict(base, n=auto_n[base["q"]], auto=True))
            # cut points: equal parts snapped to the nearest word start
            cuts = [a]
            starts = [a + tk["a"] for tk in s["tokens"]]
            for k in range(1, n):
                target = a + span * k / n
                near = [x for x in starts if abs(x - target) < 0.9 and x > cuts[-1] + 1.2]
                cuts.append(min(near, key=lambda x: abs(x - target)) if near else target)
            cuts.append(a + span)
            for k in range(n):
                m = media[k]
                sh = {"kind": "media" if m else "text", "start": cuts[k], "end": cuts[k + 1], "media": m,
                      "sentence": len(sentences) - 1, "chapter": ci, "tr": d.get("tr", ""),
                      "layout": "full" if d.get("full") else ("card" if d.get("card") else ""),
                      "kb": d.get("kb", ""), "slow": bool(d.get("slow"))}
                if k == 0:
                    for key in ("label", "stat", "quote", "text"):
                        if key in d:
                            sh[key] = d[key]
                    if d.get("flash"):
                        sh["flash"] = True; events.append({"t": cuts[k], "sfx": "impact"})
                    if "sfx" in d and d["sfx"] != "none":
                        events.append({"t": cuts[k], "sfx": d["sfx"]})
                    if "stat" in d:
                        events.append({"t": cuts[k] + 0.3, "sfx": "pop"})
                    elif "label" in d:
                        events.append({"t": cuts[k] + 0.25, "sfx": "tick"})
                    if "quote" in d and "sfx" not in d:
                        events.append({"t": cuts[k], "sfx": "whoosh"})
                elif "stat" in d:
                    sh["stat"] = d["stat"]; sh["stat_hold"] = True
                if "src" in d and k == 0:
                    sh["src"] = d["src"]
                shots.append(sh)
                if m:
                    last_media = m
            t = b + gap
    end_voice = max(s["end"] for s in sentences)
    outro = max(end_voice + 0.25, shots[-1]["end"])
    shots[-1]["end"] = outro
    shots.append({"kind": "outro", "start": outro, "end": outro + 4.0, "tr": "tear"})
    events.append({"t": outro, "sfx": "tear"}); events.append({"t": outro + 1.0, "sfx": "pop"})
    events.append({"t": 0.05, "sfx": "impact"})
    # no shot shorter than 0.9 s: merge into the previous one
    clean = []
    for sh in shots:
        if clean and sh["kind"] == "media" and sh["end"] - sh["start"] < 0.9 and clean[-1]["kind"] == "media":
            clean[-1]["end"] = sh["end"]
            for key in ("label", "stat", "quote"):
                if key in sh and key not in clean[-1]:
                    clean[-1][key] = sh[key]
        else:
            clean.append(sh)
    for i, sh in enumerate(clean):
        sh["i"] = i
        if sh["kind"] == "media" and not sh["tr"]:
            sh["tr"] = ["cut", "pop", "cut", "slide", "cut", "pop", "whip"][i % 7] if i else "cut"
        if sh["tr"] in ("whip", "slide"):
            events.append({"t": sh["start"] - 0.05, "sfx": "whoosh"})
    return {"total": outro + 4.0, "shots": clean, "sentences": sentences, "chapters": chapters,
            "events": sorted(events, key=lambda e: e["t"]), "fixed_voice": bool(fixed)}
