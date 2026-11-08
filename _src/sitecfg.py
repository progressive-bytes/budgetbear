"""Shared configuration helpers for build.py, badges.py and screenshots.py."""
import json
from pathlib import Path

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent
CFG = json.loads((SRC / "config.json").read_text(encoding="utf-8"))
DEFAULT = CFG["default_language"]
LANG_CFG = {l["code"]: l for l in CFG["languages"]}


def content_file(code):
    return SRC / "content" / f"{code}.json"


def active_languages():
    """Languages that are built: the default language and every language that has a content file."""
    return [c for c in LANG_CFG if c == DEFAULT or content_file(c).exists()]


def images_dir(code):
    """The language's own images folder: root images/ for the default language, <dir>/images/ for the others."""
    sub = "" if code == DEFAULT else LANG_CFG[code].get("dir", code) + "/"
    return ROOT / sub / "images"


def resolve(raw):
    """A path from a config file: ~ is expanded, relative paths are relative to the website repo root."""
    p = Path(raw).expanduser() if raw else Path("")
    return p if p.is_absolute() else (ROOT / p).resolve()
