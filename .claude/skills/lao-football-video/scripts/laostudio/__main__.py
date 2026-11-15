"""python -m laostudio <command>

  new   <project> [--title "..."]      ສ້າງໂຟນເດີໂປຣເຈັກ + script.md ຕົວຢ່າງ
  check <project>                      ກວດ script.md (ຄຳອ່ານ, ຄຳສັ່ງ) ໂດຍບໍ່ render
  plan  <project>                      ສຽງພາກ + ຫາ footage + ແຜນຊັອດ (ບໍ່ render)
  run   <project> [--aspect 9:16] [--both] [--workers N] [--offline] [--force]
"""
import argparse, sys

from . import pipeline, script


def main(argv=None):
    ap = argparse.ArgumentParser(prog="laostudio", description="Lao football video studio")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new"); n.add_argument("project"); n.add_argument("--title")
    c = sub.add_parser("check"); c.add_argument("project")
    for name in ("plan", "run"):
        r = sub.add_parser(name); r.add_argument("project")
        r.add_argument("--aspect", choices=["16:9", "9:16"]); r.add_argument("--both", action="store_true")
        r.add_argument("--workers", type=int); r.add_argument("--offline", action="store_true")
        r.add_argument("--force", action="store_true"); r.add_argument("--crf", type=int, default=21)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "new":
            print(pipeline.new_project(a.project, a.title))
        elif a.cmd == "check":
            doc = script.parse(a.project.rstrip("/") + "/script.md")
            probs, notes = script.check(doc)
            for x in notes:
                print("ໝາຍເຫດ:", x)
            for x in probs:
                print("✗", x)
            n_lines = sum(len(ch["lines"]) for ch in doc["chapters"])
            print(f"{len(doc['chapters'])} ບົດ, {n_lines} ປະໂຫຍກ — " + ("ຜ່ານ ✓" if not probs else f"{len(probs)} ບັນຫາ"))
            return 1 if probs else 0
        else:
            aspects = ["16:9", "9:16"] if a.both else [a.aspect]
            for asp in aspects:
                pipeline.run(a.project, aspect=asp, workers=a.workers, offline=a.offline, force=a.force,
                             plan_only=a.cmd == "plan", crf=a.crf)
    except script.ScriptError as e:
        print("ຜິດພາດ:", e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
