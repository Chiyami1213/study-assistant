# Third-Party Credits

Study Assistant is licensed under the [GNU Affero General Public License, version 3](LICENSE) (AGPL-3.0). It is built on the open-source software below. The licenses are those the installed
packages declare in their own metadata (versions: the ones the release was built with); each package's own license text ships with it.

| Software | Version | License | Used for |
|---|---|---|---|
| [Streamlit](https://streamlit.io) | 1.66.1 | Apache-2.0 | the pages and widgets |
| [PyMuPDF](https://github.com/pymupdf/pymupdf) | 2.1 | AGPL-3.0 (or a commercial license from Artifex) | reading and rendering PDFs |
| [pypdf](https://github.com/py-pdf/pypdf) | 6.21.4 | BSD-3-Clause | PDF text and outlines |
| [Pillow](https://python-pillow.org) | 13.0.0 | MIT-CMU | images and covers |
| [pillow-heif](https://github.com/bigcat88/pillow_heif) | 1.8.1 | BSD-3-Clause for its code; its binary wheels also carry libheif and libde265 (LGPL-3.0) and x265 (GPL-2.0) | HEIC photos |
| [pywebview](https://pywebview.flowrl.com) | 6.2.1 | BSD-3-Clause | the desktop window |
| [psutil](https://github.com/giampaolo/psutil) | 7.2.2 | BSD-3-Clause | stopping the program's own processes |
| [tzdata](https://github.com/python/tzdata) | 2026.6 | Apache-2.0 | time zones (Windows) |
| pandas, NumPy | 3.1.0, 2.5.4 | BSD-3-Clause (NumPy also lists 0BSD, MIT, Zlib, CC0-1.0 for parts) | brought in by Streamlit; tables |
| [three.js](https://threejs.org) r128 | r128 | MIT | the 3D parts of study guides (a copy in `study/vendor/`) |
| [PyInstaller](https://pyinstaller.org) | 6.22.3 | GPL-2.0-or-later with a special exception that allows using it to build and distribute any program | builds the Windows and Mac apps (a build tool; its bootloader is in the exe) |
| [MathJax](https://www.mathjax.org) 3.2.2 | 3.2.2 | Apache-2.0 | math in notes: not bundled, loaded from the jsDelivr CDN when a note with math is opened |

## A point still to settle

The pillow-heif binary wheels list x265 as GPL-2.0 (see the `LICENSES_bundled.txt` that comes with the package). GPL-2.0-only and AGPL-3.0 are generally treated as incompatible unless the GPL-2.0 code also allows "or later" (this is not legal advice, and the notice does not say which applies). Until this is settled
(for example by confirming the x265 terms of that wheel, or by building without HEIC support), the HEIC photo import is the only part that depends on it.

## Your files

The license covers the program. The files you import, and the notes, grades and settings the program keeps for you, are yours and are not covered by it.
