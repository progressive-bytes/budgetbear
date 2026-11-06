#!/usr/bin/env python3
"""Convert fastlane screenshots (PNG) into the website's small webp images.

Usage (paths are relative to the website repo root):
    python3 _src/screenshots.py                  # all languages in config.json
    python3 _src/screenshots.py --lang de        # only this language (repeatable)
    python3 _src/screenshots.py --list de-DE     # list the PNG files in one fastlane locale folder
    python3 _src/screenshots.py --dry-run        # show what would be converted, write nothing
    python3 _src/screenshots.py --force          # convert again even if the webp is up to date
    python3 _src/screenshots.py /path/to/fastlane/screenshots     # source folder (overrides screenshots.json)

screenshots.json maps each website image to a file name in the fastlane locale folder ("shots"). The locale folder of a
language is its "source_locale" from config.json, or the entry in screenshots.json "locales". The result is written to
<language folder>/images/<website name>.webp (the root images/ folder for the default language).
Requires cwebp (macOS: brew install webp). Python 3 standard library only.
"""
import argparse, json, shutil, subprocess, sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent
CFG = json.loads((SRC / "config.json").read_text(encoding="utf-8"))
OPT = json.loads((SRC / "screenshots.json").read_text(encoding="utf-8"))
DEFAULT = CFG["default_language"]
LANGS = {l["code"]: l for l in CFG["languages"]}


def out_dir(code):
    sub = "" if code == DEFAULT else LANGS[code].get("dir", code) + "/"
    return ROOT / sub / "images"


def main():
    ap = argparse.ArgumentParser(prog="python3 _src/screenshots.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", help="fastlane screenshots folder (default: source_dir of screenshots.json)")
    ap.add_argument("--lang", action="append", default=[], metavar="LANG", help="only this language (repeatable)")
    ap.add_argument("--list", metavar="LOCALE", help="list the PNG files of one fastlane locale folder")
    ap.add_argument("--dry-run", action="store_true", help="show what would be done, write nothing")
    ap.add_argument("--force", action="store_true", help="convert again even if the webp is up to date")
    a = ap.parse_args()

    source = Path(a.source or OPT.get("source_dir", "")).expanduser()
    if not source.is_absolute():
        source = (ROOT / source).resolve()
    if not source.is_dir():
        sys.exit(f"error: fastlane screenshots folder not found: {source}\n"
                 "       give it as argument or set source_dir in _src/screenshots.json")

    if a.list:
        folder = source / a.list
        if not folder.is_dir():
            sys.exit(f"error: {folder} does not exist; locale folders: {', '.join(sorted(d.name for d in source.iterdir() if d.is_dir()))}")
        print("\n".join(sorted(f.name for f in folder.glob("*.png"))))
        return

    unknown = [l for l in a.lang if l not in LANGS]
    if unknown:
        sys.exit(f"error: unknown language {', '.join(unknown)} (languages: {', '.join(LANGS)})")
    if not a.dry_run and not shutil.which("cwebp"):
        sys.exit("error: cwebp not found. Install it with: brew install webp")

    active = {c for c in LANGS if c == DEFAULT or (SRC / "content" / f"{c}.json").exists()}
    problems = 0
    for code in (a.lang or list(LANGS)):
        note = "" if code in active else " (no content yet)"
        locale = OPT.get("locales", {}).get(code) or LANGS[code].get("source_locale")
        folder = source / locale if locale else None
        if not folder or not folder.is_dir():
            print(f"{code:8} no fastlane folder {locale or '(no source_locale)'}{note}")
            problems += code in active
            continue
        done = skip = bad = 0
        for web_name, file_name in OPT["shots"].items():
            src = folder / file_name
            out = out_dir(code) / f"{web_name}.webp"
            if not src.exists():
                print(f"{code:8} missing: {locale}/{file_name}")
                bad += 1
            elif out.exists() and out.stat().st_mtime >= src.stat().st_mtime and not a.force:
                skip += 1
            elif a.dry_run:
                print(f"{code:8} {locale}/{file_name} -> {out.relative_to(ROOT)}")
                done += 1
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                r = subprocess.run(["cwebp", "-quiet", "-q", str(OPT["quality"]), "-m", "6", "-sharp_yuv",
                                    "-resize", str(OPT["width"]), "0", str(src), "-o", str(out)], capture_output=True, text=True)
                if r.returncode:
                    print(f"{code:8} cwebp failed for {file_name}: {r.stderr.strip()}")
                    bad += 1
                else:
                    done += 1
        print(f"{code:8} {locale:9} {done} converted, {skip} up to date, {bad} problem(s) -> {out_dir(code).relative_to(ROOT)}/{note}")
        problems += bad if code in active else 0
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
