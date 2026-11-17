---
name: "aite-debate"
voice_id: "sp-aite-debate"
voice_label: "10. ອ້າຍເຕ້ — ໂຕ້ວາທີ GOAT & ຈັດທີມ 11 ຕົວຈິງຕະຫຼອດການ"
prebuilt_voice: "Fenrir"
model: "gemini-3.8-flash-lite-tts"
speaking_pace: "fast"
description: >
  ອ້າຍເຕ້ — ສຽງຊາຍ Fenrir ໂຕ້ວາທີ GOAT ແລະ ຈັດທີມ 11 ຕົວຈິງຕະຫຼອດການ: ຂຽນບົດ hot take ພາສາລາວ 15–25 ວິ, ສ້າງ MP3
  ດ້ວຍ Gemini TTS ແລ້ວສົ່ງໃຫ້ຟັງ. Use when Joe asks for ອ້າຍເຕ້, /aite-debate, ໂຕ້ວາທີ, GOAT, ໃຜເກັ່ງກວ່າ,
  ທີມ 11 ຕົວຈິງຕະຫຼອດການ, Dream XI, hot take, or a bold debate-style Lao football voice-over.
---

# Skill 10: ອ້າຍເຕ້ — ໂຕ້ວາທີ GOAT & ຈັດທີມ 11 ຕົວຈິງຕະຫຼອດການ

## 1. Voice Engine Configuration
- **Voice ID**: `sp-aite-debate`
- **Prebuilt Voice**: `Fenrir`
- **Speaking Pace**: `fast` (ໄວຄົມ · ຈັງຫວະທ້າທາຍຄອມເມັ້ນ)
- **TTS Style Metadata**:
  `Bold, charismatic, provocative Lao football podcast debater. Fast punchy delivery with confident quick breaths, stirring heated GOAT debates and dream-XI comparisons.`

## 2. 3-Second Debate Hook Formulas
1. `ຂໍຟັນທົງແບບບໍ່ເກງໃຈໃຜເລີຍ! ...` (Unapologetic hot take)
2. `ຖ້າຕ້ອງເລືອກພຽງຄົນດຽວລົງນັດຊິງ...` (High-stakes 1v1 dilemma)
3. `ນີ້ຄືສິບເອັດຕົວຈິງຕະຫຼອດການທີ່ບໍ່ມີໃຜເອົາຊະນະໄດ້! ...` (Dream XI challenge)

## 3. Breathing & Conviction Timing
- Land the bold stance before `!`, back it up in one fast clause, then pause at `—` before issuing the comment challenge.
- Speak numbers and formations in Lao words (`ທັອບສາມ`, `ສິບເອັດຕົວຈິງ`, `ສີ່ສາມສາມ`).

## 4. Script Structure (15–25s Hot Take)
1. **0–3s (Bold Claim)**: Pick one side decisively with zero hedging.
2. **3–16s (Proof Point)**: Give 1–2 undeniable football arguments (big-game goals, consistency, trophies).
3. **16–25s (Comment Dare)**: Pause at `—` and dare viewers to name a better alternative in the comments.

## 5. Do's & Don'ts
- **DO**: Take a clear, defensible stance that naturally splits fan opinions.
- **DON'T**: Never end weakly with "it depends on personal taste"—keep the debate spark alive.

## 6. ວິທີສ້າງສຽງ (ເພີ່ມໂດຍ Claude; Joe ຟັງແລ້ວ "ຜ່ານ" 17-11-2026)
```bash
python3 .claude/skills/aite-debate/scripts/tts.py ບົດ.txt ອອກ_Fenrir.mp3     # ສຽງ Fenrir + style ຂ້າງເທິງ, ໂມເດລສຳຮອງອັດຕະໂນມັດ
```
- ຕົວຢ່າງທີ່ຜ່ານ: `references/example-goat-messi.md` (22 ວິ, ~85 ຄຳ). Fenrir ≈ 3.8–4 ຄຳລາວ/ວິ → 20 ວິ ≈ 75–85 ຄຳ.
- **ຂັດເກົາບົດດ້ວຍ skill `natural-spoken-lao`** ກ່ອນສ້າງສຽງ. **ຂຽນເປັນໂຕລາວທັງໝົດ** (ຊື່: ເມັດຊີ, ໂຣນັລໂດ…), ຕົວເລກ/ແຜນເປັນຄຳ.
- **ເວລາແບບລາວ**: `ສິບເອັດໂມງເຄິ່ງ` — ຫ້າມ `ທຸ່ມ` / `ຕີ`.
- **ຂໍ້ເທັດຈິງ**: hot take ແຮງໄດ້ ແຕ່ຕົວເລກ/ແຊ້ມ/ສະຖິຕິ ຕ້ອງກວດຈາກແຫຼ່ງ; ບໍ່ແນ່ໃຈ = ເວົ້າແບບບໍ່ມີຕົວເລກ (ເຊັ່ນ "ບານທອງຫຼາຍກວ່າໃຜ").
- ກວດຄຳຫາຍ: ຖອດສຽງດ້ວຍ MMS (ເບິ່ງ `lao-football-video`); ຄຳທີ່ຫາຍ → ສ້າງໃໝ່ ຫຼື ແບ່ງປະໂຫຍກສັ້ນລົງ.
- ໂຄຕ້າຟຣີ ~10 ເທື່ອ/ມື້/ໂມເດລ; key ຢູ່ໃນ Network secret ຂອງ `generativelanguage.googleapis.com` — ຢ່າໃຫ້ວາງ key ໃນແຊັດ.
- ເອົາໄປໃສ່ວີດີໂອ: skill `lao-football-video` ກັບ `voice: file:<ໄຟລ໌>.mp3`.
- ເມື່ອ Joe ຂໍ "ຄລິບ" ຫຼື "ວີດີໂອ": **ຖາມທຸກຄັ້ງ ລາຍການໃດ** (5 ລາຍການ ALL IN) **ແລະ ໃຊ້ສຽງໃຜ** (pak-kuan / chanthy-fans / aite-debate / ສຽງອັດເອງ).
- **ຄລິບຍາວ (ຄລິບ 003 ໂປເຊັດຕີໂນ 8 ນາທີ):** ແບ່ງບົດເປັນທ່ອນ ≤ ~1,350 ຕົວອັກສອນ (Fenrir ≈ 11–12 ຕົວ/ວິ ໃນບົດຍາວ, ຊ້າກວ່າບົດສັ້ນ),
  ຕໍ່ກັນດ້ວຍຊ່ອງງຽບ 0.45 ວິ; ຖ້າຍາວເກີນເປົ້າ ໃຊ້ `atempo=1.08` ໄດ້ (ຟັງບໍ່ອອກ). ກວດທຸກທ່ອນດ້ວຍ MMS ແລ້ວຫາຊ່ວງທີ່ຫາຍ:
  ປະໂຫຍກທີ່ TTS ຂ້າມ → ຕັດອອກຈາກ `script.md` ໃຫ້ກົງກັບສຽງ (ງ່າຍກວ່າພາກໃໝ່).
- **ຢ່າພາກໃໝ່ທີລະປະໂຫຍກສັ້ນ ດ້ວຍ Fenrir**: ສອງເທື່ອໃນຄລິບ 003 ມັນອ່ານ style prompt ອອກມາເປັນພາສາອັງກິດ ຫຼື ແຕ່ງເນື້ອເພີ່ມ.
  ຕ້ອງແກ້ ໃຫ້ພາກທັງທ່ອນໃໝ່ ຫຼື ໃສ່ປະໂຫຍກກ່ອນ/ຫຼັງໄປນຳ ແລ້ວຕັດດ້ວຍການຈັບເວລາຄຳ; ກວດດ້ວຍ MMS ທຸກເທື່ອ.

