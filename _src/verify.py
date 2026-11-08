"""Read-only verification of the finished website (build.py --verify).

Checks that everything that gets uploaded is complete and consistent: every language has its pages, the pages are current,
every link and image resolves, each language links its own badge and screenshots (which exist and are valid), every page has a
complete language switcher and hreflang list, and the App Store URLs point at pages that exist.
"""
import hashlib, json, os, re, subprocess, sys
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

import sitecfg as S

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
SKIP_DIRS = {"images", "styles", "_src", ".git", "node_modules"}


class PageInfo(HTMLParser):
    """Collects what verification needs from a generated page."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = self.title = self.canonical = None
        self.meta, self.alt, self.refs, self.imgs, self.options, self.jsonld, self.problems = {}, [], [], [], [], [], []
        self.stack, self._title, self._menu, self._opt, self._ld, self._buf = [], False, None, None, False, ""

    def _start(self, tag, attrs, push):
        a = dict(attrs)
        cls = a.get("class", "").split()
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "title":
            self._title, self.title = True, ""
        elif tag == "meta" and (a.get("name") or a.get("property")):
            self.meta[a.get("name") or a.get("property")] = a.get("content", "")
        elif tag == "link":
            rel = a.get("rel", "")
            if rel == "canonical":
                self.canonical = a.get("href")
            elif rel == "alternate" and a.get("hreflang"):
                self.alt.append((a["hreflang"], a.get("href")))
            if a.get("href"):
                self.refs.append(a["href"])
        elif tag == "a" and a.get("href") is not None:
            self.refs.append(a["href"])
        elif tag in ("img", "script") and a.get("src"):
            self.refs.append(a["src"])
        if tag == "img":
            self.imgs.append(a)
        if tag == "div" and "language-menu" in cls:
            self._menu = len(self.stack)
        if self._menu is not None and tag in ("a", "span") and "language-option" in cls:
            self._opt = {"tag": tag, "class": a.get("class", ""), "href": a.get("href"), "hreflang": a.get("hreflang"), "text": ""}
        if tag == "script" and a.get("type") == "application/ld+json":
            self._ld, self._buf = True, ""
        if push and tag not in VOID:
            self.stack.append(tag)

    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs, True)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs, False)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if tag == "title":
            self._title = False
        if tag in ("a", "span") and self._opt is not None:
            self._opt["text"] = self._opt["text"].strip()
            self.options.append(self._opt)
            self._opt = None
        if tag == "script" and self._ld:
            self.jsonld.append(self._buf)
            self._ld = False
        if not self.stack or self.stack[-1] != tag:
            self.problems.append(f"unbalanced </{tag}> (open: {self.stack[-1] if self.stack else 'nothing'})")
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
            return
        self.stack.pop()
        if tag == "div" and self._menu is not None and len(self.stack) == self._menu:
            self._menu = None

    def handle_data(self, d):
        if self._title:
            self.title += d
        if self._opt is not None:
            self._opt["text"] += d
        if self._ld:
            self._buf += d

    def finish(self):
        self.close()
        if self.stack:
            self.problems.append("unclosed tags: " + ", ".join(self.stack))
        return self


def webp_size(path):
    d = Path(path).read_bytes()[:32]
    if d[:4] != b"RIFF" or d[8:12] != b"WEBP":
        return None
    kind = d[12:16]
    if kind == b"VP8 ":
        return ((d[26] | d[27] << 8) & 0x3fff, (d[28] | d[29] << 8) & 0x3fff)
    if kind == b"VP8L":
        bits = int.from_bytes(d[21:25], "little")
        return ((bits & 0x3fff) + 1, ((bits >> 14) & 0x3fff) + 1)
    if kind == b"VP8X":
        return (int.from_bytes(d[24:27], "little") + 1, int.from_bytes(d[27:30], "little") + 1)
    return None


class Report:
    def __init__(self):
        self.checks = []

    def check(self, title):
        c = {"title": title, "errors": [], "warnings": []}
        self.checks.append(c)
        return c

    def show(self):
        errs = warns = 0
        for c in self.checks:
            e, w = sorted(set(c["errors"])), sorted(set(c["warnings"]))
            errs, warns = errs + len(e), warns + len(w)
            mark = "✗" if e else ("!" if w else "✓")
            print(f" {mark} {c['title']}" + (f"  ({len(e)} error(s))" if e else ""))
            for x in e:
                print(f"     error: {x}")
            for x in w:
                print(f"     warning: {x}")
        print()
        print("RESULT: " + ("OK" + (f", {warns} warning(s)" if warns else ", nothing wrong found") if not errs
                            else f"{errs} error(s), {warns} warning(s). Do not upload yet."))
        return 1 if errs else 0


def git(root, *args):
    r = subprocess.run(["git", "-c", "safe.directory=*", "-C", str(root), *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def run(c):
    """c: a namespace with root, base, default, active, pending, langs, data, outputs, page_dir, page_path, cfg, all_langs."""
    R = Report()
    root, base, default = c.root, c.base, c.default
    opt = {"metadata_dir": "", "allow_default_badge": [], "max_asset_kb": 500}
    vf = S.SRC / "verify.json"
    if vf.exists():
        opt.update(json.loads(vf.read_text(encoding="utf-8")))
    shots_opt = json.loads((S.SRC / "screenshots.json").read_text(encoding="utf-8"))
    pages = c.cfg["pages"]
    url = lambda lg, page: base + c.page_path(lg, page)
    file_of = lambda lg, page: root / (c.page_dir(lg) + page + ".html")

    def resolve(page_file, ref):
        """The file a relative link on a page points to (None for external links)."""
        if re.match(r"^(https?:|mailto:|tel:|#|javascript:)", ref):
            return None
        ref = ref.split("#")[0].split("?")[0]
        target = Path(os.path.normpath(page_file.parent / ref)) if ref else page_file
        if ref.endswith("/") or ref in ("", ".", "./") or target.is_dir():
            target = target / "index.html"
        elif not target.suffix:
            target = target.with_suffix(".html")
        return target

    ck = R.check(f"content is valid ({', '.join(c.langs)})")

    # ---- languages and files
    ck = R.check("every language has its pages, and the pages are current")
    if c.all_langs:
        used = {}
        for loc, code in c.cfg.get("app_store_locales", {}).items():
            used.setdefault(code, []).append(loc)
        for code in c.pending:
            if code in used:
                ck["errors"].append(f"{code}: no content yet, but the App Store locales {', '.join(used[code])} link to its pages")
            else:
                ck["warnings"].append(f"{code}: configured but has no content (not built)")
    infos, missing_pages = {}, set()
    for lg in c.langs:
        for page in pages:
            f = file_of(lg, page)
            rel = f.relative_to(root)
            if not f.exists():
                ck["errors"].append(f"{rel}: missing")
                missing_pages.add(f)
                continue
            html = f.read_text(encoding="utf-8")
            if html != c.outputs.get(f):
                ck["errors"].append(f"{rel}: differs from the sources (run build.py)")
            infos[f] = PageInfo()
            infos[f].feed(html)
            infos[f].finish()
    for f, expected in c.outputs.items():                       # legacy redirect stubs
        if f not in infos and f.parent.name in c.cfg.get("redirect_folders", []):
            if not f.exists():
                ck["errors"].append(f"{f.relative_to(root)}: missing (redirect stub)")
            elif f.read_text(encoding="utf-8") != expected:
                ck["errors"].append(f"{f.relative_to(root)}: redirect stub differs from the sources")
    if c.all_langs:
        known = {c.page_dir(lg).strip("/") for lg in c.active} | set(c.cfg.get("redirect_folders", []))
        for d in sorted(p for p in root.iterdir() if p.is_dir() and p.name not in SKIP_DIRS and not p.name.startswith(".")):
            if (d / "index.html").exists() and d.name not in known:
                ck["errors"].append(f"{d.name}/: page folder of a language that is not built (orphan, would be uploaded)")

    # ---- page structure: html, head, hreflang, switcher
    ck = R.check("every page is well formed and has correct title, language, canonical URL and hreflang list")
    ck2 = R.check("every page has a complete language switcher")
    for f, info in infos.items():
        lg = next(l for l in c.langs if f.parent == root / c.page_dir(l).strip("/") or (l == default and f.parent == root))
        page = f.stem
        rel = f.relative_to(root)
        ck["errors"] += [f"{rel}: {p}" for p in info.problems]
        if not (info.title or "").strip():
            ck["errors"].append(f"{rel}: empty <title>")
        if not info.meta.get("description", "").strip():
            ck["errors"].append(f"{rel}: empty meta description")
        if info.lang != lg:
            ck["errors"].append(f'{rel}: <html lang="{info.lang}"> should be "{lg}"')
        if info.canonical != url(lg, page):
            ck["errors"].append(f"{rel}: canonical is {info.canonical}, expected {url(lg, page)}")
        if info.meta.get("og:url") != url(lg, page):
            ck["errors"].append(f"{rel}: og:url is {info.meta.get('og:url')}, expected {url(lg, page)}")
        want = [(a, url(a, page)) for a in c.active] + [("x-default", url(default, page))]
        if sorted(info.alt) != sorted(want):
            missing = sorted(set(want) - set(info.alt))
            ck["errors"].append(f"{rel}: hreflang list is incomplete or wrong (missing: {', '.join(a for a, _ in missing) or 'none'}; unexpected: "
                                f"{', '.join(a for a, _ in sorted(set(info.alt) - set(want))) or 'none'})")
        if page == "index":
            try:
                ld = json.loads(info.jsonld[0])
                if ld["offers"]["priceCurrency"] != c.data[lg]["currency"]:
                    ck["errors"].append(f"{rel}: structured data currency differs from the content file")
            except (IndexError, KeyError, ValueError):
                ck["errors"].append(f"{rel}: structured data (JSON-LD) missing or invalid")
        # switcher
        opts = info.options
        if [o["text"] for o in opts] != [c.data[a]["name"] for a in c.active]:
            ck2["errors"].append(f"{rel}: switcher lists {[o['text'] for o in opts]}, expected {[c.data[a]['name'] for a in c.active]}")
            continue
        for a, o in zip(c.active, opts):
            if a == lg:
                if o["tag"] != "span" or "current" not in o["class"].split():
                    ck2["errors"].append(f"{rel}: {a} should be the current (unlinked) entry")
            else:
                target = resolve(f, o["href"] or "")
                if o["tag"] != "a" or target != file_of(a, page):
                    ck2["errors"].append(f"{rel}: switcher entry {a} points to {o['href']}, expected {file_of(a, page).relative_to(root)}")
                if o["hreflang"] != a:
                    ck2["errors"].append(f'{rel}: switcher entry {a} has hreflang="{o["hreflang"]}"')

    # ---- links and assets
    ck = R.check("every link, image, stylesheet and icon on every page resolves to a file")
    referenced = set()
    for f, info in infos.items():
        for ref in info.refs:
            t = resolve(f, ref)
            if t is None:
                continue
            if t in missing_pages:
                continue                                     # already reported as a missing page
            if not t.exists() or root not in t.parents:
                ck["errors"].append(f"{f.relative_to(root)}: {ref} -> {t.relative_to(root) if root in t.parents else t} does not exist")
            else:
                referenced.add(t)

    # ---- badges
    ck = R.check("every language shows its own App Store badge, stored in its images folder")
    for lg in c.langs:
        f = file_of(lg, "index")
        if f not in infos:
            continue
        badge = [i for i in infos[f].imgs if "download-cta-badge" in i.get("class", "").split()]
        if not badge:
            ck["errors"].append(f"{f.relative_to(root)}: no App Store badge found")
        want = S.images_dir(lg) / c.data[lg]["badge_file"]
        for img in badge:
            t = resolve(f, img["src"])
            if t == want:
                pass
            elif lg != default and t == S.images_dir(default) / c.data[default]["badge_file"] and c.data[lg]["badge_file"] == c.data[default]["badge_file"]:
                if lg not in opt["allow_default_badge"]:
                    ck["errors"].append(f"{lg}: uses the {default} badge; add its badge to {want.parent.relative_to(root)}/ and set badge_file "
                                        f"(or list {lg} under allow_default_badge in _src/verify.json)")
            else:
                ck["errors"].append(f"{f.relative_to(root)}: badge {img['src']} is not {want.relative_to(root)}")
            if t and t.exists():
                try:
                    if not ET.parse(t).getroot().tag.endswith("svg") or t.stat().st_size < 2048:
                        raise ValueError
                except (ET.ParseError, ValueError):
                    ck["errors"].append(f"{t.relative_to(root)}: not a valid badge SVG")

    # ---- screenshots
    ck = R.check("every language shows its own screenshots, stored in its images folder")
    ck_w = R.check("screenshots are valid webp files of the expected size")
    dims, digests = {}, {}
    for lg in c.langs:
        f = file_of(lg, "index")
        if f not in infos:
            continue
        names = set()
        for b in c.data[lg]["pages"]["index"]["blocks"]:
            names |= {s["name"] for s in b.get("screenshots", [])} | ({b["screenshot"]["name"]} if "screenshot" in b else set())
        got = {}
        for img in infos[f].imgs:
            if "app-screenshot" in img.get("class", "").split():
                got[resolve(f, img["src"])] = img["src"]
        for n in sorted(names):
            want = S.images_dir(lg) / f"{n}.webp"
            if want not in got:
                ck["errors"].append(f"{f.relative_to(root)}: screenshot {n} is not shown from {want.parent.relative_to(root)}/")
            if not want.exists():
                ck["errors"].append(f"{want.relative_to(root)}: missing")
                continue
            size = webp_size(want)
            if size is None:
                ck_w["errors"].append(f"{want.relative_to(root)}: not a valid webp image")
                continue
            if want.stat().st_size < 1024:
                ck_w["errors"].append(f"{want.relative_to(root)}: only {want.stat().st_size} bytes, probably empty or a placeholder")
                continue
            if size[0] != shots_opt["width"]:
                ck_w["errors"].append(f"{want.relative_to(root)}: width {size[0]} px, expected {shots_opt['width']}")
            dims[want] = size
            digests.setdefault((n, hashlib.sha1(want.read_bytes()).hexdigest()), []).append(lg)
        for t in got:
            if t not in {S.images_dir(lg) / f"{n}.webp" for n in names}:
                ck["errors"].append(f"{f.relative_to(root)}: shows {got[t]}, which is not one of this language's screenshots")
    ratios = sorted(h / w for w, h in dims.values())
    if ratios:
        med = ratios[len(ratios) // 2]
        for p, (w, h) in dims.items():
            if abs(h / w - med) / med > 0.015:
                ck_w["errors"].append(f"{p.relative_to(root)}: aspect ratio {w}x{h} differs from the other screenshots (different device?)")
    for (n, _), langs in digests.items():
        if len(langs) > 1:
            ck_w["warnings"].append(f"screenshot {n} is byte-identical in {', '.join(langs)} (not localized, wrong locale folder?)")

    # ---- English text left in other languages
    ck = R.check("pages of other languages are translated")
    for lg in c.langs:
        if lg == default:
            continue
        for page in pages:
            for k in ("title", "description"):
                if c.data[lg]["pages"][page][k] == c.data[default]["pages"][page][k]:
                    ck["errors"].append(f"{lg}: {page} {k} is identical to {default}")

    # ---- App Store URLs
    if c.all_langs:
        ck = R.check("the App Store URLs (support, marketing, privacy) lead to existing pages")
        meta = S.resolve(opt["metadata_dir"]) if opt["metadata_dir"] else None
        have = meta is not None and meta.is_dir()
        for loc, code in c.cfg.get("app_store_locales", {}).items():
            if code not in c.active:
                continue
            want = {"support_url.txt": (url(code, "contact"), file_of(code, "contact")),
                    "marketing_url.txt": (url(code, "index"), file_of(code, "index")),
                    "privacy_url.txt": (url(code, "privacy"), file_of(code, "privacy"))}
            for fn, (u, target) in want.items():
                if not target.exists():
                    ck["errors"].append(f"{loc}: {u} has no page {target.relative_to(root)}")
                if have:
                    got = (meta / loc / fn).read_text(encoding="utf-8").strip() if (meta / loc / fn).exists() else None
                    if got != u:
                        ck["errors"].append(f"metadata {loc}/{fn} is {got!r}, expected {u}")
        if have:
            extra = [d.name for d in meta.iterdir() if d.is_dir() and d.name != "review_information" and d.name not in c.cfg.get("app_store_locales", {})]
            ck["warnings"] += [f"metadata folder {e} is not in app_store_locales" for e in extra]
        else:
            ck["warnings"].append("metadata folder not found: the URL files of the App Store metadata were not compared "
                                  "(set metadata_dir in _src/verify.json)")

    # ---- hygiene
    ck = R.check("no unused or oversized files")
    pages_files = set(infos)
    for lg in c.langs:
        d = S.images_dir(lg)
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if f.is_file() and not f.name.startswith(".") and f not in referenced:
                    ck["warnings"].append(f"{f.relative_to(root)}: not used by any page")
    for t in sorted(referenced):
        if t.stat().st_size > opt["max_asset_kb"] * 1024:
            ck["warnings"].append(f"{t.relative_to(root)}: {t.stat().st_size // 1024} KB (limit {opt['max_asset_kb']} KB), slows down every first visit")

    # ---- git
    ck = R.check("everything that is shown can be uploaded (tracked by git, not ignored)")
    if (root / ".git").exists() and git(root, "rev-parse", "--is-inside-work-tree") is not None:
        site = {p.relative_to(root).as_posix() for p in referenced | pages_files}
        ignored = {l for l in (git(root, "ls-files", "--others", "--ignored", "--exclude-standard") or "").split("\n") if l}
        untracked = {l for l in (git(root, "ls-files", "--others", "--exclude-standard") or "").split("\n") if l}
        changed = {l for l in ((git(root, "diff", "--name-only") or "") + (git(root, "diff", "--cached", "--name-only") or "")).split("\n") if l}
        bad = sorted(site & ignored)
        if bad:
            ck["errors"].append(f"{len(bad)} shown file(s) are ignored by git and would not be uploaded: " + ", ".join(bad[:6]) + (" ..." if len(bad) > 6 else ""))
        pending_commit = sorted((site & untracked) | (site & changed))
        if pending_commit:
            ck["warnings"].append(f"{len(pending_commit)} shown file(s) are not committed yet and are uploaded only after `git add` and commit: "
                                  + ", ".join(pending_commit[:6]) + (" ..." if len(pending_commit) > 6 else ""))
    else:
        ck["warnings"].append("not a git repository: upload state not checked")

    print(f"verify: {len(c.langs)} language(s) ({', '.join(c.langs)}), {len(infos)} page(s)\n")
    return R.show()
