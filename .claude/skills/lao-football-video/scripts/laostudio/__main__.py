"""python -m laostudio <command>

  new   <project> [--title "..."]      ສ້າງໂຟນເດີໂປຣເຈັກ + script.md ຕົວຢ່າງ
  check <project>                      ກວດ script.md (ຄຳອ່ານ, ຄຳສັ່ງ) ໂດຍບໍ່ render
  plan  <project>                      ສຽງພາກ + ຫາ footage + ແຜນຊັອດ (ບໍ່ render)
  run   <project> [--aspect 9:16] [--both] [--workers N] [--offline] [--force]

  voices                               ລາຍຊື່ສຽງພາກ (voice cards)
  voice-design <name> --desc "..."     ສ້າງສຽງໃໝ່ຈາກຄຳບັນຍາຍ (ພາສາອັງກິດ) ດ້ວຍ VoxCPM2
  voice-add <name> --wav f --text ".." ສ້າງສຽງຈາກໄຟລ໌ອັດຂອງເຈົ້າຂອງສຽງເອງ
  voice-test --voices a,b --out dir    ສັງເຄາະປະໂຫຍກທົດລອງດ້ວຍແຕ່ລະສຽງ
"""
import argparse, sys

from . import pipeline, script


def main(argv=None):
    ap = argparse.ArgumentParser(prog="laostudio", description="Lao football video studio")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new"); n.add_argument("project"); n.add_argument("--title")
    c = sub.add_parser("check"); c.add_argument("project")
    for name in ("plan", "run"):
        r = sub.add_parser(name); r.add_argument("project")
        r.add_argument("--aspect", choices=["16:9", "9:16"]); r.add_argument("--both", action="store_true")
        r.add_argument("--workers", type=int); r.add_argument("--offline", action="store_true")
        r.add_argument("--force", action="store_true"); r.add_argument("--crf", type=int, default=21)
    sub.add_parser("voices")
    vd = sub.add_parser("voice-design"); vd.add_argument("name"); vd.add_argument("--desc", required=True)
    vd.add_argument("--text"); vd.add_argument("--label", default=""); vd.add_argument("--gender", default="")
    va = sub.add_parser("voice-add"); va.add_argument("name"); va.add_argument("--wav", required=True)
    va.add_argument("--text", required=True); va.add_argument("--label", default="")
    va.add_argument("--gender", default="")
    vt = sub.add_parser("voice-test"); vt.add_argument("--voices"); vt.add_argument("--out", default="voice_samples")
    vt.add_argument("--text")
    a = ap.parse_args(argv)
    if a.cmd.startswith("voice"):
        return voices_cmd(a)
    try:
        if a.cmd == "new":
            print(pipeline.new_project(a.project, a.title))
        elif a.cmd == "check":
            doc = script.parse(a.project.rstrip("/") + "/script.md")
            probs, notes = script.check(doc)
            for x in notes:
                print("ໝາຍເຫດ:", x)
            for x in probs:
                print("✗", x)
            n_lines = sum(len(ch["lines"]) for ch in doc["chapters"])
            print(f"{len(doc['chapters'])} ບົດ, {n_lines} ປະໂຫຍກ — " + ("ຜ່ານ ✓" if not probs else f"{len(probs)} ບັນຫາ"))
            return 1 if probs else 0
        else:
            aspects = ["16:9", "9:16"] if a.both else [a.aspect]
            for asp in aspects:
                pipeline.run(a.project, aspect=asp, workers=a.workers, offline=a.offline, force=a.force,
                             plan_only=a.cmd == "plan", crf=a.crf)
    except script.ScriptError as e:
        print("ຜິດພາດ:", e, file=sys.stderr)
        return 2
    return 0


REF_TEXT = ("ໂອ້ໂຫ ພີ່ນ້ອງເອີ້ຍ! ມື້ນີ້ມີເລື່ອງມັນໆ ມາເລົ່າສູ່ຟັງ. ບານເຕະຄືນນີ້ ບໍ່ທຳມະດາແທ້ໆ, "
            "ເຊື່ອບໍ່ວ່າເກີດຫຍັງຂຶ້ນ?")
# Joe's own example of emotional control: one comeback story in four moods
TEST_LINES = [
    ("hook", "ເຈົ້າເຊື່ອບໍ່... ທີມທີ່ຖືກນຳສອງປະຕູ ແລະເກືອບຈະໝົດຫວັງ ກັບສາມາດປ່ຽນທຸກຢ່າງໄດ້!"),
    ("suspense", "ເວລາເຫຼືອບໍ່ຫຼາຍ... ແຟນບານບາງຄົນເລີ່ມຖອດໃຈ... ແຕ່ຢູ່ໆ ທຸກຢ່າງກໍປ່ຽນໄປ!"),
    ("climax", "ປະຕູທຳອິດມາແລ້ວ! ປະຕູທີສອງຕາມມາ! ແລະປະຕູສຸດທ້າຍ... ໂອ້ໂຫ! ນີ້ມັນປາຕິຫານຊັດໆ!"),
    ("calm", "ນີ້ແຫຼະບານເຕະ... ຕາບໃດທີ່ກຳມະການຍັງບໍ່ເປົ່ານົກຫວີດ ທຸກຢ່າງກໍຍັງເປັນໄປໄດ້!"),
]


def voices_cmd(a):
    import os, subprocess
    from . import laotext, voice
    if a.cmd == "voices":
        for n, c in voice.list_cards().items():
            print(f"vox:{n:<18} {c.get('gender', ''):<5} {c.get('label', '')}  — {c.get('desc', '') or c.get('engine', '')}")
        print("mms                    ສຽງ AI ຮ່າງ (16 kHz, CC BY-NC)")
        return 0
    if a.cmd == "voice-design":
        print(voice.design_voice(a.name, a.desc, a.text or REF_TEXT, label=a.label, gender=a.gender))
        return 0
    if a.cmd == "voice-add":
        print(voice.add_voice(a.name, a.wav, a.text, label=a.label, gender=a.gender))
        return 0
    import numpy as np
    from . import sound
    cards = voice.list_cards()
    names = [n for n in (a.voices.split(",") if a.voices else cards) if n]
    os.makedirs(a.out, exist_ok=True)
    lines = [("story", a.text)] if a.text else TEST_LINES
    for n in names:
        sents = voice.synth_sentences([t for _, t in lines], {"voice": n if n in ("mms",) else "vox:" + n},
                                      os.path.join(a.out, ".cache"), emos=[e for e, _ in lines])
        parts = []
        for s_ in sents:
            parts += [s_["audio"], np.zeros(int(s_["gap"] * voice.SR), np.float32)]
            print(f"  {n:<8}{s_['emo']:<9}{voice_stats(s_['audio'], s_['spoken'])}", flush=True)
        wav = os.path.join(a.out, n + ".wav")
        voice.write_wav(wav, np.concatenate(parts))
        gain = -16.0 - sound.loudness(wav, sound.VOICE_FX)        # one fixed gain: the dynamics stay
        mp3 = os.path.join(a.out, n + ".mp3")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", wav, "-af",
                        f"{sound.VOICE_FX},volume={gain:.2f}dB,alimiter=limit=0.84:level=disabled", "-b:a", "160k",
                        mp3], check=True)
        os.remove(wav)
        print(mp3, flush=True)
    return 0


def voice_stats(y, text):
    """Objective proxies for a performance: pitch, pitch movement, level, pace."""
    import numpy as np
    from . import voice
    x = voice.resample(y, voice.SR, 16000)
    f = []
    for i in range(0, len(x) - 1024, 320):
        w = x[i:i + 1024] * np.hanning(1024)
        if np.sqrt((w ** 2).mean()) < 0.012:
            continue
        ac = np.correlate(w, w, "full")[1023:]
        ac /= ac[0] + 1e-9
        k = 40 + int(np.argmax(ac[40:266]))
        if ac[k] > 0.45:
            f.append(16000 / k)
    f = np.array(f) if f else np.array([1.0])
    loud = y[np.abs(y) > 0.02]
    rms = 20 * np.log10(float(np.sqrt((loud ** 2).mean())) + 1e-9) if len(loud) else -99
    n = sum(1 for c in text if c.strip() and c not in ".!?,…")
    return (f"pitch {np.median(f):4.0f} Hz  movement ±{np.std(12 * np.log2(f / np.median(f))):.1f} st  "
            f"level {rms:5.1f} dB  pace {n / (len(y) / voice.SR):4.1f} ch/s  {len(y) / voice.SR:4.1f} s")


if __name__ == "__main__":
    sys.exit(main())
