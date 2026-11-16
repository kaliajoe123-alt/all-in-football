#!/usr/bin/env python3
"""ພາກແບບກວນໆ — Lao banter voice-over with Gemini TTS (voice Puck).

Usage:
  python3 tts.py script.txt out.mp3 [--voice Puck] [--model gemini-3.8-flash-lite-tts]

API key: in a Claude cloud session the network proxy adds the `x-goog-api-key`
header itself (environment network secret for generativelanguage.googleapis.com).
On your own computer, set GEMINI_API_KEY instead.
If the model is out of quota (HTTP 429) the next model in FALLBACK is tried.
"""
import argparse, base64, io, json, os, subprocess, sys, tempfile, urllib.error, urllib.request, wave

STYLE = ("Witty, clear, fast-talking Lao football banter creator. Rapid continuous comedic pacing "
         "with lively quick breath beats right before punchlines, energetic fan excitement.")
FALLBACK = ["gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview"]
API = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"


def synth(text, voice, model):
    body = {"contents": [{"parts": [{"text": f"Read the following Lao text aloud in Lao. Style: {STYLE}\n\n{text}"}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
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
    ap.add_argument("script"); ap.add_argument("out")
    ap.add_argument("--voice", default="Puck")
    ap.add_argument("--model", default=None, help="try only this model")
    a = ap.parse_args()
    text = open(a.script, encoding="utf-8").read().strip()
    for model in ([a.model] if a.model else FALLBACK):
        try:
            wav = synth(text, a.voice, model)
            break
        except urllib.error.HTTPError as e:
            print(f"{model}: HTTP {e.code} {e.read()[:200]!r}", file=sys.stderr)
            if e.code != 429:
                sys.exit(1)
    else:
        sys.exit("ທຸກໂມເດລໝົດໂຄຕ້າ (429) — ລໍມື້ໃໝ່ ຫຼື ເປີດ billing ໃນ Google AI Studio")
    with tempfile.NamedTemporaryFile(suffix=".wav") as t:
        t.write(wav); t.flush()
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", t.name, "-af", "loudnorm=I=-16:TP=-1.5",
                        "-ar", "44100", "-b:a", "192k", a.out], check=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.out],
                               capture_output=True, text=True).stdout or 0)
    print(f"{a.out}  voice={a.voice}  model={model}  {dur:.1f}s")


if __name__ == "__main__":
    main()
