# ການຫາ footage ແລະ ລິຂະສິດ

## ລຳດັບການຫາ (ອັດຕະໂນມັດ)
1. `assets/` ຂອງໂປຣເຈັກ — ຊື່ໄຟລ໌ຕົງ ຫຼື ຄຳຄົ້ນຢູ່ໃນຊື່ໄຟລ໌ (ຕັ້ງຊື່ໄຟລ໌ຕາມສິ່ງທີ່ເຫັນ: `neuer_save.mp4`, `pep_touchline.jpg`).
2. ຄັງລວມ — `LAOSTUDIO_LIBRARY=dir1:dir2` ຫຼື `"library"` ໃນ brand json (ຮູບ/ຄລິບຂອງ Joe ທີ່ໃຊ້ຊ້ຳ).
3. **Wikimedia Commons** — ຮູບລິຂະສິດເສລີ (CC BY, CC BY-SA, CC0, Public domain). ຜູ້ຖ່າຍ + ລິຂະສິດ ຖືກບັນທຶກລົງ `_credits.txt` ແລະ ທ້າຍ `_caption.txt`.
4. **Pexels** (ຮູບ/ວີດີໂອສະຕັອກ: ສະໜາມ, ລູກບານ, ກອງເຊຍ) — ເມື່ອມີ `PEXELS_API_KEY`.
5. ບໍ່ພົບ → ກາດສີເຂັ້ມມີຊື່ (placeholder) ແລະ ຖືກລາຍງານໃນ `missing_footage` — **ຫ້າມສົ່ງວີດີໂອທີ່ຍັງມີ placeholder**.

## ກວດກ່ອນ render
`plan` ສ້າງ `out/<ຊື່>_footage.jpg`: ຮູບຂອງທຸກຊັອດ + ເລກຊັອດ + ຄຳຄົ້ນ; ສີແດງ = ຫາບໍ່ພົບ. `_plan.json` ບອກຊື່ໄຟລ໌ຕົ້ນທາງ.
- ຊື່ໄຟລ໌ຕ້ອງຢືນຢັນວ່າແມ່ນຄົນ/ສະຖານທີ່ນັ້ນ (ເຊັ່ນ "Ederson Moraes (36243872090).jpg"). ບໍ່ແນ່ໃຈ → ຢ່າໃສ່ `label:`.
- ຮູບຜິດກິລາ/ຜິດຄົນ → ປ່ຽນຄຳຄົ້ນໃຫ້ສະເພາະຂຶ້ນ ຫຼື `#2`, `#3`.
- ຮູບແນວຕັ້ງຈະຖືກວາງເຕັມຄວາມສູງ ເທິງພື້ນມົວຂອງຕົວມັນເອງ (ບໍ່ຖືກຕັດຫົວ).

## ກົດລິຂະສິດ
- ພາບຖ່າຍທອດສົດ, ໄຮໄລ້ແມັດ, ຮູບສຳນັກຂ່າວ (Getty, AFP…), ກາຕູນ/ໜັງ: **ລະບົບບໍ່ດຶງມາເອງ**. ຖ້າ Joe ວາງໄຟລ໌ແບບນັ້ນໃນ `assets/` ໃຫ້ເຕືອນເທື່ອດຽວວ່າ TikTok/Facebook ອາດປິດສຽງ ຫຼື ລຶບ.
- CC BY / CC BY-SA ຕ້ອງໃຫ້ເຄຣດິດ: ໂພສຕ້ອງມີແຖວ 📷 ຈາກ `_caption.txt` (ຫຼື ໃສ່ໃນຄຳອະທິບາຍ/ຄອມເມັ້ນປັກໝຸດ).
- ໂລໂກ້ສະໂມສອນ/ລີກ ເປັນເຄື່ອງໝາຍການຄ້າ → ລະບົບຂ້າມໄຟລ໌ຊື່ logo/crest/badge ເອງ.

## Wikimedia ຈຳກັດຄວາມໄວ
- ລະບົບຂໍເທື່ອລະຄຳຂໍ ເວັ້ນ 2–3 ວິ, ໃຊ້ຮູບຫຍໍ້ 1920px (ບໍ່ໂຫຼດໄຟລ໌ຕົ້ນສະບັບ), ແລະ cache ທຸກຢ່າງ 7 ວັນ.
- ຖ້າຂຶ້ນ `429`: ລະບົບລໍຖ້າເອງເຖິງ ~70 ວິ; ຖ້າຖືກສັ່ງລໍດົນກວ່ານັ້ນ ຈະຢຸດ ແລະ ບອກເວລາ → ລໍຖ້າແລ້ວ `plan` ໃໝ່. ຢ່າວົນລອງ.
- ຕັ້ງ `LAOSTUDIO_CONTACT=ອີເມວ ຫຼື ລິ້ງເພຈ` ເພື່ອໃສ່ໃນ User-Agent (Wikimedia ໃຫ້ໂຄຕາຫຼາຍຂຶ້ນແກ່ຜູ້ທີ່ລະບຸຕົວຕົນ) — ເປັນການຕັດສິນໃຈຂອງ Joe.

## Network ທີ່ຕ້ອງເປີດ (cloud environment `all-in-football` ຕັ້ງໄວ້ແລ້ວ)
`commons.wikimedia.org`, `thumb.wikimedia.org`, `upload.wikimedia.org`, `api.pexels.com`, `images.pexels.com`, `videos.pexels.com`,
`huggingface.co`, `us.aws.cdn.hf.co` (ໂມເດລສຽງ), `dl.dropboxusercontent.com` (ລິ້ງແຊຣ໌ Dropbox: ປ່ຽນ `www.dropbox.com` ເປັນ `dl.dropboxusercontent.com` ແລະ `dl=1`).
