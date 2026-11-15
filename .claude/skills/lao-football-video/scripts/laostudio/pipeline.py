"""ສາຍການຜະລິດອັດຕະໂນມັດ: script.md -> ສຽງພາກ -> footage -> ຕັດຕໍ່ -> ສຽງ -> ໄຟລ໌ພ້ອມໂພສ.

One command does every step and leaves a report, so the only human (or Claude) work is the script.
"""
import json, os, re, shutil, subprocess, sys, time

import numpy as np
from PIL import Image

from . import footage, gfx, render, script, sound, voice


def log(msg):
    print(msg, flush=True)


def _ts(t):
    h, r = divmod(max(0.0, t), 3600); m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"


def slugify(s):
    s = re.sub(r"[^\w຀-໿]+", "_", s, flags=re.U).strip("_")
    return s[:60] or "video"


def run(project, aspect=None, workers=None, offline=False, force=False, plan_only=False, crf=21):
    t0 = time.time()
    project = os.path.abspath(project)
    doc = script.parse(os.path.join(project, "script.md"))
    meta = doc["meta"]
    if aspect:
        meta["aspect"] = aspect
    if meta["aspect"] not in render.LAYOUT:
        raise script.ScriptError("aspect ຕ້ອງເປັນ 16:9 ຫຼື 9:16")
    probs, notes = script.check(doc)
    for n in notes:
        log("  ໝາຍເຫດ: " + n)
    if probs:
        log("ພົບບັນຫາໃນ script.md:")
        for p in probs:
            log("  ✗ " + p)
        if not force:
            raise script.ScriptError("ແກ້ script.md ກ່ອນ (ຫຼື ໃຊ້ --force)")
    theme = gfx.load_brand(str(meta.get("brand", "allin")), project)
    cache = os.path.join(project, ".cache")
    out_dir = os.path.join(project, "out")
    os.makedirs(cache, exist_ok=True); os.makedirs(out_dir, exist_ok=True)
    lines = [l["text"] for c in doc["chapters"] for l in c["lines"]]

    # 1 ── voice ------------------------------------------------------------------------------
    eng = str(meta.get("voice", "mms"))
    removed = 0.0
    if eng.startswith("file:"):
        log(f"[1/6] ສຽງພາກ: ໃຊ້ໄຟລ໌ອັດສຽງ {eng[5:]}")
        sents, rec, removed = voice.align_recording(os.path.join(project, eng[5:]), lines, meta)
    else:
        log(f"[1/6] ສຽງພາກ: ສັງເຄາະ {len(lines)} ປະໂຫຍກ ດ້ວຍ {eng}")
        sents, rec = voice.synth_sentences(lines, meta, os.path.join(cache, "voice")), None
    tl = script.build_timeline(doc, sents)
    meta["_hook_end"] = float(min(4.0, max(2.6, tl["sentences"][0]["end"])))

    # 2 ── footage ----------------------------------------------------------------------------
    log(f"[2/6] ຫາ footage ສຳລັບ {sum(1 for s in tl['shots'] if s['kind'] == 'media')} ຊັອດ")
    finder = footage.Finder(project, theme, online=not offline)
    for sh in tl["shots"]:
        if sh["kind"] == "media" and sh.get("media"):
            sh["asset"] = finder.find(sh["media"])
            sh["file"] = finder.titles.get(sh["asset"]) or (os.path.basename(sh["asset"]) if sh["asset"] else None)
    srcs = sorted({c["source"] for c in finder.credits})
    meta["_credit_line"] = ("ຮູບປະກອບ: " + ", ".join(srcs) + " · ລາຍຊື່ເຈົ້າຂອງຮູບຢູ່ໃນຄຳບັນຍາຍ") if srcs else ""
    if finder.missing:
        log("  ! ຫາບໍ່ພົບ: " + "; ".join(sorted(set(finder.missing))))

    rd = render.Renderer(tl, meta, theme, project)
    name = slugify(str(meta.get("slug") or meta["title_plain"])) + ("_9x16" if meta["aspect"] == "9:16" else "")
    plan = {"total": round(tl["total"], 2), "aspect": meta["aspect"], "voice": eng,
            "shots": [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in s.items()
                       if k in ("i", "kind", "start", "end", "layout", "tr", "kb", "label", "stat", "quote", "title",
                                "file", "media")} for s in tl["shots"]]}
    json.dump(plan, open(os.path.join(out_dir, name + "_plan.json"), "w", encoding="utf-8"), ensure_ascii=False,
              indent=1)
    media_shots = [s["end"] - s["start"] for s in tl["shots"] if s["kind"] == "media"]
    log(f"      ຍາວ {tl['total']:.1f} ວິ · {len(tl['shots'])} ຊັອດ · ສະເລ່ຍ {np.mean(media_shots):.1f} ວິ/ຊັອດ")
    _footage_sheet(tl, os.path.join(out_dir, name + "_footage.jpg"))
    if plan_only:
        log("ແຜນ: " + os.path.join(out_dir, name + "_plan.json") + "  ·  ກວດຮູບ: " + name + "_footage.jpg")
        return {"plan": os.path.join(out_dir, name + "_plan.json"), "missing": finder.missing}

    # 3 ── narration track --------------------------------------------------------------------
    log("[3/6] ປະກອບສຽງພາກໃສ່ timeline")
    vo = np.zeros(int((tl["total"] + 0.5) * voice.SR), np.float32)
    if rec is not None:
        vo[:min(len(rec), len(vo))] = rec[:len(vo)]
    else:
        for s, sent in zip(sents, tl["sentences"]):
            a = int(sent["start"] * voice.SR)
            vo[a:a + len(s["audio"])] += s["audio"][:max(0, len(vo) - a)]
    vo_path = os.path.join(cache, "voice.wav")
    voice.write_wav(vo_path, vo)

    # 4 ── picture ----------------------------------------------------------------------------
    log(f"[4/6] render ພາບ {rd.nframes} ເຟຣມ ({rd.W}x{rd.H})")
    silent = os.path.join(cache, "silent.mp4")
    render.render(rd, silent, workers=workers, crf=crf)

    # 5 ── sound ------------------------------------------------------------------------------
    log("[5/6] ສຽງ: ເພງ + ເອັບເຟັກ + ຜະສົມ -14 LUFS")
    libs = finder.dirs
    music, music_name = sound.pick_music(project, meta.get("music"), libs, tl["total"])
    fx = None if str(meta.get("sfx", "on")).lower() in ("off", "none", "false") else \
        sound.sfx_track(tl["events"], tl["total"], libs)
    mix = os.path.join(cache, "mix.m4a")
    stems = sound.mix(vo_path, music, fx, tl["total"], mix, cache, music_vol=float(meta.get("music_vol", 0.2)))
    final = os.path.join(out_dir, name + ".mp4")
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", silent, "-i", mix, "-c:v", "copy", "-c:a", "copy",
                        "-shortest", "-movflags", "+faststart", final], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("mux failed: " + r.stderr[-400:])

    clean = None
    if meta.get("capcut"):
        log("      CapCut: render ສະບັບບໍ່ມີຄຳບັນຍາຍ")
        m2 = dict(meta); m2["captions"] = False
        rd2 = render.Renderer(tl, m2, theme, project)
        silent2 = os.path.join(cache, "silent_clean.mp4")
        render.render(rd2, silent2, workers=workers, crf=crf, tmp_dir=os.path.join(cache, "parts_clean"))
        clean = os.path.join(out_dir, name + "_clean.mp4")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", silent2, "-i", mix, "-c:v", "copy", "-c:a", "copy",
                        "-shortest", "-movflags", "+faststart", clean], check=True)

    # 6 ── package ----------------------------------------------------------------------------
    log("[6/6] ຈັດຊຸດສົ່ງ: ໜ້າປົກ, caption, SRT, credits, QA")
    cover = os.path.join(out_dir, name + "_cover.jpg")
    rd.cover().save(cover, quality=93)
    srt = os.path.join(out_dir, name + ".srt")
    with open(srt, "w", encoding="utf-8") as f:
        for i, (a, b, si, idx, flags, timed) in enumerate(rd.caps, 1):
            toks = tl["sentences"][si]["tokens_all"]
            text = "\n".join("".join(toks[j] for j in line).strip() for line in idx)
            f.write(f"{i}\n{_ts(a)} --> {_ts(b)}\n{text}\n\n")
    credits = os.path.join(out_dir, name + "_credits.txt")
    with open(credits, "w", encoding="utf-8") as f:
        f.write("ແຫຼ່ງຮູບ / Image credits\n")
        for c in finder.credits:
            f.write(f"- {c['title']} — {c['author']} — {c['license']} — {c['source']}\n  {c['page']}\n")
        srcs_txt = [s["src"] for s in tl["shots"] if s.get("src")]
        if srcs_txt:
            f.write("\nແຫຼ່ງຂໍ້ມູນ / Sources\n" + "".join(f"- {s}\n" for s in dict.fromkeys(srcs_txt)))
        if eng == "mms":
            f.write("\nສຽງພາກ: Meta MMS-TTS Lao (CC BY-NC 4.0) — ໃຊ້ສະເພາະວຽກບໍ່ຫວັງກຳໄລ / ຮ່າງ\n")
    post = os.path.join(out_dir, name + "_caption.txt")
    with open(post, "w", encoding="utf-8") as f:
        cap = str(meta.get("caption") or f"{meta['title_plain']}\n\n{meta.get('cta', '')}").strip()
        tags = str(meta.get("hashtags") or "#ເຕະບານ #ບານເຕະ #football #ALLIN").strip()
        f.write(cap + "\n\n" + tags + "\n")
        if finder.credits:
            auth = sorted({c["author"][:45] for c in finder.credits if c["author"] != "?"})
            f.write("\n📷 " + ", ".join(auth) + " (" + ", ".join(srcs) + " — ລິຂະສິດແຕ່ລະຮູບຢູ່ໃນ credits)\n")
    qa = os.path.join(out_dir, name + "_qa.jpg")
    _qa_sheet(final, tl, meta, qa)
    for k, p in stems.items():
        if os.path.exists(p):
            shutil.copy(p, os.path.join(out_dir, f"{name}_stem_{k}.wav"))
    dur = render.probe_duration(final)
    report = {"video": final, "cover": cover, "caption": post, "srt": srt, "credits": credits, "qa_sheet": qa,
              "clean_video": clean, "duration": round(dur, 2), "shots": len(tl["shots"]), "avg_shot": round(float(np.mean(media_shots)), 2),
              "voice": eng, "voice_removed_pauses": round(removed, 2), "music": music_name,
              "missing_footage": sorted(set(finder.missing)), "problems": probs,
              "placeholders": sum(1 for s in tl["shots"] if s["kind"] == "media" and not s.get("asset")),
              "render_seconds": round(time.time() - t0, 1)}
    json.dump(report, open(os.path.join(out_dir, name + "_report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    log(f"ສຳເລັດ: {final}  ({dur:.1f} ວິ, ໃຊ້ເວລາ {time.time() - t0:.0f} ວິ)")
    return report


def _footage_sheet(tl, out):
    """Numbered thumbnails of every picked picture/clip, so a wrong picture is caught BEFORE rendering."""
    from PIL import ImageDraw
    cells = []
    for s in tl["shots"]:
        if s["kind"] != "media":
            continue
        cell = Image.new("RGB", (320, 214), (40, 20, 20))
        p = s.get("asset")
        try:
            if p and render.is_video(p):
                r = subprocess.run(["ffmpeg", "-v", "error", "-ss", "1", "-i", p, "-frames:v", "1", "-f", "image2pipe",
                                    "-vcodec", "png", "-"], capture_output=True)
                import io
                im = Image.open(io.BytesIO(r.stdout)).convert("RGB")
            elif p:
                im = Image.open(p); im.draft("RGB", (640, 640)); im = im.convert("RGB")
            else:
                im = None
            if im:
                cell.paste(gfx.cover_fit_plain(im, 320, 180, 0.3), (0, 0))
        except Exception:
            pass
        d = ImageDraw.Draw(cell)
        q = (s.get("media") or {}).get("q", "")
        tag = f"#{s['i']} {s['start']:.0f}s  " + (q if p else "MISSING: " + q)
        d.rectangle((0, 180, 320, 214), fill=(16, 26, 58) if p else (150, 20, 20))
        gfx.draw_text(d, 6, 205, tag[:44], 19, (255, 255, 255))
        cells.append(cell)
    if not cells:
        return
    cols = 6
    sheet = Image.new("RGB", (cols * 320, ((len(cells) + cols - 1) // cols) * 214), (20, 20, 24))
    for i, c in enumerate(cells):
        sheet.paste(c, ((i % cols) * 320, (i // cols) * 214))
    sheet.save(out, quality=85)


def _qa_sheet(video, tl, meta, out):
    """Contact sheet of the moments a human should look at (hook, labels, stats, chapters, outro)."""
    times = [0.6, min(2.0, tl["total"] / 4)]
    for s in tl["shots"]:
        if s["kind"] == "chapter":
            times.append(s["start"] + 1.0)
        elif s.get("stat") and not s.get("stat_hold") or s.get("quote") or s.get("label"):
            times.append(s["start"] + 0.9)
        elif s["kind"] == "outro":
            times.append(s["start"] + 2.6)
    times = sorted(set(round(min(t, tl["total"] - 0.1), 2) for t in times))
    if len(times) > 15:
        step = len(times) / 15
        times = [times[int(i * step)] for i in range(14)] + [times[-1]]
    thumbs = []
    for t in times:
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", "-f", "image2pipe",
                            "-vcodec", "png", "-"], capture_output=True)
        if r.stdout:
            import io
            im = Image.open(io.BytesIO(r.stdout)).convert("RGB")
            w = 640 if im.size[0] > im.size[1] else 360
            thumbs.append(im.resize((w, int(im.size[1] * w / im.size[0])), Image.LANCZOS))
    if not thumbs:
        return
    cols = 3 if thumbs[0].size[0] > thumbs[0].size[1] else 5
    tw, th_ = thumbs[0].size
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th_), (30, 30, 34))
    for i, im in enumerate(thumbs):
        sheet.paste(im, ((i % cols) * tw, (i // cols) * th_))
    sheet.save(out, quality=88)


TEMPLATE = """---
title: ຫົວຂໍ້ທີ່ດຶງດູດ ມີ *ຄຳສຳຄັນ*
show: ຝອຍນອກເກມ
handle: "@ALLINFootball"
aspect: "16:9"          # 16:9 (YouTube/Facebook) ຫຼື 9:16 (TikTok/Reels)
voice: mms              # mms | edge:female | edge:male | file:voice.m4a
music: tension          # epic | tension | sad | fun | none
say:                    # ຄຳອ່ານລາວຂອງຊື່ພາສາອັງກິດ
  Pep Guardiola: ເປບ ກວາດິໂອລາ
caption: |
  ຂໍ້ຄວາມໂພສ ...
hashtags: "#ເຕະບານ #football #ALLIN"
---
# ເປີດເລື່ອງ
[img: football stadium night | full] ປະໂຫຍກເປີດທີ່ເຮັດໃຫ້ຄົນຢຸດເລື່ອນ!
[img: Pep Guardiola | label: Pep Guardiola] ປະໂຫຍກທີສອງ ເລົ່າວ່າໃຜ ແລະ ເກີດຫຍັງຂຶ້ນ.

# ຫົວຂໍ້ບົດທີ 1
[img: goalkeeper save | stat: 52.6% = ຈ່າຍບານສຳເລັດ | src: fbref.com] ຕົວເລກສຳຄັນ ພ້ອມແຫຼ່ງຂໍ້ມູນ.
"""


def new_project(path, title=None):
    os.makedirs(os.path.join(path, "assets"), exist_ok=True)
    f = os.path.join(path, "script.md")
    if not os.path.exists(f):
        t = TEMPLATE if not title else TEMPLATE.replace("ຫົວຂໍ້ທີ່ດຶງດູດ ມີ *ຄຳສຳຄັນ*", title)
        open(f, "w", encoding="utf-8").write(t)
    return f
