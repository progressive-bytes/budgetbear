#!/usr/bin/env python3
"""Copy the App Store badges named in the content files from Apple's badge download into the website.

Normally build.py does this as part of a full build. Use this script on its own to look up file names or to run only this step.

Usage (paths are relative to the website repo root):
    python3 _src/badges.py                    # copy the badge of every language that has content
    python3 _src/badges.py --lang de          # only this language (repeatable)
    python3 _src/badges.py --list DE          # list the badge files in the download whose name contains "DE"
    python3 _src/badges.py --dry-run          # show what would be copied
    python3 _src/badges.py --force            # copy again even if the file is already there
    python3 _src/badges.py /path/to/badges    # folder with Apple's badge download (overrides badges.json)

Each language names its badge in _src/content/<code>.json ("badge_file"). The script looks for that exact file name
anywhere below the download folder and copies it to the language's images folder (root images/ for the default
language, <dir>/images/ for the others). A language that uses the default language's badge needs no copy.
Only languages that have a content file are handled. The download itself stays outside the repository.
Python 3 standard library only.
"""
import argparse, json, shutil, sys

import sitecfg as S

OPT = json.loads((S.SRC / "badges.json").read_text(encoding="utf-8"))


def badge_file(code):
    return json.loads(S.content_file(code).read_text(encoding="utf-8"))["badge_file"]


def index(source):
    found = {}
    for f in source.rglob("*.svg"):
        found.setdefault(f.name, []).append(f)
    return found


def sync(langs, source=None, force=False, dry_run=False):
    """Copy the badges of `langs` (languages with content). Returns changes, up-to-date count, problems, unavailable."""
    r = {"changes": [], "skipped": 0, "problems": [], "unavailable": None}
    src = S.resolve(source or OPT.get("source_dir", ""))
    if not src.is_dir():
        r["unavailable"] = f"badge download not found: {src} (set source_dir in _src/badges.json)"
        return r
    found = index(src)
    default_file = badge_file(S.DEFAULT)
    for code in langs:
        name = badge_file(code)
        if code != S.DEFAULT and name == default_file:
            r["skipped"] += 1                                  # uses the default language's badge
            continue
        target = S.images_dir(code) / name
        if target.exists() and not force:
            r["skipped"] += 1
        elif name not in found:
            r["problems"].append(f"{code}: badge {name} not found in {src}")
        elif len(found[name]) > 1:
            r["problems"].append(f"{code}: badge {name} exists {len(found[name])} times in the download; pass a narrower folder")
        else:
            r["changes"].append(f"{code}: {name} -> {target.relative_to(S.ROOT)}")
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(found[name][0], target)
    return r


def main():
    ap = argparse.ArgumentParser(prog="python3 _src/badges.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", help="folder with Apple's badge download (default: source_dir of badges.json)")
    ap.add_argument("--lang", action="append", default=[], metavar="LANG", help="only this language (repeatable)")
    ap.add_argument("--list", nargs="?", const="", metavar="TEXT", help="list the badge files whose name contains TEXT")
    ap.add_argument("--dry-run", action="store_true", help="show what would be copied, write nothing")
    ap.add_argument("--force", action="store_true", help="copy again even if the file is already there")
    a = ap.parse_args()

    if a.list is not None:
        src = S.resolve(a.source or OPT.get("source_dir", ""))
        if not src.is_dir():
            sys.exit(f"error: badge download not found: {src}")
        names = sorted(n for n in index(src) if a.list.lower() in n.lower())
        print("\n".join(names) if names else "no matching badge files")
        return

    active = S.active_languages()
    bad = [l for l in a.lang if l not in active]
    if bad:
        sys.exit(f"error: no content yet for {', '.join(bad)} (languages with content: {', '.join(active)})")
    r = sync(a.lang or active, a.source, a.force, a.dry_run)
    if r["unavailable"]:
        sys.exit("error: " + r["unavailable"])
    for c in r["changes"]:
        print(("would copy " if a.dry_run else "copied ") + c)
    for p in r["problems"]:
        print("problem:", p)
    print(f"{len(r['changes'])} {'to copy' if a.dry_run else 'copied'}, {r['skipped']} up to date, {len(r['problems'])} problem(s)")
    sys.exit(1 if r["problems"] else 0)


if __name__ == "__main__":
    main()
