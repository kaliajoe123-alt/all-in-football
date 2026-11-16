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
if [ "$1" = "--vox" ]; then
  # ສຽງພາກຄຸນນະພາບສູງ VoxCPM2 (ໃຫຍ່: PyTorch + ໂມເດລ ~5 GB, ໃຊ້ເວລາ 5-10 ນາທີ)
  python3 -c "import voxcpm" 2>/dev/null || {
    python3 -m pip install -q --disable-pip-version-check --root-user-action=ignore -U setuptools || true
    python3 -m pip install -q --disable-pip-version-check --root-user-action=ignore --use-pep517 voxcpm soundfile scipy
  }
  HF_HUB_DISABLE_XET=1 python3 -c "from huggingface_hub import snapshot_download; snapshot_download('openbmb/VoxCPM2')" \
    >/dev/null 2>&1 || echo "ໂຫຼດ VoxCPM2 ບໍ່ໄດ້ — ຈະລອງໃໝ່ຕອນ render"
fi
echo "Lao Video Studio ພ້ອມໃຊ້"
