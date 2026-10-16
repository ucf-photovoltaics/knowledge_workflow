# Third-party assets

No code was copied from neurosymbolic. Its layout, module boundaries and iframe arrangement were inspected as references.

## WebVOWL

- Upstream: https://github.com/VisualDataWeb/WebVOWL
- Release: `v1.1.7`, commit prefix `28e7dd9`.
- License: MIT, retained in `www/webvowl/license.txt`.
- The browser distribution was built independently from the upstream release with `npm install --ignore-scripts` and `node node_modules/grunt-cli/bin/grunt release`.
- Compiled upstream JS/CSS and data are under `www/webvowl/`. Its index bootstrap was replaced with the new `www/vowl-bridge.js` and its version placeholder resolved. A small loading graph was added as `data/dpv-empty.json`.
- `viewer.py` and the messaging bridge are new implementations. The viewer is a projection of named classes and relationships, not a full OWL reasoner or lossless OWL2VOWL conversion. The exported source ontology remains available for complete inspection.

## UCF branding

- Official UCF Athletics Knighthead announcement: https://ucfknights.com/news/2021/11/17/ucf-athletics-introduces-new-knighthead-secondary-logo
- `www/ucf-knight.jpg` is the announcement's official Open Graph image, saved without alteration. CSS controls its presentation.
- `www/ucf-logo.png` is the official site header asset from https://ucfknights.com/_nuxt/logo.CspbILyZ.png.
- Marks belong to UCF. This local research application uses the user-requested UCF DPV identity.
- UCF identity reference: https://www.ucf.edu/brand/logo-and-identity/
