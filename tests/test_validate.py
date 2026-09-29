#!/usr/bin/env python3
"""Tests for tools/validate.py (format versions 1 and 2). Run: python3 -m unittest discover tests"""
import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import validate  # noqa: E402

BTN = {"id": "a", "kind": "button", "x": 0.8, "y": 0.8, "w": 56, "h": 56, "bindings": ["pad:4096"]}
SET = {
    "format": "nebula-layout",
    "version": 2,
    "meta": {"name": "Test set", "target": "mixed"},
    "set": {"start": "foot", "cycle": ["foot", "car"]},
    "layouts": [
        {"id": "foot", "name": "On foot", "settings": {"outside": "look", "look": "mouse"},
         "landscape": [BTN, {"id": "sw", "kind": "switch", "x": 0.5, "y": 0.06, "w": 88, "h": 34, "shape": "pill"}]},
        {"id": "car", "name": "Vehicle",
         "landscape": [{"id": "horn", "kind": "button", "x": 0.2, "y": 0.8, "w": 56, "h": 56, "bindings": ["key:0x10", "key:0x45"]},
                       {"id": "go", "kind": "switch", "x": 0.5, "y": 0.06, "w": 88, "h": 34, "switchTo": "layout:plane"}]},
        {"id": "plane", "name": "Aircraft",
         "landscape": [{"id": "d", "kind": "dpad", "x": 0.2, "y": 0.7, "w": 128, "h": 128,
                        "bindings": ["key:0x57", "key:0x53+key:0x10", "key:0x41", "key:0x44"]},
                       {"id": "pick", "kind": "switch", "x": 0.5, "y": 0.06, "w": 88, "h": 34, "switchTo": "picker"}]},
    ],
}


def raw(d):
    return json.dumps(d).encode()


class V1(unittest.TestCase):
    def test_library_files_still_pass(self):
        for d, _, names in os.walk(os.path.join(validate.ROOT, "layouts")):
            for n in names:
                with open(os.path.join(d, n), "rb") as f:
                    validate.validate_layout(f.read())

    def test_v1_refuses_chords_and_switches(self):
        doc = {"format": "nebula-layout", "version": 1, "meta": {"name": "x"},
               "landscape": [dict(BTN, bindings=["pad:256+pad:512"])]}
        with self.assertRaisesRegex(validate.Invalid, "version\": 2"):
            validate.validate_layout(raw(doc))
        doc["landscape"] = [{"id": "s", "kind": "switch", "x": 0.5, "y": 0.5, "w": 60, "h": 40}]
        with self.assertRaisesRegex(validate.Invalid, "unknown control"):
            validate.validate_layout(raw(doc))


class V2(unittest.TestCase):
    def test_set_passes(self):
        validate.validate_layout(raw(SET))

    def test_single_layout_v2(self):
        doc = {"format": "nebula-layout", "version": 2, "meta": {"name": "x"},
               "landscape": [dict(BTN, bindings=["pad:256+pad:512"]), {"id": "s", "kind": "switch", "x": 0.5, "y": 0.5, "w": 60, "h": 40, "switchTo": "next"}]}
        validate.validate_layout(raw(doc))
        doc["landscape"][1]["switchTo"] = "layout:foot"
        with self.assertRaisesRegex(validate.Invalid, "single layout"):
            validate.validate_layout(raw(doc))

    def bad(self, change, msg):
        d = copy.deepcopy(SET)
        change(d)
        with self.assertRaisesRegex(validate.Invalid, msg):
            validate.validate_layout(raw(d))

    def test_rejections(self):
        self.bad(lambda d: d.update(landscape=[BTN]), "no top-level")
        self.bad(lambda d: d["layouts"].append(copy.deepcopy(d["layouts"][0])), "used twice")
        self.bad(lambda d: d["layouts"][1].update(name="on FOOT"), "used twice")
        self.bad(lambda d: d["layouts"][1].update(id="Car"), "lower-case")
        self.bad(lambda d: d["set"].update(start="boat"), "no layout 'boat'")
        self.bad(lambda d: d["set"].update(cycle=["foot", "foot"]), "each layout once")
        self.bad(lambda d: d["set"].update(order=[]), "unknown field")
        self.bad(lambda d: d["layouts"][1]["landscape"][1].update(switchTo="layout:boat"), "no layout 'boat'")
        self.bad(lambda d: d["layouts"][0]["landscape"][1].update(switchTo="first"), "next, previous")
        self.bad(lambda d: d["layouts"][0]["landscape"][1].update(bindings=["pad:4096"]), "unknown field")
        self.bad(lambda d: d["layouts"][0]["landscape"][0].update(switchTo="next"), "unknown field")
        self.bad(lambda d: d["layouts"][0]["landscape"][0].update(bindings=["key:0x10+none"]), "none")
        self.bad(lambda d: d["layouts"][0]["landscape"][0].update(bindings=["key:0x10+key:16"]), "once")
        self.bad(lambda d: d["layouts"][0]["landscape"][0].update(bindings=["lt+rt+key:1+key:2+key:3"]), "2 to 4")
        self.bad(lambda d: d["layouts"][0]["landscape"][0].update(bindings=["pad:3+key:1"]), "unknown binding")
        self.bad(lambda d: d.update(layouts=[copy.deepcopy(SET["layouts"][0]) | {"id": f"l{i}", "name": f"L{i}"} for i in range(9)]), "at most 8")
        self.bad(lambda d: d["layouts"][2].pop("landscape"), "missing")

    def test_index_entry_for_set(self):
        e = validate.entry_for("layouts/test/set.json", raw(SET), SET)
        self.assertEqual(e["layouts"], ["On foot", "Vehicle", "Aircraft"])
        self.assertEqual(e["version"], 2)
        self.assertEqual(e["controls"], 2)
        d = copy.deepcopy(SET)
        d["set"]["start"] = "plane"
        self.assertEqual(validate.entry_for("layouts/test/set.json", raw(d), d)["preview"][0][0], "dpad")


if __name__ == "__main__":
    unittest.main()
