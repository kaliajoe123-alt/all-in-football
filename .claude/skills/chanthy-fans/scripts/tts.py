#!/usr/bin/env python3
"""Gemini TTS -> MP3 for Lao voice-overs (ຈັນທີ / ພາກແບບກວນໆ).

usage: tts.py SCRIPT.txt OUT.mp3 [--voice Zephyr] [--style "..."] [--models m1,m2,...]

The voice and style default to the ones Joe approved for this skill (see VOICE / STYLE below).
API key: GEMINI_API_KEY in the environment; in a Claude cloud session the network proxy adds the
x-goog-api-key header for generativelanguage.googleapis.com, so no key is needed in the script.
On a quota / not-found error the next model in the list is tried; the model used is printed.
"""
import argparse, base64, json, os, subprocess, sys, tempfile, urllib.error, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.basename(HERE)
PRESETS = {
    "chanthy-fans": dict(
        voice="Zephyr",
        models=["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts", "gemini-3.1-flash-tts-preview"],
        style="Warm, spirited, expressive young Lao female football fan-zone host. Lively post-match "
              "conversational pace with genuine laughs, excited sighs, and relatable fan reactions."),
    "pak-kuan": dict(
        voice="Puck",
        models=["gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview"],
        style="Witty, clear, fast-talking Lao football banter creator. Rapid continuous comedic pacing with "
              "lively quick breath beats right before punchlines, energetic fan excitement."),
}
P = PRESETS.get(SKILL, PRESETS["chanthy-fans"])
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def synth(text, voice, style, model):
    body = {
        "contents": [{"parts": [{"text": f"Speak in Lao. Style: {style}\n\n{text}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    headers = {"Content-Type": "application/json"}
    if os.environ.get("GEMINI_API_KEY"):
        headers["x-goog-api-key"] = os.environ["GEMINI_API_KEY"]
    req = urllib.request.Request(URL.format(model=model), json.dumps(body).encode(), headers)
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.load(r)
    part = data["candidates"][0]["content"]["parts"][0]["inlineData"]
    rate = 24000
    for kv in part.get("mimeType", "").split(";"):
        if kv.strip().startswith("rate="):
            rate = int(kv.split("=")[1])
    return base64.b64decode(part["data"]), rate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script"); ap.add_argument("out")
    ap.add_argument("--voice", default=P["voice"]); ap.add_argument("--style", default=P["style"])
    ap.add_argument("--models", default=",".join(P["models"]))
    a = ap.parse_args()
    text = open(a.script, encoding="utf-8").read().strip()
    last = None
    for model in [m for m in a.models.split(",") if m]:
        try:
            pcm, rate = synth(text, a.voice, a.style, model)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            last = f"{model}: HTTP {e.code} {msg}"
            if e.code in (404, 429, 500, 503):            # not available / out of quota -> next model
                print(f"  ! {last} -> ລອງໂມເດລຕໍ່ໄປ", file=sys.stderr)
                continue
            sys.exit("TTS ຜິດພາດ: " + last + ("\n(ບໍ່ມີ API key? ເບິ່ງ 'ຂໍ້ຈຳກັດ' ໃນ SKILL.md)" if e.code in (401, 403) else ""))
        except (KeyError, IndexError) as e:
            last = f"{model}: ຄຳຕອບບໍ່ມີສຽງ ({e})"
            print("  ! " + last, file=sys.stderr)
            continue
        raw = tempfile.mktemp(suffix=".pcm")
        open(raw, "wb").write(pcm)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(rate), "-ac", "1", "-i", raw,
                        "-af", "loudnorm=I=-16:TP=-1.5", "-ar", "44100", "-b:a", "192k", a.out], check=True)
        os.remove(raw)
        dur = len(pcm) / 2 / rate
        print(f"ສຳເລັດ: {a.out}  ຍາວ {dur:.1f} ວິ  ໂມເດລ {model}  ສຽງ {a.voice}")
        return
    sys.exit("ທຸກໂມເດລໃຊ້ບໍ່ໄດ້ (ໂຄຕ້າໝົດ?). ຂໍ້ຜິດພາດສຸດທ້າຍ: " + str(last))


if __name__ == "__main__":
    main()
