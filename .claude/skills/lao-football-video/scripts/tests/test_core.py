"""ທົດສອບໄວ (ບໍ່ຕ້ອງອິນເຕີເນັດ, ບໍ່ຕ້ອງໂມເດລສຽງ):  python3 -m unittest discover -s scripts/tests"""
import os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from laostudio import gfx, laotext, script  # noqa: E402


class LaoText(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(laotext.number_words("21"), "ຊາວເອັດ")
        self.assertEqual(laotext.number_words("2014"), "ສອງພັນສິບສີ່")
        self.assertEqual(laotext.number_words("35,000"), "ສາມໝື່ນຫ້າພັນ")
        self.assertEqual(laotext.number_words("2.21"), "ສອງຈຸດສອງໜຶ່ງ")
        self.assertEqual(laotext.number_words("2-1"), "ສອງ ຕໍ່ ໜຶ່ງ")
        self.assertTrue(laotext.number_words("74%").endswith("ເປີເຊັນ"))

    def test_speech_plan(self):
        say = {"Pep Guardiola": "ເປບ ກວາດິໂອລາ"}
        toks, spoken, spans, missing = laotext.speech_plan("ປີ 2016 Pep Guardiola ມາຄຸມ Benfica ແທ້ໆ", say)
        self.assertIn("Pep Guardiola", toks)                       # multi-word name stays one token
        self.assertIn("ເປບ ກວາດິໂອລາ", spoken)
        self.assertIn("ແທ້ແທ້", spoken)                             # ໆ repeats the word
        self.assertEqual(missing, ["Benfica"])                     # Latin word with no Lao reading
        self.assertEqual(len(toks), len(spans))


class Script(unittest.TestCase):
    def _doc(self, body, voice="mms"):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "script.md")
        open(p, "w", encoding="utf-8").write("---\ntitle: ທົດສອບ *ເນັ້ນ*\nvoice: " + voice
                                             + "\nsay:\n  Neuer: ນອຍເອີ\n---\n" + body)
        return script.parse(p)

    def test_parse_and_timeline(self):
        doc = self._doc("# ເປີດ\n[img: a; b #2 | label: Neuer | stat: 2-1 = ຜົນ] *Neuer* ເຊຟໄດ້ 3 ຄັ້ງ\n"
                        "# ບົດສອງ\n[text: ປີ *1992* // ກົດໃໝ່] ຂໍ້ຄວາມທີສອງ\n")
        self.assertEqual(script.check(doc)[0], [])
        line = doc["chapters"][0]["lines"][0]
        self.assertEqual(line["keys"], ["Neuer"])
        sents = []
        for c in doc["chapters"]:
            for l in c["lines"]:
                toks = laotext.tokenize(l["text"], doc["meta"]["say"])
                sents.append({"dur": 4.0, "tokens": [{"t": t, "a": i * 0.3, "b": i * 0.3 + 0.3}
                                                      for i, t in enumerate(x for x in toks if x.strip())],
                              "tokens_all": toks})
        tl = script.build_timeline(doc, sents)
        kinds = [s["kind"] for s in tl["shots"]]
        self.assertEqual(kinds, ["media", "media", "chapter", "text", "outro"])
        self.assertEqual(tl["shots"][1]["media"]["n"], 2)
        self.assertEqual(tl["shots"][0]["label"], "Neuer")
        self.assertTrue(all(b["start"] >= a["end"] - 1e-6 for a, b in zip(tl["shots"], tl["shots"][1:])))

    def test_unknown_directive_and_missing_reading(self):
        doc = self._doc("[imgg: x] Ederson ຍິງ\n")
        probs, _ = script.check(doc)
        self.assertEqual(len(probs), 2)


    def test_names_use_lao_readings_unless_english_native(self):
        doc = self._doc("[img: x] Ederson ຍິງ 2 ປະຕູ!\n", voice="vox:any")
        self.assertEqual(len(script.check(doc)[0]), 1)              # default: a Lao reading is required
        doc = self._doc("[img: x] Ederson ຍິງ 2 ປະຕູ!\n", voice="vox:any\nenglish: native")
        self.assertEqual(script.check(doc)[0], [])
        spoken = laotext.speech_plan("Neuer ກັບ Ederson ຍິງ 2 ປະຕູ!", {"Neuer": "ນອຍເອີ"}, english=True)[1]
        self.assertIn("Ederson", spoken)
        self.assertIn("ສອງ", spoken)                                # numbers are always Lao words

    def test_emotions_and_pauses(self):
        from laostudio import voice
        doc = self._doc("[img: x | emo: suspense] ເວລາເຫຼືອບໍ່ຫຼາຍ... ແຕ່ຢູ່ໆ ກໍປ່ຽນໄປ!\n[img: x | emo: nope] ຂໍ້ຄວາມ\n")
        probs = script.check(doc)[0]
        self.assertEqual(len(probs), 1)                             # unknown emotion is reported
        self.assertIn("emo", probs[0])
        spoken = laotext.speech_plan("ເວລາເຫຼືອບໍ່ຫຼາຍ... ແຕ່ຢູ່ໆ ກໍປ່ຽນໄປ!", punct=True)[1]
        self.assertEqual(spoken.count(laotext.PAUSE), 1)            # "..." becomes a real pause
        self.assertIn("ຢູ່ຢູ່", spoken)
        self.assertIn("!", spoken)
        self.assertLess(voice.EMO["suspense"]["speed"], voice.EMO["climax"]["speed"])
        self.assertLess(voice.EMO["suspense"]["gain"], voice.EMO["climax"]["gain"])
        self.assertGreater(voice.EMO["suspense"]["pause"], voice.EMO["climax"]["pause"])
        self.assertEqual(voice.emotion(None)[0], "story")
        self.assertEqual(voice.emotion("excited")[0], "climax")


class CtcAlign(unittest.TestCase):
    def test_viterbi_finds_label_frames(self):
        import numpy as np
        from laostudio import ctcalign
        # 3 labels (ids 1,2,1) clearly emitted at frames 2, 5 and 8 of 10; blank = 0
        lp = np.full((10, 3), -9.0); lp[:, 0] = -0.1
        for t, k in ((2, 1), (5, 2), (8, 1)):
            lp[t] = -9.0; lp[t, k] = -0.1
        first, last = ctcalign.viterbi(lp, np.array([1, 2, 1]), 0)
        self.assertEqual(list(first), [2, 5, 8])
        self.assertEqual(list(last), [2, 5, 8])


class Gfx(unittest.TestCase):
    def test_lao_text_renders_and_wraps(self):
        self.assertEqual(gfx.RAQM.name, "RAQM", "Pillow has no raqm: Lao marks would misplace")
        im = gfx.text_block("ເປັນຫຍັງຜູ້ຮັກສາປະຕູຍຸກໃໝ່ ຕ້ອງ ຫຼິ້ນດ້ວຍຕີນ? Pep 2-1", 60, (0, 0, 0), 500, keys=["ຫຼິ້ນດ້ວຍຕີນ?"],
                            key_color=(255, 0, 0))
        self.assertLessEqual(im.size[0], 500 + 2 * 12 + 4)
        self.assertGreater(im.size[1], 60 * 1.5 * 2)                # wrapped to 2+ lines
        px = im.convert("RGBA").getdata()
        self.assertTrue(any(p[0] > 200 and p[1] < 60 and p[3] > 200 for p in px))   # key words are red


if __name__ == "__main__":
    unittest.main()
