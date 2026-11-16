"""Forced alignment of a Lao narration recording to its script (CTC, MMS Lao model).

Gives every spoken character a time, so each line (shot change) and each word (key captions) starts
exactly when the narrator says it — instead of guessing sentence breaks from pauses, which fails for
fast TTS narrators (Gemini) that pause inside sentences more than between them.

Needs torch + transformers and the facebook/mms-1b-all model (~4 GB, cached by setup.sh / first use).
"""
import os, re, subprocess
import numpy as np

FR = 0.02                    # seconds per CTC frame (wav2vec2: 320 samples at 16 kHz)
_M = None
_NORM = {"ຳ": "ໍາ", "ໜ": "ຫນ", "ໝ": "ຫມ", "ໆ": ""}


def _model():
    global _M
    if _M is None:
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1"); os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
        import torch
        from transformers import AutoProcessor, Wav2Vec2ForCTC
        torch.set_num_threads(max(1, os.cpu_count() or 1))
        p = AutoProcessor.from_pretrained("facebook/mms-1b-all", target_lang="lao")
        m = Wav2Vec2ForCTC.from_pretrained("facebook/mms-1b-all", target_lang="lao", ignore_mismatched_sizes=True)
        m.eval()
        _M = (p, m)
    return _M


def available():
    try:
        import torch, transformers  # noqa: F401
        return True
    except ImportError:
        return False


def log_probs(y, sr):
    """Audio (float mono, any rate) -> (T, V) CTC log-probabilities, computed in 20 s chunks."""
    import torch
    p, m = _model()
    if sr != 16000:
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-",
                            "-ar", "16000", "-f", "f32le", "-"], input=y.astype("<f4").tobytes(), capture_output=True)
        y = np.frombuffer(r.stdout, "<f4")
    hop, ctx = 320 * 1000, 320 * 50                    # 20 s chunks + 1 s context each side
    out = []
    for a in range(0, len(y), hop):
        lo, hi = max(0, a - ctx), min(len(y), a + hop + ctx)
        x = y[lo:hi]
        x = (x - x.mean()) / (x.std() + 1e-7)
        with torch.no_grad():
            lg = m(torch.from_numpy(np.ascontiguousarray(x))[None]).logits[0]
        lp = torch.log_softmax(lg, -1).numpy()
        s = (a - lo) // 320
        n = (min(a + hop, len(y)) - a + 319) // 320
        out.append(lp[s:s + n])
    return np.concatenate(out)


def _targets(spokens, vocab):
    """-> (label ids, owner (line, char index in that line's spoken string) for each label)."""
    ids, own = [], []
    for li, s in enumerate(spokens):
        for ci, ch in enumerate(s):
            for c in _NORM.get(ch, ch):
                if c in vocab:
                    ids.append(vocab[c]); own.append((li, ci))
    return np.array(ids, int), own


def viterbi(lp, labels, blank):
    """Best CTC path. -> frame index where each label is first emitted, and its last frame."""
    T, L = len(lp), len(labels)
    S = 2 * L + 1
    lab = np.full(S, blank); lab[1::2] = labels
    skip = np.zeros(S, bool)
    skip[3::2] = labels[1:] != labels[:-1]               # may jump over the blank between different labels
    NEG = -1e30
    a = np.full(S, NEG); a[0] = lp[0, blank]; a[1] = lp[0, lab[1]]
    back = np.zeros((T, S), np.int8)
    for t in range(1, T):
        s1 = np.concatenate(([NEG], a[:-1]))
        s2 = np.where(skip, np.concatenate(([NEG, NEG], a[:-2])), NEG)
        stack = np.stack([a, s1, s2])
        k = stack.argmax(0)
        back[t] = k
        a = stack[k, np.arange(S)] + lp[t, lab]
    s = S - 1 if a[S - 1] >= a[S - 2] else S - 2
    first, last = np.full(L, -1), np.full(L, -1)
    for t in range(T - 1, -1, -1):
        if s % 2 == 1:
            i = s // 2
            first[i] = t
            if last[i] < 0:
                last[i] = t
        s -= int(back[t, s])
    return first, last


def align(y, sr, spokens):
    """Times of every line's characters. -> list (per line) of dict char_index -> (start, end) seconds."""
    p, _ = _model()
    vocab = p.tokenizer.get_vocab()
    blank = vocab.get("<pad>", p.tokenizer.pad_token_id)
    labels, own = _targets(spokens, vocab)
    lp = log_probs(y, sr)
    if len(labels) == 0 or len(lp) < len(labels):
        raise ValueError("recording too short for the script")
    first, last = viterbi(lp, labels, blank)
    out = [dict() for _ in spokens]
    for (li, ci), f, l in zip(own, first, last):
        a, b = f * FR, (l + 1) * FR
        if ci in out[li]:
            a = min(a, out[li][ci][0]); b = max(b, out[li][ci][1])
        out[li][ci] = (a, b)
    return out
