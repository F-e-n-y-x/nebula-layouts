#!/usr/bin/env python3
"""Validate Nebula layout files and (re)build index.json.

    tools/validate.py                 # check every layouts/**/*.json and index.json
    tools/validate.py --write-index   # also rewrite index.json from the layout files
    tools/validate.py path/to/one.json

Reads format versions 1 and 2 (2 adds layout sets, the layout switch element and chords; see
schema/nebula-layout-2.schema.json). Standard library only. The rules are the app's
(LayoutFile.parse in Nebula): the JSON Schemas in schema/ describe the same format; when the
`jsonschema` package is installed they are checked too.
Exit status 1 when anything fails.
"""
import hashlib
import json
import math
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_BYTES = 256 * 1024
MAX_ELEMENTS = 64
TOP_KEYS = {"$schema", "format", "version", "meta", "settings", "landscape", "portrait"}
SET_TOP_KEYS = {"$schema", "format", "version", "meta", "set", "layouts"}
LAYOUT_KEYS = {"id", "name", "settings", "landscape", "portrait"}
SET_KEYS = {"start", "cycle"}
MAX_LAYOUTS = 8
MAX_CHORD = 4
SWITCH_KEYS = {"id", "kind", "x", "y", "w", "h", "label", "opacity", "shape", "tint", "switchTo"}
SWITCH_TO = re.compile(r"^(next|previous|picker|layout:[a-z0-9][a-z0-9-]{0,31})$")
LAYOUT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
META_KEYS = {"name", "author", "game", "target", "device", "aspect", "description", "tags"}
GAME_KEYS = {"name", "steamAppId"}
SETTINGS = {"outside": {"look", "nothing", "trackpad", "direct"}, "look": {"mouse", "stick"}}
ELEMENT_KEYS = {
    "id", "kind", "x", "y", "w", "h", "label", "opacity", "mode", "shape", "bindings", "stick", "click", "floating",
    "deadzone", "sensitivity", "steps", "tint", "zone", "acceleration", "invertY", "showRing", "keepWithController",
    "lookThrough", "antiDeadzone", "sprint", "sprintAt", "runLock", "role",
}
KINDS = {"button", "dpad", "stick", "trigger", "touchpad", "combo", "macro", "zone"}
KINDS_V2 = KINDS | {"switch"}
ENUMS = {
    "mode": {"hold", "toggle", "mixed"},
    "shape": {"round", "pill", "square"},
    "stick": {"left", "right", "keys"},
    "zone": {"camera_stick", "camera_mouse", "floating_stick"},
    "role": {"none", "fire", "ads", "move", "sprint", "jump", "crouch", "prone", "reload", "switch", "interact",
             "peek_left", "peek_right", "free_look", "menu"},
}
RANGES = {"opacity": (0.1, 1), "deadzone": (0, 0.9), "sensitivity": (0.1, 5), "acceleration": (0.5, 2.5),
          "antiDeadzone": (0, 0.45), "sprintAt": (1, 2)}
BOOLS = {"floating", "invertY", "showRing", "keepWithController", "lookThrough", "runLock"}
PAD_FLAGS = {0x1, 0x2, 0x4, 0x8, 0x10, 0x20, 0x40, 0x80, 0x100, 0x200, 0x400, 0x1000, 0x2000, 0x4000, 0x8000,
             0x10000, 0x20000, 0x40000, 0x80000, 0x100000, 0x200000}
MOUSE = {"left", "middle", "right", "back", "forward"}
ID = re.compile(r"^[A-Za-z0-9_.:-]{1,40}$")
TAG = re.compile(r"^[a-z0-9][a-z0-9-]{0,23}$")
PATH = re.compile(r"^layouts/[a-z0-9][a-z0-9-]{0,47}/[a-z0-9][a-z0-9.-]{0,63}\.json$")
BAD_CHARS = re.compile("[\u0000-\u001f\u007f‭‮]")


class Invalid(Exception):
    pass


def num(v, path, lo, hi):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise Invalid(f"{path}: must be a number")
    if v < lo or v > hi:
        raise Invalid(f"{path}: must be between {lo} and {hi}")
    return v


def text(o, key, path, max_len, required=False, multiline=False):
    if key not in o:
        if required:
            raise Invalid(f"{path}: missing")
        return ""
    s = o[key]
    if not isinstance(s, str):
        raise Invalid(f"{path}: must be text")
    if required and not s.strip():
        raise Invalid(f"{path}: missing")
    if len(s) > max_len:
        raise Invalid(f"{path}: at most {max_len} characters")
    chk = s.replace("\n", "") if multiline else s
    if BAD_CHARS.search(chk):
        raise Invalid(f"{path}: has control characters")
    return s


def keys(o, allowed, where):
    bad = [k for k in o if k not in allowed]
    if bad:
        raise Invalid(f"{where}: unknown field(s) {bad[:3]}")


def parse_int(s):
    return int(s[2:], 16) if s.startswith("0x") else int(s)


def binding(v, path, version=1):
    if not isinstance(v, str):
        raise Invalid(f"{path}: must be text")
    t = v.strip().lower()
    if "+" in t:
        # Version 2 chord: 2-4 different bindings pressed together, e.g. key:0x10+key:0x45 (Shift+E).
        if version < 2:
            raise Invalid(f"{path}: chords ({v!r}) need \"version\": 2")
        parts = t.split("+")
        if not 2 <= len(parts) <= MAX_CHORD:
            raise Invalid(f"{path}: a chord joins 2 to {MAX_CHORD} bindings")
        for i, part in enumerate(parts):
            if part == "none":
                raise Invalid(f"{path}: a chord can't contain none")
            one(part, v, path)
        if len({canonical(x) for x in parts}) != len(parts):
            raise Invalid(f"{path}: a chord presses each binding once")
        return
    one(t, v, path)


def canonical(t):
    head, _, arg = t.partition(":")
    if head in ("pad", "key"):
        return f"{head}:{parse_int(arg)}"
    return t


def one(t, v, path):
    head, _, arg = t.partition(":")
    ok = False
    try:
        if t in ("none", "lt", "rt", "wheel:up", "wheel:down"):
            ok = True
        elif head == "pad":
            ok = parse_int(arg) in PAD_FLAGS
        elif head == "key":
            ok = 1 <= parse_int(arg) <= 0xFE
        elif head == "mouse":
            ok = arg in MOUSE
    except ValueError:
        ok = False
    if not ok:
        raise Invalid(f"{path}: unknown binding {v!r}")


def meta_of(m, where="meta"):
    if not isinstance(m, dict):
        raise Invalid(f"{where}: must be an object")
    keys(m, META_KEYS, where)
    text(m, "name", f"{where}.name", 60, required=True)
    text(m, "author", f"{where}.author", 40)
    text(m, "description", f"{where}.description", 500, multiline=True)
    if "game" in m:
        g = m["game"]
        if not isinstance(g, dict):
            raise Invalid(f"{where}.game: must be an object")
        keys(g, GAME_KEYS, f"{where}.game")
        text(g, "name", f"{where}.game.name", 80, required=True)
        if "steamAppId" in g and (isinstance(g["steamAppId"], bool) or not isinstance(g["steamAppId"], int) or not 1 <= g["steamAppId"] <= 99999999):
            raise Invalid(f"{where}.game.steamAppId: a whole number from 1 to 99999999")
    if "target" in m and m["target"] not in ("xinput", "kbm", "mixed"):
        raise Invalid(f"{where}.target: unknown value")
    if "device" in m and m["device"] not in ("phone", "tablet", "any"):
        raise Invalid(f"{where}.device: unknown value")
    if "aspect" in m:
        num(m["aspect"], f"{where}.aspect", 0.3, 4)
    if "tags" in m:
        t = m["tags"]
        if not isinstance(t, list) or len(t) > 8 or not all(isinstance(x, str) and TAG.match(x) for x in t):
            raise Invalid(f"{where}.tags: up to 8 lower-case tags")


def element(o, p, version=1, layout_ids=None):
    """layout_ids: the set's layout ids (a set file), or None (a single layout)."""
    if not isinstance(o, dict):
        raise Invalid(f"{p}: must be an object")
    kind = o.get("kind")
    if o.get("kind") == "switch" and version >= 2:
        keys(o, SWITCH_KEYS, p)
    else:
        keys(o, ELEMENT_KEYS, p)
    if not isinstance(o.get("id"), str) or not ID.match(o["id"]):
        raise Invalid(f"{p}.id: letters, digits and _ . : - only, up to 40")
    if kind not in (KINDS_V2 if version >= 2 else KINDS):
        raise Invalid(f"{p}.kind: unknown control {kind!r}" + (' (switch elements need "version": 2)' if kind == "switch" else ""))
    if kind == "switch" and "switchTo" in o:
        t = o["switchTo"]
        if not isinstance(t, str) or not SWITCH_TO.match(t):
            raise Invalid(f"{p}.switchTo: next, previous, picker or layout:<layout id>")
        if t.startswith("layout:"):
            if layout_ids is None:
                raise Invalid(f"{p}.switchTo: {t!r} names a layout, but this file is a single layout, not a set")
            if t[7:] not in layout_ids:
                raise Invalid(f"{p}.switchTo: no layout {t[7:]!r} in this set")
    for k in ("x", "y"):
        if k not in o:
            raise Invalid(f"{p}.{k}: missing")
        num(o[k], f"{p}.{k}", 0, 1)
    lo, hi = (0.08, 1) if kind == "zone" else (28, 360)
    for k in ("w", "h"):
        if k not in o:
            raise Invalid(f"{p}.{k}: missing")
        num(o[k], f"{p}.{k}", lo, hi)
    text(o, "label", f"{p}.label", 24)
    for k, allowed in ENUMS.items():
        if k in o and o[k] not in allowed:
            raise Invalid(f"{p}.{k}: unknown value {o[k]!r}")
    for k, (a, b) in RANGES.items():
        if k in o:
            num(o[k], f"{p}.{k}", a, b)
    for k in BOOLS:
        if k in o and not isinstance(o[k], bool):
            raise Invalid(f"{p}.{k}: must be true or false")
    if "bindings" in o:
        b = o["bindings"]
        mx = 5 if kind == "combo" else 4
        if not isinstance(b, list) or len(b) > mx:
            raise Invalid(f"{p}.bindings: a list of at most {mx}")
        for i, x in enumerate(b):
            binding(x, f"{p}.bindings[{i}]", version)
    for k in ("click", "sprint"):
        if k in o:
            binding(o[k], f"{p}.{k}", version)
    if "tint" in o and not (isinstance(o["tint"], str) and re.match(r"^#[0-9A-Fa-f]{8}$", o["tint"])):
        raise Invalid(f"{p}.tint: must look like #AARRGGBB")
    if "steps" in o:
        st = o["steps"]
        if not isinstance(st, list) or len(st) > 16:
            raise Invalid(f"{p}.steps: a list of at most 16")
        total = 0
        for i, s in enumerate(st):
            if not isinstance(s, dict):
                raise Invalid(f"{p}.steps[{i}]: must be an object")
            keys(s, {"binding", "holdMs", "gapMs"}, f"{p}.steps[{i}]")
            if "binding" not in s:
                raise Invalid(f"{p}.steps[{i}].binding: missing")
            binding(s["binding"], f"{p}.steps[{i}].binding", version)
            total += num(s.get("holdMs", 60), f"{p}.steps[{i}].holdMs", 10, 5000)
            total += num(s.get("gapMs", 40), f"{p}.steps[{i}].gapMs", 0, 5000)
        if total > 20000:
            raise Invalid(f"{p}.steps: a macro may last at most 20 seconds")


def elements(v, path, required, version=1, layout_ids=None):
    if v is None:
        if required:
            raise Invalid(f"{path}: missing")
        return []
    if not isinstance(v, list):
        raise Invalid(f"{path}: must be a list")
    if required and not v:
        raise Invalid(f"{path}: the layout has no controls")
    if len(v) > MAX_ELEMENTS:
        raise Invalid(f"{path}: at most {MAX_ELEMENTS} controls")
    ids = set()
    for i, e in enumerate(v):
        element(e, f"{path}[{i}]", version, layout_ids)
        if e["id"] in ids:
            raise Invalid(f"{path}[{i}].id: {e['id']!r} is used twice")
        ids.add(e["id"])
    return v


def validate_layout(raw: bytes):
    if len(raw) > MAX_BYTES:
        raise Invalid(f"larger than {MAX_BYTES // 1024} KB")
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise Invalid(f"not valid JSON: {e}")
    if not isinstance(doc, dict):
        raise Invalid("not a JSON object")
    if doc.get("format") != "nebula-layout":
        raise Invalid('"format" must be "nebula-layout"')
    version = doc.get("version")
    if isinstance(version, bool) or version not in (1, 2):
        raise Invalid('"version" must be 1 or 2')
    if version >= 2 and "layouts" in doc:
        return validate_set(doc)
    keys(doc, TOP_KEYS, "the file")
    if "meta" not in doc:
        raise Invalid("meta: missing")
    meta_of(doc["meta"])
    if "settings" in doc:
        settings_of(doc["settings"], "settings")
    elements(doc.get("landscape"), "landscape", True, version)
    elements(doc.get("portrait"), "portrait", False, version)
    return doc


def settings_of(s, where):
    if not isinstance(s, dict):
        raise Invalid(f"{where}: must be an object")
    keys(s, set(SETTINGS), where)
    for k, allowed in SETTINGS.items():
        if k in s and s[k] not in allowed:
            raise Invalid(f"{where}.{k}: unknown value")


def validate_set(doc):
    """Version 2 set: several layouts for one game, an optional cycle order and start layout."""
    bad_top = [k for k in ("settings", "landscape", "portrait") if k in doc]
    if bad_top:
        raise Invalid(f"a set file has no top-level {bad_top[0]!r}; each layout has its own")
    keys(doc, SET_TOP_KEYS, "the file")
    if "meta" not in doc:
        raise Invalid("meta: missing")
    meta_of(doc["meta"])
    ls = doc["layouts"]
    if not isinstance(ls, list) or not ls:
        raise Invalid("layouts: a list of 1 or more layouts")
    if len(ls) > MAX_LAYOUTS:
        raise Invalid(f"layouts: at most {MAX_LAYOUTS}")
    ids, names = [], set()
    for i, l in enumerate(ls):
        p = f"layouts[{i}]"
        if not isinstance(l, dict):
            raise Invalid(f"{p}: must be an object")
        keys(l, LAYOUT_KEYS, p)
        lid = l.get("id")
        if not isinstance(lid, str) or not LAYOUT_ID.match(lid):
            raise Invalid(f"{p}.id: lower-case letters, digits and -, up to 32")
        if lid in ids:
            raise Invalid(f"{p}.id: {lid!r} is used twice")
        ids.append(lid)
        name = text(l, "name", f"{p}.name", 24, required=True)
        if name.strip().lower() in names:
            raise Invalid(f"{p}.name: {name!r} is used twice")
        names.add(name.strip().lower())
    for i, l in enumerate(ls):
        p = f"layouts[{i}]"
        if "settings" in l:
            settings_of(l["settings"], f"{p}.settings")
        elements(l.get("landscape"), f"{p}.landscape", True, 2, set(ids))
        elements(l.get("portrait"), f"{p}.portrait", False, 2, set(ids))
    if "set" in doc:
        st = doc["set"]
        if not isinstance(st, dict):
            raise Invalid("set: must be an object")
        keys(st, SET_KEYS, "set")
        if "start" in st and st["start"] not in ids:
            raise Invalid(f"set.start: no layout {st['start']!r}")
        if "cycle" in st:
            c = st["cycle"]
            if not isinstance(c, list) or not 1 <= len(c) <= MAX_LAYOUTS:
                raise Invalid(f"set.cycle: a list of 1 to {MAX_LAYOUTS} layout ids")
            for j, x in enumerate(c):
                if x not in ids:
                    raise Invalid(f"set.cycle[{j}]: no layout {x!r}")
            if len(set(c)) != len(c):
                raise Invalid("set.cycle: each layout once")
    return doc


def start_layout(doc):
    """The layout a set starts on (the file itself for a single layout)."""
    if "layouts" not in doc:
        return doc
    start = doc.get("set", {}).get("start")
    return next((l for l in doc["layouts"] if l["id"] == start), doc["layouts"][0])


def schema_check(doc, path):
    try:
        import jsonschema  # optional
    except ImportError:
        return
    with open(os.path.join(ROOT, "schema", f"nebula-layout-{doc.get('version', 1)}.schema.json")) as f:
        jsonschema.validate(doc, json.load(f))


def entry_for(rel, raw, doc):
    m = doc["meta"]
    game_dir, name = rel.split("/")[1], os.path.splitext(rel.split("/")[2])[0]
    e = {"id": f"{game_dir}/{name}"}
    for k in ("name", "author", "game", "target", "device", "aspect", "description", "tags"):
        if k in m:
            e[k] = m[k]
    e["path"] = rel
    e["size"] = len(raw)
    e["sha256"] = hashlib.sha256(raw).hexdigest()
    start = start_layout(doc)
    e["controls"] = len(start["landscape"])
    # The thumbnail the app draws before downloading: kind, centre, size (zones: shares; else dp), shape.
    # A set shows its start layout.
    e["preview"] = [[el["kind"], el["x"], el["y"], el["w"], el["h"], el.get("shape", "round")] for el in start["landscape"]]
    if doc["version"] >= 2:
        e["version"] = doc["version"]
    if "layouts" in doc:
        e["layouts"] = [l["name"] for l in doc["layouts"]]
    return e


def main(argv):
    write = "--write-index" in argv
    files = [a for a in argv if not a.startswith("--")]
    failed = 0
    if files:
        for f in files:
            try:
                with open(f, "rb") as fh:
                    doc = validate_layout(fh.read())
                schema_check(doc, f)
                print(f"ok    {f}")
            except Exception as e:  # noqa: BLE001 - report every failure
                failed += 1
                print(f"FAIL  {f}: {e}")
        return 1 if failed else 0

    entries = []
    for d, _, names in sorted(os.walk(os.path.join(ROOT, "layouts"))):
        for n in sorted(names):
            if not n.endswith(".json"):
                continue
            full = os.path.join(d, n)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            try:
                if not PATH.match(rel):
                    raise Invalid("path must be layouts/<game>/<name>.json in lower case (a-z, 0-9, -)")
                with open(full, "rb") as fh:
                    raw = fh.read()
                doc = validate_layout(raw)
                schema_check(doc, rel)
                entries.append(entry_for(rel, raw, doc))
                print(f"ok    {rel}")
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"FAIL  {rel}: {e}")
    ids = [e["id"] for e in entries]
    if len(ids) != len(set(ids)):
        failed += 1
        print("FAIL  duplicate layout ids")
    index_path = os.path.join(ROOT, "index.json")
    if write and not failed:
        # Generic layouts first, then by game and name.
        entries.sort(key=lambda e: (e["id"].split("/")[0] != "generic", e["id"]))
        index = {"format": "nebula-layout-index", "version": 1, "updated": date.today().isoformat(), "layouts": entries}
        with open(index_path, "w") as fh:
            json.dump(index, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"wrote index.json ({len(entries)} layouts)")
    elif os.path.exists(index_path):
        with open(index_path) as fh:
            index = json.load(fh)
        listed = {e["path"]: e for e in index.get("layouts", [])}
        for e in entries:
            if e["path"] not in listed:
                failed += 1
                print(f"FAIL  index.json doesn't list {e['path']} (run with --write-index)")
            elif listed[e["path"]].get("sha256") != e["sha256"]:
                failed += 1
                print(f"FAIL  index.json checksum for {e['path']} is stale (run with --write-index)")
        for p in listed:
            if p not in {e["path"] for e in entries}:
                failed += 1
                print(f"FAIL  index.json lists a missing file {p}")
    print("all good" if not failed else f"{failed} problem(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
