# Nebula layouts

On-screen control layouts for [Nebula](https://github.com/F-e-n-y-x/nebula), the Android game-stream
client for Nova. Nebula's editor lists this library under **Profiles → Browse layouts**, reads
`index.json` and downloads a layout only when you pick it.

## Layout

```
index.json                          generated: every layout with name, game, checksum, preview
schema/nebula-layout-1.schema.json  JSON Schema of a layout file
tools/validate.py                   validator and index builder (Python 3, standard library)
layouts/<game>/<name>.json          one layout per file
```

`<game>` is a lower-case slug (`gta-v`, `apex-legends`), or `generic` for layouts that suit any
game of a kind (the PUBG-style shooter layouts). File names are lower case, `a-z 0-9 -`.

## The format

```json
{
  "format": "nebula-layout",
  "version": 1,
  "meta": {
    "name": "GTA V: PUBG-style",
    "author": "Nebula",
    "game": { "name": "Grand Theft Auto V", "steamAppId": 271590 },
    "target": "xinput",
    "device": "phone",
    "aspect": 2.17,
    "description": "…",
    "tags": ["gta", "shooter"]
  },
  "settings": { "outside": "look", "look": "mouse" },
  "landscape": [ { "id": "fire", "kind": "trigger", "x": 0.8, "y": 0.55, "w": 80, "h": 80, "bindings": ["rt"], "lookThrough": true } ],
  "portrait": [ … ]
}
```

- `x`, `y` are the element's centre as a share (0–1) of the controls area, so layouts carry
  across screens. `w`, `h` are dp for controls (28–360) and a share of the area for zones.
  Nebula's style picker scales the dp sizes to the device.
- `target`: `xinput` (gamepad), `kbm` (keyboard and mouse) or `mixed`. `device`: `phone`,
  `tablet` or `any`. `aspect`: the landscape area's width / height it was made on.
- Bindings are names only: `pad:<flag>` (A = 4096, B = 8192, X = 16384, Y = 32768, LB = 256,
  RB = 512, L3 = 64, R3 = 128, Start = 16, Back = 32, D-pad 1/2/4/8), `lt`, `rt`,
  `key:<Windows virtual-key code>`, `mouse:left|right|middle|back|forward`, `wheel:up|down`,
  `none`.
- Fields at their default may be left out. Anything unknown is an error.

The easiest way to make one is Nebula itself: edit the controls, then **Profiles → Share →
Save file** (or **Share to library**, which fills in a GitHub page for you).

## Submitting a layout

1. Play with it first. A layout goes in only if its author has used it in the game.
2. Put the file in `layouts/<game>/<name>.json`. One layout per pull request.
3. Run `python3 tools/validate.py --write-index` and commit `index.json` with the layout.
4. Open a pull request with a screenshot of the layout (Nebula's **Share to library** saves one)
   and a line on how it plays (fingers, which in-game settings it expects).

Or open an issue with Nebula's **Share to library → Open an issue**: it fills in the JSON, and a
maintainer adds it.

## Review rules

A maintainer merges a layout when:

- `tools/validate.py` passes (CI runs it on every pull request) and `index.json` is regenerated;
- the name says the game and the style, e.g. "Apex Legends: claw 4-finger";
- `game` names the real game (with its Steam app id when there is one); generic layouts have no
  `game` and go in `layouts/generic/`;
- `target` matches the bindings, and the description says which in-game controls it expects;
- no two layouts are near-copies (improve the existing one instead);
- labels and descriptions are plain, polite English; no links, ads or personal data;
- nothing in it tries to do more than press buttons: no macros longer than a few seconds, no
  key sequences that open programs or type text (Win+R, Alt+F4, Ctrl+Alt+Del and similar are
  refused).

Layouts are data, never code: Nebula validates every download again (size cap, known fields and
values only, checksum from `index.json`) before it shows a preview, and nothing is installed
until you tap **Add**.

## Licence

Layouts are contributed under CC0 1.0: anyone may copy, change and share them.

## License

Layouts in this repository are released under [CC0 1.0](LICENSE): anyone may use, change and
share them. By submitting a layout you agree to release it the same way.
