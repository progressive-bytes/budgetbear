#!/usr/bin/env python3
"""Convert fastlane screenshots (PNG) into the website's small webp images.

Normally build.py does this as part of a full build. Use this script on its own to list the PNG files or to run only this step.

Usage (paths are relative to the website repo root):
    python3 _src/screenshots.py                  # all languages that have content
    python3 _src/screenshots.py --lang de        # only this language (repeatable)
    python3 _src/screenshots.py --list de-DE     # list the PNG files in one fastlane locale folder
    python3 _src/screenshots.py --dry-run        # show what would be converted, write nothing
    python3 _src/screenshots.py --force          # convert again even if the webp is up to date
    python3 _src/screenshots.py /path/to/fastlane/screenshots     # source folder (overrides screenshots.json)

screenshots.json maps each website image to a file name in the fastlane locale folder ("shots"). The locale folder of a
language is its "source_locale" from config.json, or the entry in screenshots.json "locales". The result is written to
<language folder>/images/<website name>.webp (the root images/ folder for the default language).
Only languages that have a content file are handled. Requires cwebp (macOS: brew install webp). Python 3 standard library only.
"""
import argparse, json, shutil, subprocess, sys

import sitecfg as S

OPT = json.loads((S.SRC / "screenshots.json").read_text(encoding="utf-8"))


def sync(langs, source=None, force=False, dry_run=False):
    """Convert the screenshots of `langs` (languages with content). Returns changes, up-to-date count, problems, unavailable."""
    r = {"changes": [], "skipped": 0, "problems": [], "unavailable": None}
    src_dir = S.resolve(source or OPT.get("source_dir", ""))
    if not src_dir.is_dir():
        r["unavailable"] = f"fastlane screenshots folder not found: {src_dir} (set source_dir in _src/screenshots.json)"
        return r
    if not dry_run and not shutil.which("cwebp"):
        r["unavailable"] = "cwebp not found (macOS: brew install webp)"
        return r
    for code in langs:
        locale = OPT.get("locales", {}).get(code) or S.LANG_CFG[code].get("source_locale")
        folder = src_dir / locale if locale else None
        if not folder or not folder.is_dir():
            r["problems"].append(f"{code}: no fastlane folder {locale or '(no source_locale)'}")
            continue
        for web_name, file_name in OPT["shots"].items():
            src = folder / file_name
            out = S.images_dir(code) / f"{web_name}.webp"
            if not src.exists():
                r["problems"].append(f"{code}: missing {locale}/{file_name}")
            elif out.exists() and out.stat().st_mtime >= src.stat().st_mtime and not force:
                r["skipped"] += 1
            elif dry_run:
                r["changes"].append(f"{code}: {locale}/{file_name} -> {out.relative_to(S.ROOT)}")
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                p = subprocess.run(["cwebp", "-quiet", "-q", str(OPT["quality"]), "-m", "6", "-sharp_yuv",
                                    "-resize", str(OPT["width"]), "0", str(src), "-o", str(out)], capture_output=True, text=True)
                if p.returncode:
                    r["problems"].append(f"{code}: cwebp failed for {file_name}: {p.stderr.strip()}")
                else:
                    r["changes"].append(f"{code}: {locale}/{file_name} -> {out.relative_to(S.ROOT)}")
    return r


def main():
    ap = argparse.ArgumentParser(prog="python3 _src/screenshots.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", help="fastlane screenshots folder (default: source_dir of screenshots.json)")
    ap.add_argument("--lang", action="append", default=[], metavar="LANG", help="only this language (repeatable)")
    ap.add_argument("--list", metavar="LOCALE", help="list the PNG files of one fastlane locale folder")
    ap.add_argument("--dry-run", action="store_true", help="show what would be done, write nothing")
    ap.add_argument("--force", action="store_true", help="convert again even if the webp is up to date")
    a = ap.parse_args()

    if a.list:
        base = S.resolve(a.source or OPT.get("source_dir", ""))
        folder = base / a.list
        if not folder.is_dir():
            sys.exit(f"error: {folder} does not exist" + (f"; locale folders: {', '.join(sorted(d.name for d in base.iterdir() if d.is_dir()))}" if base.is_dir() else ""))
        print("\n".join(sorted(f.name for f in folder.glob("*.png"))))
        return

    active = S.active_languages()
    bad = [l for l in a.lang if l not in active]
    if bad:
        sys.exit(f"error: no content yet for {', '.join(bad)} (languages with content: {', '.join(active)})")
    r = sync(a.lang or active, a.source, a.force, a.dry_run)
    if r["unavailable"]:
        sys.exit("error: " + r["unavailable"])
    for c in r["changes"]:
        print(("would convert " if a.dry_run else "converted ") + c)
    for p in r["problems"]:
        print("problem:", p)
    print(f"{len(r['changes'])} {'to convert' if a.dry_run else 'converted'}, {r['skipped']} up to date, {len(r['problems'])} problem(s)")
    sys.exit(1 if r["problems"] else 0)


if __name__ == "__main__":
    main()
