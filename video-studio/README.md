# Lao Video Studio — ໂຮງງານວີດີໂອເຕະບານພາສາລາວ

ຈາກ "ຫົວຂໍ້" ເຖິງ MP4 ພ້ອມໂພສ ແບບອັດຕະໂນມັດ: ຂຽນບົດ → ຫາ footage → ສຽງພາກລາວ → ຕັດຕໍ່ → ຄຳບັນຍາຍ → ເພງ/ເອັບເຟັກ → ໜ້າປົກ + caption.

- Skill ແລະ ໂຄດ: [`.claude/skills/lao-football-video/`](../.claude/skills/lao-football-video/SKILL.md)
- ໂປຣເຈັກວີດີໂອ: `video-studio/projects/<NNN_ຊື່>/script.md` (+ `assets/` ສຳລັບຮູບ/ຄລິບ/ສຽງຂອງເຈົ້າເອງ)
- ຜົນ: `video-studio/projects/<NNN_ຊື່>/out/` (ບໍ່ຖືກ commit)

## ວິທີໃຊ້ທີ່ງ່າຍສຸດ
ເປີດ Claude Code ໃນ repo ນີ້ ແລ້ວພິມ: **`/lao-football-video ເຮັດວີດີໂອເລື່ອງ …`** — Claude ຈະຄົ້ນຂໍ້ມູນ, ຂຽນບົດ, ແລະ ແລ່ນທຸກຂັ້ນຕອນ.

## ໃຊ້ດ້ວຍມື
```bash
bash .claude/skills/lao-football-video/scripts/setup.sh      # ເທື່ອທຳອິດ
./video-studio/studio new   video-studio/projects/002_ຊື່ --title "ຫົວຂໍ້ *ເນັ້ນ*"
./video-studio/studio check video-studio/projects/002_ຊື່
./video-studio/studio plan  video-studio/projects/002_ຊື່     # ເບິ່ງ out/*_footage.jpg
./video-studio/studio run   video-studio/projects/002_ຊື່ --both
```
ຕົວຢ່າງສຳເລັດຮູບ: `projects/001_goalkeeper_feet` (17 ປະໂຫຍກ → 148 ວິ, render ~2 ນາທີ ເທິງ 4 CPU).

## ຕ້ອງມີ
Python 3.10+, ffmpeg, Pillow ທີ່ມີ raqm (ສຳລັບສະຫຼະລາວ), ແລະ ແພັກເກັດໃນ `scripts/requirements.txt`.
