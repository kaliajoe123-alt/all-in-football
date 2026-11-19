#!/usr/bin/env python3
"""ສ້າງສຽງພາກ 2 ຄົນ (Gemini multi-speaker) ຈາກ script.md ທີ່ທຸກແຖວມີ `spk:`.

  python3 video-studio/duo_voice.py video-studio/projects/<ຊື່> [--dry]
ຄົນເວົ້າ → ສຽງ (ຈາກ .claude/skills/lao-voices/voices.json ຕາມຊື່ຫຼິ້ນ):
  ຈັນທີ = (ຜູ້ຍິງ) Zephyr · ໂຄ້ດ = (ດຸດັນ) Charon
ສ້າງທີລະບົດ (1 request/ບົດ), ຕໍ່ກັນດ້ວຍຊ່ວງງຽບ 0.7 ວິ → <project>/voice.wav, ແລ້ວ script ໃຊ້ `voice: file:voice.wav`.
Chapter WAVs are cached in <project>/.cache/duo/ so a re-run only re-synthesizes changed chapters.
"""
import base64, hashlib, json, os, sys, time, urllib.error, urllib.request, wave, io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, ".claude/skills/lao-football-video/scripts"))
from laostudio import script as S, laotext  # noqa: E402

SPEAKERS = {"ຈັນທີ": ("Chanthy", "Zephyr"), "ໂຄ້ດ": ("Coach", "Charon")}
MODELS = os.environ.get("DUO_MODELS", "gemini-3.8-flash-tts,gemini-3.8-flash-lite-tts").split(",")
API = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
SR = 24000
MAX_CHARS = int(os.environ.get("DUO_MAX_CHARS", "1500"))


def chapter_parts(ch, say):
    parts = []
    for l in ch["lines"]:
        spk = l["d"].get("spk")
        if spk not in SPEAKERS:
            sys.exit(f"ແຖວ {l['no']}: spk ຕ້ອງເປັນ {list(SPEAKERS)} (ໄດ້ '{spk}')")
        spoken = laotext.speech_plan(l["text"], say)[1].strip()
        name = SPEAKERS[spk][0]
        if parts and parts[-1][0] == name:
            parts[-1] = (name, parts[-1][1] + " " + spoken)
        else:
            parts.append((name, spoken))
    return parts


LEGACY = {"gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"}  # "Name: text" format


def synth(parts):
    for model in MODELS:
        r = _synth(parts, model)
        if r:
            return r
    sys.exit("ທຸກໂມເດລໃຊ້ບໍ່ໄດ້ (ໂຄຕ້າ/ບໍ່ວ່າງ)")


def _synth(parts, model):
    if model in LEGACY:
        contents = [{"parts": [{"text": "TTS the following conversation in Lao between " + " and ".join(n for n, _ in SPEAKERS.values())
                                + ":\n" + "\n".join(f"{s}: {t}" for s, t in parts)}]}]
    else:
        contents = [{"role": "user", "parts": [{"text": t, "speechMetadata": {"speaker": s}} for s, t in parts]}]
    body = {"contents": contents,
            "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"multiSpeakerVoiceConfig": {
                "speakerVoiceConfigs": [{"speaker": n, "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": v}}}
                                        for n, v in SPEAKERS.values()]}}}}
    headers = {"Content-Type": "application/json"}
    if os.environ.get("GEMINI_API_KEY"):
        headers["x-goog-api-key"] = os.environ["GEMINI_API_KEY"]
    if True:
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(API.format(model), data=json.dumps(body).encode(),
                                                                         headers=headers), timeout=600))
            d = base64.b64decode(r["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
            if d[:4] == b"RIFF":
                w = wave.open(io.BytesIO(d)); assert w.getframerate() == SR; d = w.readframes(w.getnframes())
            return d, model
        except urllib.error.HTTPError as e:
            msg = e.read()
            print(f"  {model}: HTTP {e.code} {msg[:150]!r}", file=sys.stderr)
            if e.code == 429 and b"PerMinute" in msg and b"PerDay" not in msg:
                time.sleep(65)                                  # per-minute limit: wait and retry once
                return _synth(parts, model)
            if e.code not in (429, 500, 503):
                sys.exit(1)
    return None


def main():
    proj = sys.argv[1]
    doc = S.parse(os.path.join(proj, "script.md"))
    say = doc["meta"]["say"]
    cache = os.path.join(proj, ".cache", "duo"); os.makedirs(cache, exist_ok=True)
    pcm, used = b"", []
    # group chapters into batches of ~MAX_CHARS so a whole video needs only a few requests
    batches, cur = [], []
    for ch in doc["chapters"]:
        if cur and sum(len(t) for c in cur for _, t in chapter_parts(c, say)) + sum(len(t) for _, t in chapter_parts(ch, say)) > MAX_CHARS:
            batches.append(cur); cur = []
        cur.append(ch)
    batches.append(cur)
    for i, chs in enumerate(batches):
        ch = {"title": " + ".join(c["title"] for c in chs)}
        parts = [p for c in chs for p in chapter_parts(c, say)]
        chars = sum(len(t) for _, t in parts)
        key = hashlib.sha1(json.dumps([parts, SPEAKERS], ensure_ascii=False).encode()).hexdigest()[:12]
        f = os.path.join(cache, f"{i:02d}_{key}.pcm")
        if "--dry" in sys.argv:
            print(f"ບົດ {i}: {len(parts)} ທ່ອນ, {chars} ຕົວອັກສອນ, ~{chars / 11.5:.0f} ວິ"); continue
        if os.path.exists(f):
            d = open(f, "rb").read()
            model = "cache:" + (open(f + ".model").read() if os.path.exists(f + ".model") else "?")
        else:
            d, model = synth(parts); open(f, "wb").write(d); open(f + ".model", "w").write(model); time.sleep(20)
        used.append(model)
        print(f"ບົດ {i} '{ch['title']}': {len(d) / 2 / SR:.1f} ວິ  ({model})", flush=True)
        pcm += d + b"\0\0" * int(0.7 * SR)
    if "--dry" in sys.argv:
        return
    out = os.path.join(proj, "voice.wav")
    raw = os.path.join(proj, ".cache", "duo", "voice_raw.wav")
    with wave.open(raw, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)
    tempo = float(os.environ.get("DUO_TEMPO", "1.25"))          # Joe: ໄວຂຶ້ນ 20-30% (pitch ຄືເດີມ)
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", f"atempo={tempo}", out], check=True)
    dur = len(pcm) / 2 / SR / tempo
    print(f"{out}: {dur / 60:.1f} ນາທີ (ໄວ x{tempo}) · ໂມເດລ: {sorted(set(used))}")


if __name__ == "__main__":
    main()
