"""ສຽງພາກລາວອັດຕະໂນມັດ (Lao voice-over).

Engines
  mms   - offline neural Lao voice (Meta MMS-TTS, ONNX, CPU). Gives exact per-word timing.
          Licence CC-BY-NC 4.0 -> good for drafts / non-commercial; use `edge` or a recording for ads.
  edge  - Microsoft neural voices lo-LA-KeomanyNeural (ຍິງ) / lo-LA-ChanthavongNeural (ຊາຍ) via `edge-tts`
          (needs open internet + websockets; not available inside the locked cloud sandbox).
  file  - the narrator's own recording (best quality). Sentences are aligned to the pauses in the recording.
"""
import hashlib, json, os, subprocess, sys, urllib.request, wave

import numpy as np

from . import laotext

SR = 16000
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


def read_audio(path, sr=SR):
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
        y, dur = y[0, 0].astype(np.float32), dur[0, 0]
        cum = np.concatenate([[0], np.cumsum(dur)]) * 256.0 / SR
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


def synth_sentences(lines, cfg, cache_dir):
    """lines: list of display texts. Returns list of dicts {audio, dur, tokens:[{t,a,b}], spoken, missing}."""
    engine = cfg.get("voice", "mms")
    speed = float(cfg.get("speed", 1.0))
    say = cfg.get("say", {})
    os.makedirs(cache_dir, exist_ok=True)
    model, out = None, []
    for text in lines:
        toks, spoken, spans, missing = laotext.speech_plan(text, say)
        key = hashlib.sha1(json.dumps([engine, speed, spoken], ensure_ascii=False).encode()).hexdigest()[:16]
        fa, fj = os.path.join(cache_dir, key + ".npy"), os.path.join(cache_dir, key + ".json")
        if os.path.exists(fa) and os.path.exists(fj):
            y, times = np.load(fa), json.load(open(fj))
        else:
            if engine == "mms":
                model = model or MMS()
                y, times = model.say(spoken, speed)
            elif engine.startswith("edge"):
                v = engine.split(":", 1)[1] if ":" in engine else "female"
                y, times = edge_say(spoken, EDGE_VOICES.get(v, v), speed)
            else:
                raise ValueError("voice engine ບໍ່ຮູ້ຈັກ: " + engine)
            y, off = trim_silence(y)
            times = [(max(0.0, a - off), max(0.0, b - off)) for a, b in times]
            pk = float(np.abs(y).max()) or 1.0
            y = (y / pk * 0.89).astype(np.float32)
            np.save(fa, y); json.dump(times, open(fj, "w"))
        dur = len(y) / SR
        tk = []
        for t, (a, b) in zip(toks, spans):
            if a >= b or not any(c.isalnum() or laotext.is_lao(c) for c in t):
                continue
            ta, tb = float(times[a][0]), float(times[b - 1][1])
            tk.append({"t": t, "a": round(min(ta, dur), 3), "b": round(min(max(tb, ta + 0.04), dur), 3)})
        out.append({"audio": y, "dur": dur, "tokens": tk, "tokens_all": toks, "spoken": spoken, "missing": missing})
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


def align_recording(path, lines, cfg):
    """Narrator recording -> same structure as synth_sentences, plus absolute 'start' per sentence."""
    say = cfg.get("say", {})
    y = read_audio(path)
    y = y / (np.abs(y).max() + 1e-9) * 0.89
    removed = 0.0
    if cfg.get("tighten", True):
        y, removed = tighten(y, speech_spans(y))
    spans = speech_spans(y, min_sil=0.15)
    total = len(y) / SR
    plans = [laotext.speech_plan(t, say) for t in lines]
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
