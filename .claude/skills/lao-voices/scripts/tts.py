#!/usr/bin/env python3
"""ຄັງສຽງພາກລາວ — Gemini TTS ສຳລັບ 5 ສຽງທີ່ Joe ເລືອກ (voices.json).

Usage:
  python3 tts.py script.txt out.mp3 --pick ດຸດັນ      # ຫຼື --pick 1 (ອັນດັບ)
  python3 tts.py --list                               # ສະແດງ 5 ສຽງ

API key: in a Claude cloud session the network proxy adds the `x-goog-api-key`
header itself (environment network secret for generativelanguage.googleapis.com).
On your own computer, set GEMINI_API_KEY instead.
The voice's own model is tried first; on HTTP 429/503 the other TTS models are tried.
"""
import argparse, base64, io, json, os, subprocess, sys, tempfile, urllib.error, urllib.request, wave

HERE = os.path.dirname(os.path.abspath(__file__))
VOICES = json.load(open(os.path.join(HERE, "..", "voices.json"), encoding="utf-8"))["voices"]
MODELS = ["gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview"]
API = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"


def find(pick):
    for v in VOICES:
        if pick in (str(v["rank"]), v["nick"]):
            return v
    sys.exit(f"ບໍ່ມີສຽງ '{pick}'. ເລືອກໄດ້: " + ", ".join(f"{v['rank']} ({v['nick']})" for v in VOICES))


def synth(text, v, model):
    body = {"contents": [{"parts": [{"text": f"Read the following Lao text aloud in Lao. Style: {v['style']}\n\n{text}"}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": v["voice"]}}}}}
    headers = {"Content-Type": "application/json"}
    if os.environ.get("GEMINI_API_KEY"):
        headers["x-goog-api-key"] = os.environ["GEMINI_API_KEY"]
    req = urllib.request.Request(API.format(model), data=json.dumps(body).encode(), headers=headers)
    r = json.load(urllib.request.urlopen(req, timeout=300))
    part = r["candidates"][0]["content"]["parts"][0]["inlineData"]
    data, mime = base64.b64decode(part["data"]), part["mimeType"]
    if data[:4] == b"RIFF":                       # Gemini returns a WAV container
        return data
    rate = int(mime.split("rate=")[1].split(";")[0]) if "rate=" in mime else 24000
    buf = io.BytesIO()                            # raw 16-bit PCM -> wrap as WAV
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(data)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script", nargs="?"); ap.add_argument("out", nargs="?")
    ap.add_argument("--pick", help="ອັນດັບ 1-5 ຫຼື ຊື່ຫຼິ້ນ (ດຸດັນ, ກວນດີ, ຜູ້ຍິງ, ກວນ, ກວນຕີນ)")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list or not (a.script and a.out and a.pick):
        for v in VOICES:
            print(f"{v['rank']}. {v['character']} ({v['nick']}) — {v['voice']} · {v['use']}")
        return
    v = find(a.pick)
    text = open(a.script, encoding="utf-8").read().strip()
    wav = None
    for model in [v["model"]] + [m for m in MODELS if m != v["model"]]:
        try:
            wav = synth(text, v, model)
            break
        except urllib.error.HTTPError as e:
            print(f"{model}: HTTP {e.code} {e.read()[:160]!r}", file=sys.stderr)
            if e.code not in (429, 503):
                sys.exit(1)
    if wav is None:
        sys.exit("ທຸກໂມເດລໝົດໂຄຕ້າ/ບໍ່ວ່າງ — ລໍມື້ໃໝ່ ຫຼື ເປີດ billing ໃນ Google AI Studio")
    with tempfile.NamedTemporaryFile(suffix=".wav") as t:
        t.write(wav); t.flush()
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", t.name, "-af", "loudnorm=I=-16:TP=-1.5",
                        "-ar", "44100", "-b:a", "192k", a.out], check=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.out],
                               capture_output=True, text=True).stdout or 0)
    note = "" if model == v["model"] else f"  (ສຳຮອງ — ໂມເດລຫຼັກ {v['model']} ໃຊ້ບໍ່ໄດ້)"
    print(f"{a.out}  {v['rank']}. ({v['nick']}) voice={v['voice']}  model={model}  {dur:.1f}s{note}")


if __name__ == "__main__":
    main()
