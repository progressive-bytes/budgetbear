"""Content validation: a small JSON Schema subset validator plus cross-language structure checks."""
import json, re

PY_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool}


class Validator:
    def __init__(self, schema):
        self.schema = schema
        self.errors = []

    def resolve(self, s):
        while "$ref" in s:
            name = s["$ref"].rsplit("/", 1)[-1]
            extra = {k: v for k, v in s.items() if k != "$ref"}
            s = {**self.schema["$defs"][name], **extra}
        return s

    def err(self, path, msg):
        self.errors.append(f"{path or '(file)'}: {msg}")

    def check(self, inst, schema, path=""):
        schema = self.resolve(schema)
        if "oneOf" in schema:
            return self.check_union(inst, schema, path)
        t = schema.get("type")
        if t and (not isinstance(inst, PY_TYPES[t]) or (t != "boolean" and isinstance(inst, bool))):
            return self.err(path, f"expected {t}, found {type(inst).__name__}")
        if "const" in schema and inst != schema["const"]:
            return self.err(path, f"must be {schema['const']!r}")
        if "enum" in schema and inst not in schema["enum"]:
            return self.err(path, f"must be one of {schema['enum']}, found {inst!r}")
        if t == "string":
            if len(inst) < schema.get("minLength", 0):
                self.err(path, "must not be empty")
            if "pattern" in schema and not re.search(schema["pattern"], inst):
                self.err(path, f"{inst!r} does not match {schema['pattern']}")
            if schema.get("x-inline"):
                for problem in inline_problems(inst):
                    self.err(path, problem)
            elif inst != inst.strip() or "\n" in inst:
                self.err(path, "must not have leading/trailing spaces or line breaks")
        elif t == "array":
            if len(inst) < schema.get("minItems", 0):
                self.err(path, f"needs at least {schema['minItems']} item(s)")
            if len(inst) > schema.get("maxItems", 10**9):
                self.err(path, f"allows at most {schema['maxItems']} item(s)")
            for i, item in enumerate(inst):
                self.check(item, schema["items"], f"{path}[{i}]")
        elif t == "object":
            props = schema.get("properties", {})
            for key in schema.get("required", []):
                if key not in inst:
                    self.err(path, f'missing "{key}"')
            for key, val in inst.items():
                if key in props:
                    self.check(val, props[key], f"{path}.{key}" if path else key)
                elif schema.get("additionalProperties") is False:
                    self.err(path, f'unknown key "{key}" (allowed: {", ".join(props)})')

    def check_union(self, inst, schema, path):
        branches = [self.resolve(b) for b in schema["oneOf"]]
        consts = {b["properties"]["type"]["const"]: b for b in branches}
        if not isinstance(inst, dict):
            return self.err(path, f"expected object, found {type(inst).__name__}")
        kind = inst.get("type")
        if kind not in consts:
            return self.err(path, f'"type" must be one of: {", ".join(consts)} (found {kind!r})')
        self.check(inst, consts[kind], path)


def inline_problems(s):
    out = []
    if s != s.strip() or "\n" in s:
        out.append("must not have leading/trailing spaces or line breaks")
    if re.search(r"[<>]", s):
        out.append("contains < or >; HTML is not allowed (use **bold** and [text](https://url))")
    if re.search(r"&[A-Za-z#0-9]+;", s):
        out.append("contains an HTML entity; write the character itself (e.g. & not &amp;)")
    if s.count("**") % 2:
        out.append("unbalanced ** (bold)")
    if "****" in s:
        out.append("empty bold text")
    rest = s
    for m in re.finditer(r"\[([^\]]*)\]\(([^)]*)\)", s):
        if not m.group(2).startswith("https://"):
            out.append(f"link URL must start with https:// ({m.group(2)!r})")
        if not m.group(1).strip():
            out.append("link without text")
        rest = rest.replace(m.group(0), "")
    if re.search(r"[\[\]]", rest):
        out.append("stray [ or ]; links must look like [text](https://url)")
    if re.search(r"[{}]", rest.replace("{site_link}", "")):
        out.append("unknown {placeholder}; only {site_link} is allowed")
    return out


def signature(block):
    """Everything about a block that must be identical in all languages (i.e. all but the wording)."""
    t = block["type"]
    if t == "hero":
        return f'hero shots={[s["name"] for s in block.get("screenshots", [])]} subtitle={"subtitle" in block}'
    if t == "section":
        els = ", ".join(f'list({len(e["items"])})' if e["type"] == "list" else e["type"] for e in block["content"])
        return f'section heading={"heading" in block} divider={block.get("divider", True)} [{els}]'
    if t == "feature":
        return f'feature reverse={block.get("reverse", False)} shot={block["screenshot"]["name"]} items={len(block["items"])}'
    if t == "trust":
        return f'trust variant={block.get("variant", "default")} emphasis={"emphasis" in block} paragraphs={len(block["paragraphs"])}'
    return t


def structure_problems(lang, data, default_lang, default_data):
    out = []
    for page, ref_page in default_data["pages"].items():
        mine = data["pages"].get(page)
        if mine is None:
            continue
        a, b = ref_page["blocks"], mine["blocks"]
        where = f"{lang}: pages.{page}.blocks"
        if len(a) != len(b):
            out.append(f"{where}: {len(b)} blocks, but {default_lang} has {len(a)}")
        ids = [x.get("id") for x in b]
        for dup in sorted({i for i in ids if ids.count(i) > 1}):
            out.append(f'{where}: duplicate id "{dup}"')
        for i, (x, y) in enumerate(zip(a, b)):
            if x["id"] != y.get("id"):
                out.append(f'{where}[{i}]: id "{y.get("id")}" should be "{x["id"]}" (same as {default_lang})')
            elif signature(x) != signature(y):
                out.append(f'{where}[{i}] (id "{x["id"]}"): structure differs from {default_lang}\n'
                           f'      {default_lang}: {signature(x)}\n      {lang}: {signature(y)}')
    return out


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as e:
        return None, f"{path.name}: invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}"
    except FileNotFoundError:
        return None, f"{path.name}: file not found"
