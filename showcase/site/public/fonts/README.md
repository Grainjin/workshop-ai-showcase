# Simplified Chinese serif fallback

`workshop-song-sc-regular.woff2` and `workshop-song-sc-bold.woff2` are locally
self-hosted derivatives of the official **Noto Serif SC** (Simplified Chinese)
variable font. They provide a readable serif face when system Songti SC/SimSun
is unavailable. No macOS font files are distributed.

Upstream source:
- https://github.com/google/fonts/tree/main/ofl/notoserifsc
- https://raw.githubusercontent.com/google/fonts/main/ofl/notoserifsc/NotoSerifSC%5Bwght%5D.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/notoserifsc/METADATA.pb

Retrieved 2026-10-12. Source SHA-256:
`050080d9255a86808f2945bffac582b31ef32bc36411ce29563b4961670c66f9`.
Official metadata identifies `chinese-simplified` / `zh_Hans`.

The upstream SIL Open Font License 1.1 is retained verbatim in `OFL.txt`.
The font's embedded copyright `(c) 2017-2024 Adobe (http://www.adobe.com/)` is
preserved. Derivative family naming is **Workshop Song SC**; this does not imply
endorsement by Google or Adobe.

Generated with fontTools 4.55.3: instantiate `wght=400` and `wght=700`, subset
each to all characters in non-test `.ts`/`.tsx` source plus printable ASCII and
Chinese punctuation, retain name/copyright/license records, and encode WOFF2.
Both outputs were reopened and verified to cover all **673 required codepoints**.
Regular: 111,648 bytes; bold: 114,824 bytes. Future copy introducing new characters
must rebuild and verify this subset. Use the SC upstream, never JP/TC variants.
