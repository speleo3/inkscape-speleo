[![CI](https://github.com/speleo3/inkscape-speleo/workflows/CI/badge.svg)](https://github.com/speleo3/inkscape-speleo/actions)

# Inkscape extensions for cave surveying

Collection of extensions for Inkscape to import/export various cave mapping data files, including:

| Format                | Import | Export  |
| --------------------- | ------ | ------- |
| Survex `.3d`          | Yes    |         |
| Therion `.th2`        | Yes    | Yes     |
| Therion `.xvi`        | Yes    |         |
| Therion MetaPost      |        | Yes     |
| PocketTopo `.top`     | Yes    |         |
| SexyTopo `.plan.json` | Yes    |         |

In addition, there are symbol annotation extensions in the
_Extensions > Therion_ menu for the `.th2` export.

## Installation (basic)

Copy everything from the [extensions](extensions) folder into the Inkscape extensions folder. This is probably similar to one of these:

* Windows: `%APPDATA%\Inkscape\extensions`
* Linux: `~/.config/inkscape/extensions`

If you can't find the folder, check _Inkscape > Preferences > System > User config_, or run `inkscape --user-data-directory`.

## Installation (advanced)

Clone the repo directly to your user data directory. This can be done (in
a reasonable safe way) with the following commands:

```sh
git clone --no-checkout https://github.com/speleo3/inkscape-speleo
mv inkscape-speleo/.git "$(inkscape --user-data-directory)/"
rmdir inkscape-speleo
cd "$(inkscape --user-data-directory)"
git checkout
```

And whenever there are updates to the repo:

```sh
cd "$(inkscape --user-data-directory)"
git pull
```

## Therion Metapost

Supports point symbol export. One symbol per layer, with layer names like
`p_stalactite_UIS` or `p_u_mysymbol`. Start with _File > New From Template >
Custom > Therion Metapost_ (opens
[templates/therion_mp.svg](templates/therion_mp.svg)). The orange box with label "U" is the bounding box for alignment (optional).

## See also:

* http://therion.speleo.sk/
* http://survex.com/
* http://jaskinie.jaszczur.org/index_en.html
