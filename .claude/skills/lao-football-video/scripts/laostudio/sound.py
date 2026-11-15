"""ສຽງ: ສຽງພາກ + ເພງພື້ນຫຼັງ + ສຽງເອັບເຟັກ, ຜະສົມ ແລະ ປັບລະດັບ -14 LUFS.

Sound design. Everything can be generated offline (numpy synth) so a video never ships silent,
but real files always win:
  music : project/music.*  ->  <library>/MUSIC/<mood>/*  ->  synthesized bed (soft, loopable)
  sfx   : <library>/SFX/{whoosh,pop,impact,tear,tick}*  ->  synthesized
Voice sits on top; music is side-chain ducked under it; the final mix is normalised to -14 LUFS
(TikTok / Facebook / YouTube level - the reference video is about -24 LUFS, i.e. too quiet).
"""
import glob, os, random, subprocess

import numpy as np

from .voice import read_audio, write_wav

SR = 48000
MOODS = {"epic": ("ເດືອດ", "epic"), "tension": ("ລຸ້ນ", "tension"), "sad": ("ເສົ້າ", "sad"), "fun": ("ມ່ວນ", "fun")}
AUDIO_EXT = (".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac")


def _env(n, a=0.01, r=0.2):
    e = np.ones(n, np.float32)
    na, nr = max(1, int(a * SR)), max(1, int(r * SR))
    e[:na] = np.linspace(0, 1, na); e[-nr:] *= np.linspace(1, 0, nr)
    return e


def _smooth(x, n):
    return np.convolve(x, np.ones(n, np.float32) / n, mode="same").astype(np.float32)


def sfx(name, rng):
    x = _sfx(name, rng)
    return (x / max(1.0, float(np.abs(x).max()) / 0.75)).astype(np.float32)


def _sfx(name, rng):
    if name == "whoosh":
        n = int(0.42 * SR); t = np.linspace(0, 1, n)
        x = _smooth(rng.normal(0, 1, n).astype(np.float32), 24) * np.sin(np.pi * t) ** 2 * 3.0
        return x * 0.5
    if name == "pop":
        n = int(0.14 * SR); t = np.arange(n) / SR
        f = 520 + 700 * np.exp(-t * 40)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 30)).astype(np.float32) * 0.6
    if name == "tick":
        n = int(0.06 * SR); t = np.arange(n) / SR
        return (np.sin(2 * np.pi * 1500 * t) * np.exp(-t * 90)).astype(np.float32) * 0.35
    if name == "impact":
        n = int(0.9 * SR); t = np.arange(n) / SR
        f = 48 + 90 * np.exp(-t * 18)
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 5)
        click = _smooth(rng.normal(0, 1, n).astype(np.float32), 6) * np.exp(-t * 35) * 0.7
        return (body + click).astype(np.float32) * 0.8
    if name == "tear":
        n = int(0.5 * SR); t = np.linspace(0, 1, n)
        noise = rng.normal(0, 1, n).astype(np.float32)
        crack = (rng.random(n) > 0.985).astype(np.float32) * rng.normal(0, 4, n).astype(np.float32)
        x = (noise - _smooth(noise, 12)) * 0.5 + _smooth(crack, 3)
        return (x * np.sin(np.pi * t) ** 1.5).astype(np.float32) * 0.45
    return np.zeros(1, np.float32)


def _library_file(dirs, sub, prefix):
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, sub, "*"))):
            if os.path.basename(f).lower().startswith(prefix) and f.lower().endswith(AUDIO_EXT):
                return f
    return None


def sfx_track(events, total, lib_dirs, vol=1.0, seed=11):
    rng = np.random.default_rng(seed)
    out = np.zeros(int((total + 1) * SR), np.float32)
    cache = {}
    for e in events:
        name = e["sfx"]
        if name not in cache:
            f = _library_file(lib_dirs, "SFX", name)
            cache[name] = read_audio(f, SR) * 0.8 if f else sfx(name, rng)
        x = cache[name]
        a = max(0, int(e["t"] * SR))
        b = min(len(out), a + len(x))
        if b > a:
            out[a:b] += x[:b - a] * vol
    return np.clip(out, -1, 1)


def synth_music(total, mood="tension", seed=5):
    """A soft loopable bed: pad chords + pulse bass + light hats. Meant as a placeholder under the voice."""
    rng = np.random.default_rng(seed)
    cfg = {"epic": (96, [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]], 1.0),
           "tension": (88, [[57, 60, 64], [57, 60, 65], [55, 58, 62], [52, 55, 59]], 0.7),
           "sad": (70, [[57, 60, 64], [53, 57, 60], [50, 53, 57], [52, 55, 59]], 0.3),
           "fun": (112, [[60, 64, 67], [57, 60, 64], [53, 57, 60], [55, 59, 62]], 1.0)}.get(mood) or \
          (88, [[57, 60, 64], [53, 57, 60]], 0.7)
    bpm, chords, drive = cfg
    beat = 60.0 / bpm
    bar = int(beat * 4 * SR)
    n = int((total + 2) * SR)
    out = np.zeros(n + bar, np.float32)
    hz = lambda m: 440.0 * 2 ** ((m - 69) / 12)
    t = np.arange(bar) / SR
    for b in range(0, n, bar):
        ch = chords[(b // bar) % len(chords)]
        pad = sum(np.sin(2 * np.pi * hz(m) * t + rng.random() * 6) + 0.4 * np.sin(2 * np.pi * hz(m) * 2.003 * t)
                  for m in ch) / len(ch)
        pad = pad * _env(bar, 0.4, 0.5) * 0.22
        bass = np.zeros(bar, np.float32)
        for k in range(8):
            a = int(k * beat / 2 * SR); ln = int(beat / 2 * SR * 0.9)
            tt = np.arange(ln) / SR
            bass[a:a + ln] += (np.sin(2 * np.pi * hz(ch[0] - 24) * tt) * np.exp(-tt * 7))[:max(0, bar - a)] * 0.3 * drive
        hat = np.zeros(bar, np.float32)
        for k in range(8):
            a = int(k * beat / 2 * SR); ln = int(0.04 * SR)
            if a + ln < bar:
                hat[a:a + ln] += rng.normal(0, 1, ln) * np.exp(-np.arange(ln) / SR * 120) * (0.05 if k % 2 else 0.03) * drive
        out[b:b + bar] += (pad + bass + hat).astype(np.float32)
    out = out[:n]
    out *= _env(n, 1.2, 2.0)
    return out / (np.abs(out).max() + 1e-6) * 0.6


def pick_music(project, mood, lib_dirs, total, seed=0):
    """-> (float32 mono track at 48k, description)"""
    if not mood or str(mood).lower() in ("none", "off", "false"):
        return None, "ບໍ່ມີເພງ"
    cands = [f for f in glob.glob(os.path.join(project, "music.*")) if f.lower().endswith(AUDIO_EXT)]
    for f in (str(mood), os.path.join(project, str(mood))):
        if os.path.isfile(f):
            cands = [f]
    if not cands:
        for d in lib_dirs:
            for folder in MOODS.get(str(mood), (str(mood),)):
                cands += [f for f in glob.glob(os.path.join(d, "MUSIC", folder, "*")) if f.lower().endswith(AUDIO_EXT)]
    if cands:
        f = random.Random(seed).choice(sorted(cands))
        x = read_audio(f, SR)
        if len(x) < SR:
            return synth_music(total, str(mood)), "ເພງສັງເຄາະ (ໄຟລ໌ເພງສັ້ນເກີນ)"
        reps = int(np.ceil((total + 2) * SR / len(x)))
        x = np.tile(x, reps)[:int((total + 2) * SR)]
        x *= _env(len(x), 1.0, 2.5)
        return x / (np.abs(x).max() + 1e-6) * 0.7, os.path.basename(f)
    return synth_music(total, str(mood)), f"ເພງສັງເຄາະ ({mood})"


def mix(voice_wav, music, sfx_arr, total, out_m4a, tmp_dir, music_vol=0.2, stems=True):
    """voice_wav: 16k mono narration placed on the timeline. Writes the final mix (+ stems)."""
    os.makedirs(tmp_dir, exist_ok=True)
    paths = {"voice": voice_wav}
    inputs, filt = ["-i", voice_wav], []
    filt.append("[0:a]aresample=48000,highpass=f=75,equalizer=f=3200:t=q:w=1.2:g=2.5,"
                "acompressor=threshold=-20dB:ratio=3:attack=8:release=160:makeup=3,"
                "loudnorm=I=-16:TP=-2:LRA=9,asplit=2[v][vsc]")
    last, k = "[v]", 1
    if music is not None:
        paths["music"] = os.path.join(tmp_dir, "music.wav"); write_wav(paths["music"], music, SR)
        inputs += ["-i", paths["music"]]
        filt.append(f"[{k}:a]volume={music_vol}[m0];[m0][vsc]sidechaincompress=threshold=0.03:ratio=8:attack=15:"
                    f"release=350[m]")
        k += 1
    else:
        filt.append("[vsc]anullsink")
    if sfx_arr is not None:
        paths["sfx"] = os.path.join(tmp_dir, "sfx.wav"); write_wav(paths["sfx"], sfx_arr, SR)
        inputs += ["-i", paths["sfx"]]
        filt.append(f"[{k}:a]volume=0.55[s]")
    ins = "[v]" + ("[m]" if music is not None else "") + ("[s]" if sfx_arr is not None else "")
    n = 1 + (music is not None) + (sfx_arr is not None)
    filt.append(f"{ins}amix=inputs={n}:normalize=0:duration=longest,loudnorm=I=-14:TP=-1.5:LRA=11,"
                f"atrim=0:{total:.3f},afade=t=out:st={max(0, total - 1.2):.3f}:d=1.2[out]")
    r = subprocess.run(["ffmpeg", "-y", "-v", "error"] + inputs + ["-filter_complex", ";".join(filt), "-map", "[out]",
                        "-ar", "48000", "-ac", "2", "-c:a", "aac", "-b:a", "192k", out_m4a],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("audio mix failed:\n" + r.stderr[-800:])
    return paths
