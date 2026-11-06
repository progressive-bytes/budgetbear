#!/usr/bin/env python3
"""Copy the App Store badges named in the content files from Apple's badge download into the website.

Usage (paths are relative to the website repo root):
    python3 _src/badges.py                    # copy the badge of every language that has content
    python3 _src/badges.py --list DE          # list the badge files in the download whose name contains "DE"
    python3 _src/badges.py --dry-run          # show what would be copied
    python3 _src/badges.py --force            # copy again even if the file is already there
    python3 _src/badges.py /path/to/badges    # folder with Apple's badge download (overrides badges.json)

Each language names its badge in _src/content/<code>.json ("badge_file"). The script looks for that exact file name
anywhere below the download folder and copies it to the language's images folder (root images/ for the default
language, <dir>/images/ for the others). A language that uses the default language's badge needs no copy.
The download itself stays outside the repository. Python 3 standard library only.
"""
import argparse, json, shutil, sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent
CFG = json.loads((SRC / "config.json").read_text(encoding="utf-8"))
OPT = json.loads((SRC / "badges.json").read_text(encoding="utf-8"))
DEFAULT = CFG["default_language"]
LANGS = {l["code"]: l for l in CFG["languages"]}


def out_dir(code):
    return ROOT / ("" if code == DEFAULT else LANGS[code].get("dir", code) + "/") / "images"


def main():
    ap = argparse.ArgumentParser(prog="python3 _src/badges.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", help="folder with Apple's badge download (default: source_dir of badges.json)")
    ap.add_argument("--list", nargs="?", const="", metavar="TEXT", help="list the badge files whose name contains TEXT")
    ap.add_argument("--dry-run", action="store_true", help="show what would be copied, write nothing")
    ap.add_argument("--force", action="store_true", help="copy again even if the file is already there")
    a = ap.parse_args()

    source = Path(a.source or OPT.get("source_dir", "")).expanduser()
    if not source.is_absolute():
        source = (ROOT / source).resolve()
    if not source.is_dir():
        sys.exit(f"error: badge folder not found: {source}\n       give it as argument or set source_dir in _src/badges.json")
    found = {}
    for f in source.rglob("*.svg"):
        found.setdefault(f.name, []).append(f)

    if a.list is not None:
        names = sorted(n for n in found if a.list.lower() in n.lower())
        print("\n".join(names) if names else "no matching badge files")
        return

    default_file = None
    problems = 0
    for code in LANGS:
        f = SRC / "content" / f"{code}.json"
        if not f.exists():
            continue
        name = json.loads(f.read_text(encoding="utf-8"))["badge_file"]
        if code == DEFAULT:
            default_file = name
        elif name == default_file:
            print(f"{code:8} uses the default language's badge ({name}); nothing to copy")
            continue
        target = out_dir(code) / name
        if target.exists() and not a.force:
            print(f"{code:8} {name} is already in {out_dir(code).relative_to(ROOT)}/")
        elif name not in found:
            print(f"{code:8} {name} not found in {source}")
            problems += 1
        elif len(found[name]) > 1:
            print(f"{code:8} {name} exists {len(found[name])} times in the download; remove the duplicates or pass a narrower folder")
            problems += 1
        else:
            print(f"{code:8} {'would copy' if a.dry_run else 'copied'} {name} -> {target.relative_to(ROOT)}")
            if not a.dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(found[name][0], target)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
