"""ສຽງພາກລາວອັດຕະໂນມັດ (Lao voice-over).

Engines
  vox   - VoxCPM2 (Apache-2.0, 48 kHz, Lao supported). `voice: vox:<card>` speaks with a saved voice card
          (assets/voices/<card>/: a short reference clip + its text) so every sentence has the SAME voice.
          Cards are made by voice design (text description) or from a real recording. Slow on CPU.
  mms   - offline neural Lao voice (Meta MMS-TTS, ONNX, CPU). Gives exact per-word timing.
          Licence CC-BY-NC 4.0, 16 kHz -> quick drafts only.
  edge  - Microsoft neural voices lo-LA-KeomanyNeural (ຍິງ) / lo-LA-ChanthavongNeural (ຊາຍ) via `edge-tts`
          (needs open internet + websockets; not available inside the locked cloud sandbox).
  file  - the narrator's own recording (best quality). Sentences are aligned to the pauses in the recording.
"""
import hashlib, json, os, subprocess, sys, urllib.request, wave

import numpy as np

from . import laotext

SR = 48000                                                     # narration track sample rate
CACHE = os.path.expanduser(os.environ.get("LAOSTUDIO_CACHE", "~/.cache/laostudio"))
MMS_URL = "https://huggingface.co/willwade/mms-tts-multilingual-models-onnx/resolve/main/lao/"
EDGE_VOICES = {"female": "lo-LA-KeomanyNeural", "male": "lo-LA-ChanthavongNeural"}


def fetch(url, dest, ua="LaoVideoStudio/1.0"):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
    except Exception:
        r = subprocess.run(["curl", "-sSL", "--fail", "-A", ua, "-o", tmp, url], capture_output=True, text=True)
        if r.returncode != 0:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise RuntimeError(f"ດາວໂຫຼດບໍ່ໄດ້ / download failed: {url}\n{r.stderr[-300:]}")
    os.replace(tmp, dest)
    return dest


def atempo(y, speed):
    """Change speaking rate without changing pitch (ffmpeg atempo)."""
    import tempfile
    a, b = tempfile.mktemp(suffix=".wav"), tempfile.mktemp(suffix=".wav")
    write_wav(a, y)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", a, "-af", f"atempo={speed:.3f}", b], check=True)
    out = read_audio(b); os.remove(a); os.remove(b)
    return out


def read_audio(path, sr=None):
    sr = sr or SR
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                       capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg cannot read " + path + "\n" + r.stderr.decode()[-300:])
    return np.frombuffer(r.stdout, "<f4").copy()


def write_wav(path, x, sr=SR):
    x = np.clip(x, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1 if x.ndim == 1 else x.shape[1]); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def resample(y, sr_in, sr_out):
    if sr_in == sr_out or len(y) == 0:
        return y.astype(np.float32)
    try:
        from math import gcd
        from scipy.signal import resample_poly
        g = gcd(sr_in, sr_out)
        return resample_poly(y, sr_out // g, sr_in // g).astype(np.float32)
    except Exception:
        x = np.arange(int(len(y) * sr_out / sr_in)) * (sr_in / sr_out)
        return np.interp(x, np.arange(len(y)), y).astype(np.float32)


# ------------------------------------------------------------------ voice cards (VoxCPM2)
SKILL = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VOICE_DIRS = [os.path.join(SKILL, "assets", "voices")]


def load_card(name, project=None):
    """A voice card = folder with ref.wav (5-15 s of the voice), card.json {text, desc, label, gender}."""
    for d in ([os.path.join(project, "voices")] if project else []) + VOICE_DIRS:
        f = os.path.join(d, name, "card.json")
        if os.path.isfile(f):
            card = json.load(open(f, encoding="utf-8"))
            card["wav"] = os.path.join(d, name, "ref.wav")
            card["name"] = name
            return card
    raise ValueError(f"ບໍ່ພົບສຽງ '{name}' — ເບິ່ງລາຍຊື່ດ້ວຍ `studio voices`")


def list_cards(project=None):
    out = {}
    for d in VOICE_DIRS + ([os.path.join(project, "voices")] if project else []):
        for n in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if os.path.isfile(os.path.join(d, n, "card.json")):
                out[n] = load_card(n, project)
    return out


class Vox:
    def __init__(self):
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        os.environ.setdefault("TQDM_DISABLE", "1")
        import torch
        from voxcpm import VoxCPM
        torch.set_num_threads(os.cpu_count() or 2)
        print("  ໂຫຼດໂມເດລສຽງ VoxCPM2 ...", flush=True)
        self.m = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
        self.sr = self.m.tts_model.sample_rate

    def say(self, spoken, card=None, desc=None, style=None, steps=10, cfg=2.0):
        """card + style -> the card's timbre, performed in that style (emotion, energy)
        card only    -> closest copy of the card's voice (flat, neutral delivery)
        desc only    -> design a new voice from a description"""
        spoken = " ".join(spoken.split()).replace(" ,", ",").replace(" .", ".").replace(" !", "!").replace(" ?", "?")
        kw = dict(cfg_value=cfg, inference_timesteps=steps)
        if card and style and card.get("perform", True):
            kw.update(text=f"({style}){spoken}", reference_wav_path=card["wav"])
        elif card:
            kw.update(text=spoken, prompt_wav_path=card["wav"], prompt_text=card["text"],
                      reference_wav_path=card["wav"])
        else:
            kw.update(text=f"({desc}){spoken}" if desc else spoken)
        y = np.asarray(self.m.generate(**kw), dtype=np.float32).reshape(-1)
        return resample(y, self.sr, SR)


_VOX = None


def get_vox():
    """One loaded model per process (loading takes minutes)."""
    global _VOX
    _VOX = _VOX or Vox()
    return _VOX


def design_voice(name, desc, text, out_dir=None, label="", gender="", model=None):
    """Create a voice card from a natural-language description. Returns the card folder."""
    model = model or get_vox()
    y = model.say(text, desc=desc)
    y, _ = trim_silence(y)
    y = (y / (np.abs(y).max() + 1e-9) * 0.89).astype(np.float32)
    d = os.path.join(out_dir or VOICE_DIRS[0], name)
    os.makedirs(d, exist_ok=True)
    write_wav(os.path.join(d, "ref.wav"), y)
    json.dump({"text": text, "desc": desc, "label": label, "gender": gender, "engine": "VoxCPM2 voice design"},
              open(os.path.join(d, "card.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return d


def add_voice(name, wav, text, out_dir=None, label="", gender=""):
    """Voice card from a REAL recording (only the speaker's own voice, with their consent)."""
    y = read_audio(wav)
    y, _ = trim_silence(y)
    y = (y[:int(20 * SR)] / (np.abs(y).max() + 1e-9) * 0.89).astype(np.float32)
    d = os.path.join(out_dir or VOICE_DIRS[0], name)
    os.makedirs(d, exist_ok=True)
    write_wav(os.path.join(d, "ref.wav"), y)
    json.dump({"text": text, "desc": "", "label": label, "gender": gender, "engine": "recording"},
              open(os.path.join(d, "card.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return d


def _char_weights(spoken):
    """Relative duration of every character, borrowed from the MMS duration model (fast); uniform fallback."""
    try:
        global _MMS
        _MMS = globals().get("_MMS") or MMS()
        _, times = _MMS.say(spoken, 1.0)
        # the Lao duration model cannot time Latin letters: give English words ~65 ms per letter
        return [0.065 if laotext.LATIN.match(c) else max(0.0, b - a) for c, (a, b) in zip(spoken, times)]
    except Exception:
        return [0.0 if c.isspace() else 0.07 for c in spoken]


def _scaled_times(spoken, total, lead=0.04):
    w = _char_weights(spoken)
    s = sum(w) or 1.0
    out, t = [], lead
    for x in w:
        d = (total - 2 * lead) * x / s
        out.append((t, t + d)); t += d
    return out


# ------------------------------------------------------------------ MMS (offline)
class MMS:
    MAP = {"ຳ": "ໍາ", "ໜ": "ຫນ", "ໝ": "ຫມ", "ໞ": "ຍ", "ໟ": "ຍ"}

    def __init__(self):
        import onnxruntime as ort
        d = os.path.join(CACHE, "mms-lao")
        for f in ("model.onnx", "tokens.txt"):
            if not os.path.exists(os.path.join(d, f)):
                print(f"  ດາວໂຫຼດໂມເດລສຽງລາວ ({f}) ...", flush=True)
                fetch(MMS_URL + f, os.path.join(d, f))
        self.tok = {}
        for line in open(os.path.join(d, "tokens.txt"), encoding="utf-8").read().split("\n"):
            if line:
                c, i = line.rsplit(" ", 1)
                self.tok[c] = int(i)
        so = ort.SessionOptions(); so.intra_op_num_threads = max(1, (os.cpu_count() or 2) - 1)
        self.s = ort.InferenceSession(os.path.join(d, "model.onnx"), so, providers=["CPUExecutionProvider"])

    def say(self, spoken, speed=1.0):
        """-> (audio float32 @16k, char_times) ; char_times[i] = (start, end) seconds of spoken[i]."""
        ids, owner = [], []
        for ci, ch in enumerate(spoken):
            for c in self.MAP.get(ch, ch):
                if c in self.tok:
                    ids.append(self.tok[c]); owner.append(ci)
        if not ids:
            return np.zeros(int(0.2 * SR), np.float32), [(0.0, 0.0)] * len(spoken)
        x = [0]
        for i in ids:
            x += [i, 0]
        y, dur = self.s.run(None, {"x": np.array([x], np.int64), "x_length": np.array([len(x)], np.int64),
                                    "noise_scale": np.array([0.6], np.float32),
                                    "length_scale": np.array([1.0 / speed], np.float32),
                                    "noise_scale_w": np.array([0.75], np.float32)})
        y, dur = resample(y[0, 0].astype(np.float32), 16000, SR), dur[0, 0]
        cum = np.concatenate([[0], np.cumsum(dur)]) * 256.0 / 16000.0
        times, k = [None] * len(spoken), 0
        for k, ci in enumerate(owner):                  # token k sits at x-position 2k+1 (blank before it at 2k)
            a, b = cum[2 * k], cum[2 * k + 2]
            times[ci] = (a, b) if times[ci] is None else (times[ci][0], b)
        last = 0.0
        for i in range(len(times)):                     # silent chars (spaces dropped, etc.) take zero time
            if times[i] is None:
                times[i] = (last, last)
            last = times[i][1]
        return y, times


# ------------------------------------------------------------------ Edge (online)
def edge_say(spoken, voice, speed=1.0):
    import asyncio, tempfile
    import edge_tts
    rate = f"{int(round((speed - 1) * 100)):+d}%"
    tmp = tempfile.mktemp(suffix=".mp3")
    asyncio.run(edge_tts.Communicate(spoken, voice, rate=rate).save(tmp))
    y = read_audio(tmp); os.remove(tmp)
    return y, _proportional(spoken, len(y) / SR)


def _proportional(spoken, total, lead=0.05):
    w = [0.0 if c.isspace() else 1.0 for c in spoken]
    s = sum(w) or 1.0
    out, t = [], lead
    for x in w:
        d = (total - 2 * lead) * x / s
        out.append((t, t + d)); t += d
    return out


# ------------------------------------------------------------------ sentences
def trim_silence(y, thr=0.012, pad=0.06):
    env = np.abs(y)
    idx = np.where(env > thr)[0]
    if len(idx) == 0:
        return y, 0.0
    a = max(0, idx[0] - int(pad * SR)); b = min(len(y), idx[-1] + int(pad * SR))
    return y[a:b], a / SR


def use_english(cfg):
    """Default: English names are read with their Lao reading from `say:` (Joe prefers this).
    `english: native` lets a vox voice read Latin words as real English instead."""
    return str(cfg.get("voice", "")).startswith("vox") and str(cfg.get("english", "lao")) == "native"


# Lao is tonal: a style that is too extreme (whispering, shouting) bends the word tones and the accent
# stops sounding native, so the style prompts stay moderate and the contrast comes from the numbers below.
# How each emotion is PERFORMED. `style` steers the voice model (it changes pitch and energy but not
# reliably the pace), so pace, loudness, pitch offset and pauses are also enforced here.
#   speed  : speaking-rate factor          gain : dB relative to normal        pitch : semitones
#   pause  : seconds of silence for every "..." in the line        gap : silence after the line
EMO = {
    "hook":     dict(style="strong, firm, dramatic voice, punchy and confident, grabbing attention",
                     speed=1.00, gain=1.0, pitch=0.0, pause=0.40, gap=0.30),
    "story":    dict(style="lively, warm, conversational storyteller chatting with friends, expressive ups and downs",
                     speed=1.00, gain=0.0, pitch=0.0, pause=0.32, gap=0.24),
    "suspense": dict(style="lower, quieter and slower, tense and suspenseful, clearly spoken",
                     speed=0.90, gain=-4.0, pitch=-1.0, pause=0.65, gap=0.45),
    "climax":   dict(style="very excited and energetic, fast, thrilled, like a football fan telling the best moment, "
                           "clearly spoken", speed=1.06, gain=2.5, pitch=0.0, pause=0.22, gap=0.14),
    "calm":     dict(style="calm, slow, warm, thoughtful and meaningful", speed=0.92, gain=-1.5, pitch=-0.6,
                     pause=0.55, gap=0.40),
    "funny":    dict(style="playful, teasing, amused, cheeky, holding back a laugh", speed=1.03, gain=0.5, pitch=0.3,
                     pause=0.32, gap=0.22),
    "angry":    dict(style="angry, frustrated, sharp and forceful", speed=1.03, gain=1.5, pitch=0.0, pause=0.30,
                     gap=0.22),
    "sad":      dict(style="sad, disappointed, soft and slow, heavy-hearted", speed=0.90, gain=-3.0, pitch=-0.8,
                     pause=0.60, gap=0.42),
    "happy":    dict(style="happy, bright, cheerful, smiling", speed=1.03, gain=1.0, pitch=0.3, pause=0.28, gap=0.22),
    "question": dict(style="curious, intrigued, asking the audience a question, rising intonation", speed=0.98,
                     gain=0.0, pitch=0.2, pause=0.40, gap=0.34),
}
EMO_ALIASES = {"normal": "story", "tense": "suspense", "excited": "climax", "close": "calm", "joke": "funny"}


def emotion(name):
    name = EMO_ALIASES.get(str(name or "story").lower(), str(name or "story").lower())
    if name not in EMO:
        raise ValueError(f"emo ບໍ່ຮູ້ຈັກ: {name} (ມີ: {', '.join(EMO)})")
    return name, EMO[name]


def shape(y, speed=1.0, pitch_st=0.0):
    """Change pace and pitch without the chipmunk effect (rubberband, formants preserved)."""
    if abs(speed - 1.0) < 0.005 and abs(pitch_st) < 0.05:
        return y
    import tempfile
    a, b = tempfile.mktemp(suffix=".wav"), tempfile.mktemp(suffix=".wav")
    write_wav(a, y)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", a, "-af",
                    f"rubberband=tempo={speed:.3f}:pitch={2 ** (pitch_st / 12):.4f}:formant=preserved:pitchq=quality",
                    b], check=True)
    out = read_audio(b); os.remove(a); os.remove(b)
    return out


def level(y, gain_db=0.0, target_rms=0.10):
    """Same loudness for every take (RMS over the voiced part), then the emotion's gain on top."""
    loud = y[np.abs(y) > 0.02]
    rms = float(np.sqrt((loud ** 2).mean())) if len(loud) else 1.0
    y = y * (target_rms / (rms + 1e-9)) * 10 ** (gain_db / 20)
    pk = float(np.abs(y).max())
    return (y * (0.97 / pk) if pk > 0.97 else y).astype(np.float32)


def median_f0(y, sr=None):
    """Median pitch (Hz) of the voiced part; 0 when nothing voiced was found."""
    x = resample(y, sr or SR, 16000)
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
    return float(np.median(f)) if f else 0.0


# Tone lock (cards with "lock_tone": true): every line must stay near the card's own pitch (f0_hz), so the
# voice keeps the same weight from the first line to the last. Allowed drift in semitones per emotion;
# a climax may rise a little. Outside the window: re-generate, then pull the best take back to the edge.
TONE_ROOM = {"climax": (-1.0, 2.5), "happy": (-1.5, 2.0)}
TONE_DEFAULT = (-1.5, 1.5)


def _vox_take(model, text, card, style, desc, expect, emo="story"):
    """One take with sanity checks: the model sometimes skips or repeats words (length vs the MMS duration
    model), and - for tone-locked cards - drifts away from the card's pitch. Re-generate when either is off."""
    target = float(card.get("f0_hz") or 0) if card and card.get("lock_tone") else 0.0
    lo, hi = TONE_ROOM.get(emo, TONE_DEFAULT)
    best = None
    for attempt in range(5 if target else 3):
        y = trim_silence(model.say(text, card=card, desc=desc, style=style))[0]
        ratio = len(y) / SR / expect
        f = median_f0(y) if target else 0.0
        st = 12 * np.log2(f / target) if (target and f) else 0.0
        outside = max(lo - st, st - hi, 0.0)
        score = abs(ratio - 0.78) * 4 + outside
        if best is None or score < best[0]:
            best = (score, y, st)
        len_ok = 0.45 <= ratio <= 1.35
        if len_ok and outside == 0:
            break
        why = f"ຄວາມຍາວ x{ratio:.2f}" if not len_ok else f"ໂທນເພ້ຍ {st:+.1f} st"
        print(f"    … {why} ສັງເຄາະໃໝ່", flush=True)
    _, y, st = best
    if target and not (lo <= st <= hi):                    # still off: pull it back to the window edge
        y = shape(y, 1.0, max(-4.0, min(4.0, (lo if st < lo else hi) - st)))
    return y


def _ltas(x, n=2048):
    """Long-term average spectrum (power per FFT bin) over the voiced frames."""
    from scipy.signal import stft
    _, _, Z = stft(x, nperseg=n, noverlap=n * 3 // 4)
    P = np.abs(Z) ** 2
    e = P.sum(0)
    keep = e > np.percentile(e, 40)
    return P[:, keep].mean(1) if keep.any() else P.mean(1)


def match_tone(y, ref, max_db=6.0, n=2048):
    """Give `y` the tonal balance (weight, warmth, brightness) of `ref` with a smooth static EQ
    (1/3-octave smoothing, at most +-max_db). Level is handled separately."""
    from scipy.signal import istft, stft
    if len(y) < n * 2 or len(ref) < n * 2:
        return y
    f = np.fft.rfftfreq(n, 1 / SR)
    g = 10 * np.log10((_ltas(ref, n) + 1e-12) / (_ltas(y, n) + 1e-12))
    sm = np.empty_like(g)
    for i, fc in enumerate(f):                               # 1/3-octave smoothing
        lo, hi = max(1.0, fc) / 2 ** (1 / 6), max(1.0, fc) * 2 ** (1 / 6)
        sel = (f >= lo) & (f <= hi)
        sm[i] = g[sel].mean() if sel.any() else g[i]
    band = (f > 90) & (f < 9000)
    sm -= np.average(sm[band], weights=1 / np.maximum(f[band], 90))   # keep overall level roughly unchanged
    sm[f < 70] = min(0.0, sm[(f >= 70)][0])                  # never boost rumble
    gain = 10 ** (np.clip(sm, -max_db, max_db) / 20)
    _, _, Z = stft(y, nperseg=n, noverlap=n * 3 // 4)
    _, out = istft(Z * gain[:, None], nperseg=n, noverlap=n * 3 // 4)
    return out[:len(y)].astype(np.float32)


def phrases(y, sr=None, min_gap=0.12, min_len=0.25):
    """(start, end) sample ranges of the spoken phrases, split at silences of at least `min_gap` s."""
    sr = sr or SR
    hop = int(0.01 * sr)
    n = len(y) // hop
    if n == 0:
        return []
    e = np.sqrt((y[:n * hop].reshape(n, hop) ** 2).mean(1))
    on = e > 0.02 * (e.max() + 1e-9)
    out, st, quiet = [], None, 0
    for i, v in enumerate(on):
        if v:
            st = i if st is None else st
            quiet = 0
        elif st is not None:
            quiet += 1
            if quiet >= int(min_gap * 100):
                out.append((st, i - quiet + 1)); st, quiet = None, 0
    if st is not None:
        out.append((st, n))
    return [(a * hop, b * hop) for a, b in out if (b - a) * 0.01 >= min_len]


def tone_profile(ref):
    """Pitch register of the approved reference: overall median and the range its phrases move in."""
    f0 = median_f0(ref)
    sts = [12 * np.log2(f / f0) for f in (median_f0(ref[a:b]) for a, b in phrases(ref)) if f]
    return {"f0": f0, "lo": min(sts + [-1.5]) - 0.3, "hi": max(sts + [1.5]) + 0.3}


def _shift_exact(y, st):
    """Pitch-shift by `st` semitones, keeping the exact length (timings stay valid)."""
    if abs(st) < 0.1 or len(y) < int(0.05 * SR):
        return y
    z = shape(y, 1.0, st)
    return np.pad(z, (0, max(0, len(y) - len(z))))[:len(y)].astype(np.float32)


def lock_pitch(y, prof, center_tol=0.4):
    """Keep a line in the reference's register: move the whole line so its median sits on the reference
    median (when off by more than center_tol), then pull any phrase that leaves the reference's own phrase
    range back to its edge. Cuts only happen in silences, so no seams inside words."""
    f = median_f0(y)
    if not f:
        return y
    m = 12 * np.log2(f / prof["f0"])
    if abs(m) > center_tol:
        y = _shift_exact(y, max(-4.0, min(4.0, -m)))
    y = y.copy()
    for a, b in phrases(y):
        fp = median_f0(y[a:b])
        if not fp:
            continue
        st = 12 * np.log2(fp / prof["f0"])
        if st > prof["hi"] or st < prof["lo"]:
            y[a:b] = _shift_exact(y[a:b], (prof["hi"] if st > prof["hi"] else prof["lo"]) - st)
    return y


def _raw_segment(engine, seg, emo, E, card, cfg, cache_dir, model_box, speed):
    """Synthesise one segment (no pause inside) and cache the RAW take, so level / tone / pace can be
    re-tuned later without re-synthesising. Returns (audio, char_times)."""
    is_vox = engine.startswith("vox")
    style = E["style"] if (is_vox and card and card.get("perform", True)) else None
    key = hashlib.sha1(json.dumps(["raw2", engine, seg, SR, style, emo if is_vox else None,
                                   None if is_vox else speed], ensure_ascii=False).encode()).hexdigest()[:18]
    fa, fj = os.path.join(cache_dir, key + ".npy"), os.path.join(cache_dir, key + ".json")
    if os.path.exists(fa) and os.path.exists(fj):
        return np.load(fa), [tuple(x) for x in json.load(open(fj))], False
    if is_vox:
        model_box[0] = model_box[0] or get_vox()
        y = _vox_take(model_box[0], seg, card, E["style"], cfg.get("voice_desc"), sum(_char_weights(seg)) or 1.0, emo)
        tt = _scaled_times(seg, len(y) / SR)
    elif engine == "mms":
        model_box[0] = model_box[0] or MMS()
        y, tt = model_box[0].say(seg, speed)
        y, o = trim_silence(y)
        tt = [(max(0.0, a - o), max(0.0, b - o)) for a, b in tt]
    elif engine.startswith("edge"):
        v = engine.split(":", 1)[1] if ":" in engine else "female"
        y, tt = edge_say(seg, EDGE_VOICES.get(v, v), speed)
        y, o = trim_silence(y)
        tt = [(max(0.0, a - o), max(0.0, b - o)) for a, b in tt]
    else:
        raise ValueError("voice engine ບໍ່ຮູ້ຈັກ: " + engine)
    np.save(fa, y.astype(np.float32)); json.dump(tt, open(fj, "w"))
    return y, tt, True


def synth_sentences(lines, cfg, cache_dir, project=None, emos=None):
    """lines: display texts; emos: one emotion name per line (None = story).
    Returns list of dicts {audio, dur, gap, emo, tokens:[{t,a,b}], spoken, missing}.

    Tone-locked cards ("lock_tone": true - the voice Joe approved): every line keeps the weight of the
    approved reference take - same loudness and pace as the opening (hook) line, the reference's tonal
    balance (match_tone) and its pitch (checked in _vox_take). Emotion then lives in the words and pauses."""
    engine = cfg.get("voice", "mms")
    base_speed = float(cfg.get("speed", 1.0))
    say = cfg.get("say", {})
    os.makedirs(cache_dir, exist_ok=True)
    model_box, out = [None], []
    english, is_vox = use_english(cfg), engine.startswith("vox")
    card = load_card(engine.split(":", 1)[1], project) if (is_vox and ":" in engine) else None
    locked = bool(card and card.get("lock_tone"))
    ref = read_audio(card["wav"]) if locked else None
    prof = tone_profile(ref) if locked else None
    for li, text in enumerate(lines):
        emo, E = emotion(emos[li] if emos else None)
        H = EMO["hook"]
        speed = base_speed * (H["speed"] if locked else E["speed"])
        gain = H["gain"] if locked else E["gain"]
        pitch = 0.0 if (locked or is_vox and card and card.get("lock_tone")) else E["pitch"]
        toks, spoken, spans, missing = laotext.speech_plan(text, say, english, punct=is_vox)
        parts, pos = [], 0                                   # split at every "..." -> real pauses
        for seg in spoken.split(laotext.PAUSE):
            parts.append((pos, seg)); pos += len(seg) + 1
        pieces, times, t = [], [(0.0, 0.0)] * len(spoken), 0.0
        fresh = False
        for off, seg in parts:
            if not seg.strip():
                continue
            y, tt, new = _raw_segment(engine, seg, emo, E, card, cfg, cache_dir, model_box, speed)
            fresh = fresh or new
            if is_vox:
                k0 = len(y)
                y = shape(y, speed, pitch)
                tt = [(a * len(y) / k0, b * len(y) / k0) for a, b in tt]
            elif abs(pitch) > 0.05:
                y = shape(y, 1.0, pitch)
            if locked:
                y = match_tone(y, ref)
            if pieces:
                n = int(E["pause"] * SR)
                pieces.append(np.zeros(n, np.float32)); t += n / SR
                if off - 1 < len(times):
                    times[off - 1] = (t - n / SR, t)
            for i, (a, b) in enumerate(tt):
                if off + i < len(times):
                    times[off + i] = (t + a, t + b)
            pieces.append(y); t += len(y) / SR
        y = np.concatenate(pieces) if pieces else np.zeros(int(0.2 * SR), np.float32)
        if locked:
            y = lock_pitch(y, prof)
        y = level(y, gain)
        last = 0.0
        for i in range(len(times)):                          # characters with no sound keep the running time
            if times[i] == (0.0, 0.0) and i > 0:
                times[i] = (last, last)
            last = times[i][1]
        if is_vox and fresh:
            print(f"    ✓ {len(y) / SR:4.1f} ວິ  [{emo}] {text[:44]}", flush=True)
        dur = len(y) / SR
        tk = []
        for t_, (a, b) in zip(toks, spans):
            if a >= b or not any(c.isalnum() or laotext.is_lao(c) for c in t_):
                continue
            ta, tb = float(times[a][0]), float(times[b - 1][1])
            tk.append({"t": t_, "a": round(min(ta, dur), 3), "b": round(min(max(tb, ta + 0.04), dur), 3)})
        out.append({"audio": y, "dur": dur, "gap": E["gap"], "emo": emo, "tokens": tk, "tokens_all": toks,
                    "spoken": spoken, "missing": missing})
    return out


# ------------------------------------------------------------------ recorded narrator
def speech_spans(y, min_sil=0.22, thr_db=-38):
    """Energy based speech spans (seconds) for a narrator recording."""
    hop = int(0.01 * SR)
    n = len(y) // hop
    rms = np.sqrt((y[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)
    db = 20 * np.log10(rms / (rms.max() + 1e-9) + 1e-9)
    on = db > thr_db
    spans, st = [], None
    for i, v in enumerate(on):
        if v and st is None:
            st = i
        elif not v and st is not None:
            spans.append([st * 0.01, i * 0.01]); st = None
    if st is not None:
        spans.append([st * 0.01, n * 0.01])
    merged = []
    for a, b in spans:
        if merged and a - merged[-1][1] < min_sil:
            merged[-1][1] = b
        elif b - a > 0.08:
            merged.append([a, b])
    return merged


def tighten(y, spans, max_gap=0.35, pad=0.1):
    """Cut pauses longer than max_gap (keeps `pad` around speech). -> (new_audio, removed_seconds)."""
    keep, total = [], len(y) / SR
    for a, b in spans:
        a, b = max(0, a - pad), min(total, b + pad)
        if keep and a - keep[-1][1] <= max_gap - 2 * pad:
            keep[-1][1] = b
        else:
            keep.append([a, b])
    fade = int(0.01 * SR); ramp = np.linspace(0, 1, fade, dtype=np.float32)
    parts = []
    for i, (a, b) in enumerate(keep):
        seg = y[int(a * SR):int(b * SR)].copy()
        if len(seg) > 2 * fade:
            seg[:fade] *= ramp; seg[-fade:] *= ramp[::-1]
        parts.append(seg)
        if i < len(keep) - 1:
            parts.append(np.zeros(int((max_gap - 2 * pad) * SR), np.float32))
    out = np.concatenate(parts) if parts else y
    return out, total - len(out) / SR


def _ctc_lines(y, plans, cache, log=print):
    """Forced alignment (ctcalign) -> per line (start, end, {char index: (a, b)}) or None if unavailable."""
    from . import ctcalign
    mode = "ctc"
    if not ctcalign.available():
        return None
    key = hashlib.sha1(y[::7].tobytes() + "\n".join(p[1] for p in plans).encode()).hexdigest()[:16]
    f = os.path.join(cache, f"align_{key}.json") if cache else None
    if f and os.path.exists(f):
        raw = json.load(open(f))
        return [{int(k): tuple(v) for k, v in d.items()} for d in raw]
    log(f"      ຈັບເວລາຄຳຕໍ່ຄຳ ({mode}, ~2–3 ນາທີ)")
    try:
        res = ctcalign.align(y, SR, [p[1] for p in plans])
    except Exception as e:                                   # model missing / offline -> pause-based fallback
        log(f"      ຈັບເວລາຄຳຕໍ່ຄຳບໍ່ໄດ້ ({e}); ໃຊ້ຊ່ວງງຽບແທນ")
        return None
    if f:
        os.makedirs(cache, exist_ok=True)
        json.dump([{str(k): v for k, v in d.items()} for d in res], open(f, "w"))
    return res


def align_recording(path, lines, cfg, cache=None, log=print):
    """Narrator recording -> same structure as synth_sentences, plus absolute 'start' per sentence.

    Line and word times come from forced alignment of the script to the recording (`align: ctc`, default
    when torch/transformers are installed); `align: pauses` (or no model) guesses breaks from pauses."""
    say = cfg.get("say", {})
    y = read_audio(path)
    y = y / (np.abs(y).max() + 1e-9) * 0.89
    removed = 0.0
    if cfg.get("tighten", True):
        y, removed = tighten(y, speech_spans(y))
    spans = speech_spans(y, min_sil=0.15)
    total = len(y) / SR
    plans = [laotext.speech_plan(t, say) for t in lines]
    ct = _ctc_lines(y, plans, cache, log) if str(cfg.get("align", "ctc")) == "ctc" else None
    if ct and all(ct):
        first = [min(a for a, b in d.values()) for d in ct]
        last = [max(b for a, b in d.values()) for d in ct]
        starts = [max(0.0, first[0] - 0.12)]
        for i in range(1, len(lines)):                      # cut just before the first sound of the line
            starts.append(max(last[i - 1], first[i] - 0.12, starts[-1] + 0.3))
        ends = starts[1:] + [min(total, last[-1] + 0.25)]
        out = []
        for i, (toks, spoken, sp, missing) in enumerate(plans):
            a, d = starts[i], ct[i]
            tk = []
            for t, (x, z) in zip(toks, sp):
                ts = [d[c] for c in range(x, z) if c in d]
                if z > x and ts and any(ch.isalnum() or laotext.is_lao(ch) for ch in t):
                    tk.append({"t": t, "a": round(max(0.0, ts[0][0] - a), 3), "b": round(max(0.0, ts[-1][1] - a), 3)})
            out.append({"audio": None, "dur": ends[i] - a, "start": a, "tokens": tk, "tokens_all": toks,
                        "spoken": spoken, "missing": []})
        return out, y, removed
    weights = [max(1, sum(1 for c in p[1] if not c.isspace())) for p in plans]
    if not spans:
        spans = [[0.0, total]]
    # pauses between speech spans: (time, speech seconds before it, pause length)
    pauses, acc = [], 0.0
    for i in range(len(spans) - 1):
        acc += spans[i][1] - spans[i][0]
        pauses.append(((spans[i][1] + spans[i + 1][0]) / 2, acc, spans[i + 1][0] - spans[i][1]))
    speech_total = acc + spans[-1][1] - spans[-1][0]
    expect = [w / sum(weights) * speech_total for w in weights]
    n, P = len(lines), len(pauses)
    bounds = None
    if P >= n - 1 and n > 1:
        # dynamic programming: put the n-1 sentence breaks on pauses so every sentence gets about its
        # share of speech time; longer pauses are preferred (people pause longer between sentences)
        INF = float("inf")
        cost = [[INF] * P for _ in range(n - 1)]
        back = [[-1] * P for _ in range(n - 1)]
        def seg(d, e, gap):
            return ((d - e) / e) ** 2 - 0.25 * min(gap, 0.6)
        for j in range(P):
            cost[0][j] = seg(pauses[j][1], expect[0], pauses[j][2])
        for i in range(1, n - 1):
            for j in range(i, P):
                best, arg = INF, -1
                for k in range(i - 1, j):
                    if cost[i - 1][k] < INF:
                        c = cost[i - 1][k] + seg(pauses[j][1] - pauses[k][1], expect[i], pauses[j][2])
                        if c < best:
                            best, arg = c, k
                cost[i][j], back[i][j] = best, arg
        j = min(range(P), key=lambda j: cost[n - 2][j] + ((speech_total - pauses[j][1] - expect[-1]) / expect[-1]) ** 2)
        idx = [j]
        for i in range(n - 2, 0, -1):
            j = back[i][j]; idx.append(j)
        bounds = [spans[0][0]] + [pauses[j][0] for j in reversed(idx)] + [spans[-1][1]]
    if bounds is None:                                      # too few pauses: split by share of speech time
        def speech_to_abs(sv):
            for a, b in spans:
                if sv <= b - a:
                    return a + sv
                sv -= b - a
            return total
        bounds, acc = [spans[0][0]], 0.0
        for e in expect[:-1]:
            acc += e
            bounds.append(max(bounds[-1] + 0.3, speech_to_abs(acc)))
        bounds.append(spans[-1][1])
    out = []
    for i, (toks, spoken, sp, missing) in enumerate(plans):
        a, b = bounds[i], bounds[i + 1]
        times = _proportional(spoken, b - a, lead=0.03)
        tk = [{"t": t, "a": round(times[x][0], 3), "b": round(times[z - 1][1], 3)}
              for t, (x, z) in zip(toks, sp) if z > x and any(c.isalnum() or laotext.is_lao(c) for c in t)]
        out.append({"audio": None, "dur": b - a, "start": a, "tokens": tk, "tokens_all": toks,
                    "spoken": spoken, "missing": []})
    return out, y, removed
