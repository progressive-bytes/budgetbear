#!/usr/bin/env python3
"""Convert the fastlane snapshot PNGs into the website's small webp screenshots.

Usage (from anywhere; paths are relative to the website repo root):
    python3 _src/screenshots.py                  # all languages in config.json
    python3 _src/screenshots.py --lang de        # only this language (repeatable)
    python3 _src/screenshots.py --list de-DE     # show the PNG names in one fastlane locale folder
    python3 _src/screenshots.py --dry-run        # show what would be converted, write nothing
    python3 _src/screenshots.py --force          # convert again even if the webp is up to date
    python3 _src/screenshots.py /path/to/fastlane/screenshots     # source folder (overrides screenshots.json)

For every language the PNGs of its fastlane locale folder (config.json "source_locale", or the override in
screenshots.json "locales") are converted to <language folder>/images/<WebName>.webp: the root images/ folder for
the default language, <dir>/images/ for the others. Which snapshot becomes which website image is set in
screenshots.json "shots" (website name -> snapshot name). Requires cwebp (macOS: brew install webp).
Python 3 standard library only.
"""
import argparse, collections, json, shutil, struct, subprocess, sys
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


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def locale_folder(source, code):
    """The fastlane locale folder that serves a website language, or (None, candidates)."""
    wanted = [OPT.get("locales", {}).get(code), LANGS[code].get("source_locale"), code]
    for w in wanted:
        if w and (source / w).is_dir():
            return source / w, []
    lang = code.split("-")[0]
    cand = sorted(d.name for d in source.iterdir() if d.is_dir() and d.name.split("-")[0] == lang)
    return (source / cand[0], []) if len(cand) == 1 else (None, cand)


def main():
    ap = argparse.ArgumentParser(prog="python3 _src/screenshots.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", help="fastlane screenshots folder (default: source_dir of screenshots.json)")
    ap.add_argument("--lang", action="append", default=[], metavar="LANG", help="only this language (repeatable)")
    ap.add_argument("--list", metavar="LOCALE", help="list the PNG names found in one fastlane locale folder")
    ap.add_argument("--dry-run", action="store_true", help="show what would be done, write nothing")
    ap.add_argument("--force", action="store_true", help="convert again even if the webp is up to date")
    a = ap.parse_args()

    raw = a.source or OPT.get("source_dir", "")
    source = Path(raw).expanduser()
    if not source.is_absolute():
        source = (ROOT / source).resolve()
    if not raw or not source.is_dir():
        sys.exit(f"error: fastlane screenshots folder not found: {source}\n"
                 "       give it as argument or set source_dir in _src/screenshots.json")
    device = OPT["device"]

    if a.list:
        folder = source / a.list
        if not folder.is_dir():
            sys.exit(f"error: {folder} does not exist; locale folders: {', '.join(sorted(d.name for d in source.iterdir() if d.is_dir()))}")
        for f in sorted(folder.glob("*.png")):
            print(("* " if device in f.name else "  ") + f.name + f"   {png_size(f) and 'x'.join(map(str, png_size(f)))}")
        print(f'\n* = matches device "{device}"')
        return

    unknown = [l for l in a.lang if l not in LANGS]
    if unknown:
        sys.exit(f"error: unknown language {', '.join(unknown)} (languages: {', '.join(LANGS)})")
    if not a.dry_run and not shutil.which("cwebp"):
        sys.exit("error: cwebp not found. Install it with: brew install webp")

    active = {c for c in LANGS if c == DEFAULT or (SRC / "content" / f"{c}.json").exists()}
    totals = collections.Counter()
    sizes = collections.Counter()
    problems = 0
    for code in (a.lang or list(LANGS)):
        folder, cand = locale_folder(source, code)
        tag = "" if code in active else " (pending, no content yet)"
        if folder is None:
            hint = f" (candidates: {', '.join(cand)}; set one in screenshots.json \"locales\")" if cand else ""
            print(f"{code:8} no fastlane locale folder{hint}{tag}")
            problems += code in active or bool(a.lang)
            continue
        files = [f for f in folder.glob("*.png") if device in f.name]
        done = skip = bad = 0
        for web, snap in OPT["shots"].items():
            hits = [f for f in files if f.stem.endswith("-" + snap)]
            if len(hits) != 1:
                what = "no PNG" if not hits else f"{len(hits)} PNGs ({', '.join(h.name for h in hits)})"
                print(f'{code:8} {web}: {what} for "{snap}" in {folder.name} with device "{device}"')
                bad += 1
                continue
            src = hits[0]
            sizes[png_size(src)] += 1
            out = out_dir(code) / f"{web}.webp"
            if out.exists() and out.stat().st_mtime >= src.stat().st_mtime and not a.force:
                skip += 1
                continue
            if a.dry_run:
                print(f"{code:8} would convert {src.name} -> {out.relative_to(ROOT)}")
                done += 1
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            r = subprocess.run(["cwebp", "-quiet", "-q", str(OPT["quality"]), "-m", "6", "-sharp_yuv",
                                "-resize", str(OPT["width"]), "0", str(src), "-o", str(out)], capture_output=True, text=True)
            if r.returncode:
                print(f"{code:8} cwebp failed for {src.name}: {r.stderr.strip()}")
                bad += 1
                continue
            totals["bytes"] += out.stat().st_size
            done += 1
        print(f"{code:8} {folder.name:9} {done} converted, {skip} up to date, {bad} problem(s)  -> {out_dir(code).relative_to(ROOT)}/{tag}")
        problems += bad if (code in active or a.lang) else 0
    if len(sizes) > 1:
        print("warning: source PNGs differ in size: " + ", ".join(f"{w}x{h} ({n}x)" for (w, h), n in sizes.items() if (w, h)) +
              f'. Check the device filter "{device}" in screenshots.json.')
    elif sizes:
        (w, h), = sizes.keys()
        print(f"source size {w}x{h} -> width {OPT['width']} px" + (f", {totals['bytes'] // 1024} KB written" if totals["bytes"] else ""))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
