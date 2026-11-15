#!/usr/bin/env bash
# ຕິດຕັ້ງເຄື່ອງມືຂອງ Lao Video Studio (ເອີ້ນຊ້ຳໄດ້). Installs Python deps + the offline Lao voice model.
set -e
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v ffmpeg >/dev/null || { echo "ຕ້ອງມີ ffmpeg (apt-get install -y ffmpeg)"; exit 1; }
python3 -m pip install -q --disable-pip-version-check --root-user-action=ignore -r "$here/requirements.txt"
python3 - <<'PY'
from PIL import features
print("raqm (Lao shaping):", "ok" if features.check("raqm") else "MISSING - install libraqm, Lao marks will misplace")
PY
dir="${LAOSTUDIO_CACHE:-$HOME/.cache/laostudio}/mms-lao"
mkdir -p "$dir"
for f in model.onnx tokens.txt; do
  if [ ! -s "$dir/$f" ]; then
    curl -sSL --fail --retry 3 -o "$dir/$f.part" \
      "https://huggingface.co/willwade/mms-tts-multilingual-models-onnx/resolve/main/lao/$f" \
      && mv "$dir/$f.part" "$dir/$f" || echo "ໂຫຼດໂມເດລສຽງບໍ່ໄດ້ ($f) — ຈະລອງໃໝ່ຕອນ render"
  fi
done
echo "Lao Video Studio ພ້ອມໃຊ້"
