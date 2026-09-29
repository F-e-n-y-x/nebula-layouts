# Nebula layouts

Community on-screen control layouts for [Nebula](https://github.com/F-e-n-y-x/nebula), the Android
game-streaming client for [Nova](https://github.com/F-e-n-y-x/nova-host). Stream a PC game to a
phone or tablet, pick a layout made for that game (or for its genre) and play it with touch
alone, or together with a controller.

In Nebula: **Edit controls → Profiles → Browse layouts**. The app reads `index.json`, shows each
layout's preview, and downloads a layout only when you pick it.

## What's here

```
layouts/<game>/<name>.json          layouts made for one game        (layouts/gta-v/…)
layouts/genre-<genre>/<name>.json   templates for any game of a genre (layouts/genre-shooter/…)
index.json                          generated list of every layout: name, game, tags, checksum, preview
schema/nebula-layout-1.schema.json  JSON Schema of a version 1 layout file
schema/nebula-layout-2.schema.json  JSON Schema of a version 2 file (layout sets, switch element, chords)
tools/validate.py                   validator and index builder (Python 3, standard library only)
tests/                              validator tests (python3 -m unittest discover tests)
```

- **Game layouts** are tuned to one game's own controls and name it in `game`
  (with its Steam app id when there is one). Folder: the game's lower-case slug, e.g. `gta-v`,
  `elden-ring`, `forza-horizon-5`.
- **Genre templates** have no `game` and work as a starting point for any game of that kind.
  Genres: `shooter`, `racing`, `action-adventure`, `platformer`, `fighting`, `sports`, `rpg`,
  `strategy`, `desktop`. A new genre folder is fine when none of these fit.

### Naming

`<Game or genre> · <what makes it different>`, describing the controls, not other games:
"GTA V · touch controls", "Touch shooter · keyboard & mouse", "Forza Horizon 5 · tilt steering",
"Elden Ring · controller + touch camera".

### Tags

Tags make search work across games. Use a few of:

| Kind | Tags |
|---|---|
| Genre | `shooter`, `racing`, `action-adventure`, `platformer`, `fighting`, `sports`, `rpg`, `strategy`, `desktop` |
| View | `first-person`, `third-person`, `top-down`, `side-view` |
| Input sent | `controller`, `keyboard-mouse`, `mixed` |
| How it's played | `touch-only`, `with-controller`, `gyro`, `one-hand` |

### Starter layouts

| Layout | For |
|---|---|
| Touch shooter · controller | Any shooter that uses a controller: floating move stick with sprint and run-lock, look anywhere on the right, fire on both sides (the right one aims while dragged), aim, jump, crouch/prone, reload, lean |
| Touch shooter · keyboard & mouse | The same scheme for games played with keyboard and mouse (the stick is WASD, mouse look) |
| GTA V · touch controls | Grand Theft Auto V on its own controller map, on foot and in vehicles |

## The format

```json
{
  "format": "nebula-layout",
  "version": 1,
  "meta": {
    "name": "GTA V · touch controls",
    "author": "Nebula",
    "game": { "name": "Grand Theft Auto V", "steamAppId": 271590 },
    "target": "xinput",
    "device": "phone",
    "aspect": 2.17,
    "description": "…",
    "tags": ["action-adventure", "third-person", "controller", "touch-only"]
  },
  "settings": { "outside": "look", "look": "mouse" },
  "landscape": [ { "id": "fire", "kind": "trigger", "x": 0.8, "y": 0.55, "w": 80, "h": 80, "bindings": ["rt"], "lookThrough": true } ],
  "portrait": [ … ]
}
```

- `x`, `y` are the element's centre as a share (0–1) of the controls area, so layouts carry across
  screens. `w`, `h` are dp for controls (28–360) and a share of the area for zones. Nebula scales
  the dp sizes to the device ("Fit to this screen").
- `target`: `xinput` (gamepad), `kbm` (keyboard and mouse) or `mixed`. `device`: `phone`, `tablet`
  or `any`. `aspect`: the landscape area's width / height it was made on.
- Bindings are names only: `pad:<flag>` (A = 4096, B = 8192, X = 16384, Y = 32768, LB = 256,
  RB = 512, L3 = 64, R3 = 128, Start = 16, Back = 32, D-pad 1/2/4/8), `lt`, `rt`,
  `key:<Windows virtual-key code>`, `mouse:left|right|middle|back|forward`, `wheel:up|down`, `none`.
- Fields at their default may be left out. Anything unknown is an error.

### Version 2: layout sets, the switch element and chords

Nebula 0.4 also reads `"version": 2`, which adds:

- **Layout sets**: one file with several layouts for one game, e.g. On foot / Vehicle / Aircraft.
  Instead of top-level `settings`/`landscape`/`portrait`, a set has
  `"layouts": [{ "id": "on-foot", "name": "On foot", "settings": {…}, "landscape": […], "portrait": […] }, …]`
  (1–8 layouts) and an optional `"set": { "start": "on-foot", "cycle": ["on-foot", "vehicle"] }`.
- **The layout switch** element: `{ "kind": "switch", "switchTo": "next" }` (or `previous`, `picker`,
  `layout:<id>`). It is placed like a button, never sends anything to the PC, and releases every
  held input before the next layout appears.
- **Chords**: any binding may join 2–4 bindings with `+`, e.g. `key:0x10+key:0x45` (Shift+E),
  `pad:256+pad:512` (LB+RB), `key:0x11+mouse:left`. Allowed in D-pad directions, `click`, `sprint`
  and macro steps as well as button bindings.
- **Editor groups**: an optional `"group": "abxy:e-3f9a1c2d"` on elements placed together from a
  ready-made group (ABXY, WASD…), so the editor keeps moving them as one. Play ignores it.

Use version 1 when a layout needs none of these, so older Nebula can read it. The full
description is `schema/nebula-layout-2.schema.json`; index entries of sets list their layouts'
names in `layouts` and preview the start layout.

The easiest way to make one is Nebula itself: edit the controls, then **Profiles → Share → Save
file**, or **Share to library**, which fills in a GitHub page for you.

## Submitting a layout

1. Play with it first. A layout goes in only if its author has used it in that game (or, for a
   genre template, in a few games of that genre).
2. Put the file in `layouts/<game>/` or `layouts/genre-<genre>/`, one layout per pull request.
3. Run `python3 tools/validate.py --write-index` and commit `index.json` with the layout.
4. Open a pull request with a screenshot of the layout (Nebula's **Share to library** saves one)
   and a line on how it plays: how many fingers, and which in-game settings it expects.

Or use Nebula's **Share to library → Open an issue**: it fills in the JSON, and a maintainer adds it.

## Review rules

A layout is merged when:

- `tools/validate.py` passes (it runs on every pull request) and `index.json` is regenerated;
- its name and tags follow the conventions above, and `game` names the real game (genre templates
  have no `game`);
- `target` matches the bindings, and the description says which in-game controls it expects;
- it isn't a near-copy of an existing layout (improve that one instead);
- labels and descriptions are plain, polite English, with no links, ads or personal data;
- it only presses buttons: no macros longer than a few seconds, and no key sequences that open
  programs or type text (Win+R, Alt+F4, Ctrl+Alt+Del and similar are refused).

Layouts are data, never code. Nebula checks every download again (size cap, known fields and
values only, the checksum from `index.json`) before it shows a preview, and nothing is saved until
you tap **Add**.

## License

Layouts in this repository are released under [CC0 1.0](LICENSE): anyone may use, change and share
them. By submitting a layout you agree to release it the same way.
