# Third-party notices

## Document reading additions

Pillow **12.2.0** retains its [HPND license](third_party/python/pillow/). pypdfium2 **5.15.1** offers Apache-2.0/BSD-3-Clause licensing; its wrapper, PDFium and bundled dependency notices are retained in [the notice directory](third_party/python/pypdfium2/), including the PDFium BSD license and component licenses. No PDFium source or binaries are copied into this Git repository. Installed wheels retain their notices in the application container.

Tesseract is an unmodified, separate **Apache-2.0** executable installed from Debian packages in the container. [Tesseract](third_party/tesseract/LICENSE) and [Leptonica](third_party/tesseract/leptonica-license.txt) notices are retained; Debian package copyright/license files remain in `/usr/share/doc`. This subprocess integration does not relicense the engine. Windows local validation used the upstream-linked Tesseract 5.5.3 installer, retained only in ignored local work files.

The printed receipt and scan fixtures are authored synthetic records under this repository's MIT license. The evaluated handwritten manuscript is public domain, credited to Library of Congress, Manuscript Division, Abraham Lincoln Papers; its image is not vendored. These are evaluation materials, not real customer transactions.

## Delivery map additions

Leaflet **1.9.4** is BSD-2-Clause, copyright Volodymyr Agafonkin and CloudMade; its full [license](third_party/npm/leaflet/LICENSE) is retained. `@types/leaflet` **1.9.21** and `@types/geojson` **7946.0.16** retain their MIT [Leaflet types](third_party/npm/@types/leaflet/LICENSE) / [GeoJSON types](third_party/npm/@types/geojson/LICENSE) notices. Package versions are locked. No geocoding server code is vendored.

Photon is an Apache-2.0 open-source geocoder accessed through its documented public API at low volume, with no availability guarantee. Its service policy is separate from its software license. Geocoding and map data are from OpenStreetMap contributors under [ODbL](https://www.openstreetmap.org/copyright); this project does not relicense provider data as MIT. Visible map attribution is retained. [Photon usage/API](https://github.com/komoot/photon) · [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/). No public Nominatim service is called.

VERDICT uses maintained open-source infrastructure. No application code from the five reviewed dispute projects was copied. Research credits and pinned source commits are in docs/RESEARCH.md.

The frontend build bundles runtime packages. Installed package license texts are retained below, including development packages for completeness. Original notices must remain with redistributed portions.

| Package | Installed version | Declared license | License text |
|---|---|---|---|
| @babel/code-frame | 7.29.7 | MIT | [notice](third_party/npm/babel__code-frame.txt) |
| @babel/compat-data | 7.29.7 | MIT | [notice](third_party/npm/babel__compat-data.txt) |
| @babel/core | 7.29.13 | MIT | [notice](third_party/npm/babel__core.txt) |
| @babel/generator | 7.29.13 | MIT | [notice](third_party/npm/babel__generator.txt) |
| @babel/helper-compilation-targets | 7.29.13 | MIT | [notice](third_party/npm/babel__helper-compilation-targets.txt) |
| @babel/helper-globals | 7.29.7 | MIT | [notice](third_party/npm/babel__helper-globals.txt) |
| @babel/helper-module-imports | 7.29.7 | MIT | [notice](third_party/npm/babel__helper-module-imports.txt) |
| @babel/helper-module-transforms | 7.29.13 | MIT | [notice](third_party/npm/babel__helper-module-transforms.txt) |
| @babel/helper-plugin-utils | 7.29.7 | MIT | [notice](third_party/npm/babel__helper-plugin-utils.txt) |
| @babel/helper-string-parser | 7.29.13 | MIT | [notice](third_party/npm/babel__helper-string-parser.txt) |
| @babel/helper-validator-identifier | 7.29.7 | MIT | [notice](third_party/npm/babel__helper-validator-identifier.txt) |
| @babel/helper-validator-option | 7.29.7 | MIT | [notice](third_party/npm/babel__helper-validator-option.txt) |
| @babel/helpers | 7.29.13 | MIT | [notice](third_party/npm/babel__helpers.txt) |
| @babel/parser | 7.29.13 | MIT | [notice](third_party/npm/babel__parser.txt) |
| @babel/plugin-transform-react-jsx-self | 7.29.7 | MIT | [notice](third_party/npm/babel__plugin-transform-react-jsx-self.txt) |
| @babel/plugin-transform-react-jsx-source | 7.29.7 | MIT | [notice](third_party/npm/babel__plugin-transform-react-jsx-source.txt) |
| @babel/template | 7.29.7 | MIT | [notice](third_party/npm/babel__template.txt) |
| @babel/traverse | 7.29.13 | MIT | [notice](third_party/npm/babel__traverse.txt) |
| @babel/types | 7.29.11 | MIT | [notice](third_party/npm/babel__types.txt) |
| @jridgewell/gen-mapping | 0.3.13 | MIT | [notice](third_party/npm/jridgewell__gen-mapping.txt) |
| @jridgewell/remapping | 2.3.5 | MIT | [notice](third_party/npm/jridgewell__remapping.txt) |
| @jridgewell/resolve-uri | 3.1.2 | MIT | [notice](third_party/npm/jridgewell__resolve-uri.txt) |
| @jridgewell/sourcemap-codec | 1.6.0 | MIT | [notice](third_party/npm/jridgewell__sourcemap-codec.txt) |
| @jridgewell/trace-mapping | 0.3.31 | MIT | [notice](third_party/npm/jridgewell__trace-mapping.txt) |
| @rolldown/pluginutils | 1.0.0-beta.27 | MIT | [notice](third_party/npm/rolldown__pluginutils.txt) |
| @types/babel__core | 7.20.5 | MIT | [notice](third_party/npm/types__babel__core.txt) |
| @types/babel__generator | 7.27.0 | MIT | [notice](third_party/npm/types__babel__generator.txt) |
| @types/babel__template | 7.4.4 | MIT | [notice](third_party/npm/types__babel__template.txt) |
| @types/babel__traverse | 7.28.0 | MIT | [notice](third_party/npm/types__babel__traverse.txt) |
| @types/d3-color | 3.1.3 | MIT | [notice](third_party/npm/types__d3-color.txt) |
| @types/d3-drag | 3.0.7 | MIT | [notice](third_party/npm/types__d3-drag.txt) |
| @types/d3-interpolate | 3.0.4 | MIT | [notice](third_party/npm/types__d3-interpolate.txt) |
| @types/d3-selection | 3.0.12 | MIT | [notice](third_party/npm/types__d3-selection.txt) |
| @types/d3-transition | 3.0.9 | MIT | [notice](third_party/npm/types__d3-transition.txt) |
| @types/d3-zoom | 3.0.9 | MIT | [notice](third_party/npm/types__d3-zoom.txt) |
| @types/estree | 1.0.10 | MIT | [notice](third_party/npm/types__estree.txt) |
| @types/react | 19.3.0 | MIT | [notice](third_party/npm/types__react.txt) |
| @types/react-dom | 19.3.0 | MIT | [notice](third_party/npm/types__react-dom.txt) |
| @vitejs/plugin-react | 4.7.0 | MIT | [notice](third_party/npm/vitejs__plugin-react.txt) |
| @xyflow/react | 12.12.1 | MIT | [notice](third_party/npm/xyflow__react.txt) |
| @xyflow/system | 0.0.84 | MIT | [notice](third_party/npm/xyflow__system.txt) |
| baseline-browser-mapping | 2.11.35 | Apache-2.0 | [notice](third_party/npm/baseline-browser-mapping.txt) |
| browserslist | 4.29.5 | MIT | [notice](third_party/npm/browserslist.txt) |
| caniuse-lite | 1.0.30001822 | CC-BY-4.0 | [notice](third_party/npm/caniuse-lite.txt) |
| classcat | 5.0.5 | MIT | [notice](third_party/npm/classcat.txt) |
| convert-source-map | 2.0.0 | MIT | [notice](third_party/npm/convert-source-map.txt) |
| csstype | 3.2.3 | MIT | [notice](third_party/npm/csstype.txt) |
| d3-color | 3.1.1 | ISC | [notice](third_party/npm/d3-color.txt) |
| d3-dispatch | 3.0.2 | ISC | [notice](third_party/npm/d3-dispatch.txt) |
| d3-drag | 3.0.1 | ISC | [notice](third_party/npm/d3-drag.txt) |
| d3-ease | 3.0.2 | BSD-3-Clause | [notice](third_party/npm/d3-ease.txt) |
| d3-interpolate | 3.0.2 | ISC | [notice](third_party/npm/d3-interpolate.txt) |
| d3-selection | 3.0.1 | ISC | [notice](third_party/npm/d3-selection.txt) |
| d3-timer | 3.0.2 | ISC | [notice](third_party/npm/d3-timer.txt) |
| d3-transition | 3.0.2 | ISC | [notice](third_party/npm/d3-transition.txt) |
| d3-zoom | 3.0.1 | ISC | [notice](third_party/npm/d3-zoom.txt) |
| debug | 4.4.3 | MIT | [notice](third_party/npm/debug.txt) |
| electron-to-chromium | 1.5.477 | ISC | [notice](third_party/npm/electron-to-chromium.txt) |
| esbuild | 0.25.12 | MIT | [notice](third_party/npm/esbuild.txt) |
| escalade | 3.2.0 | MIT | [notice](third_party/npm/escalade.txt) |
| fdir | 6.5.0 | MIT | [notice](third_party/npm/fdir.txt) |
| gensync | 1.0.0-beta.2 | MIT | [notice](third_party/npm/gensync.txt) |
| js-tokens | 4.0.0 | MIT | [notice](third_party/npm/js-tokens.txt) |
| json5 | 2.2.3 | MIT | [notice](third_party/npm/json5.txt) |
| lru-cache | 5.1.1 | ISC | [notice](third_party/npm/lru-cache.txt) |
| lucide-react | 0.468.0 | ISC | [notice](third_party/npm/lucide-react.txt) |
| ms | 2.1.3 | MIT | [notice](third_party/npm/ms.txt) |
| nanoid | 3.3.20 | MIT | [notice](third_party/npm/nanoid.txt) |
| node-releases | 2.0.63 | MIT | [notice](third_party/npm/node-releases.txt) |
| picocolors | 1.1.1 | ISC | [notice](third_party/npm/picocolors.txt) |
| picomatch | 4.0.7 | MIT | [notice](third_party/npm/picomatch.txt) |
| postcss | 8.5.32 | MIT | [notice](third_party/npm/postcss.txt) |
| react | 19.3.1 | MIT | [notice](third_party/npm/react.txt) |
| react-dom | 19.3.1 | MIT | [notice](third_party/npm/react-dom.txt) |
| react-refresh | 0.17.0 | MIT | [notice](third_party/npm/react-refresh.txt) |
| rollup | 4.67.5 | MIT | [notice](third_party/npm/rollup.txt) |
| scheduler | 0.28.0 | MIT | [notice](third_party/npm/scheduler.txt) |
| semver | 6.3.2 | ISC | [notice](third_party/npm/semver.txt) |
| source-map-js | 1.2.2 | BSD-3-Clause | [notice](third_party/npm/source-map-js.txt) |
| tinyglobby | 0.2.17 | MIT | [notice](third_party/npm/tinyglobby.txt) |
| typescript | 5.9.3 | Apache-2.0 | [notice](third_party/npm/typescript.txt) |
| update-browserslist-db | 1.3.4 | MIT | [notice](third_party/npm/update-browserslist-db.txt) |
| use-sync-external-store | 1.7.0 | MIT | [notice](third_party/npm/use-sync-external-store.txt) |
| vite | 6.4.5 | MIT | [notice](third_party/npm/vite.txt) |
| yallist | 3.1.1 | ISC | [notice](third_party/npm/yallist.txt) |
| zustand | 4.5.7 | MIT | [notice](third_party/npm/zustand.txt) |

Python dependencies are installed from PyPI according to backend/requirements.lock.txt; they are not vendored into the source release. Their distributions retain upstream notices.

| Distribution | Version | License metadata |
|---|---|---|
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| argon2-cffi | 25.1.0 | MIT |
| argon2-cffi-bindings | 26.1.0 | MIT; bundled Argon2 upstream notices retained |
| anyio | 4.16.0 | MIT |
| certifi | 2026.10.23 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| click | 8.5.0 | BSD-3-Clause |
| colorama | 0.4.6 | See upstream distribution |
| fastapi | 0.162.0 | MIT |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| iniconfig | 2.3.1 | MIT |
| opentelemetry-api | 1.45.2 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pluggy | 1.7.0 | MIT |
| pwdlib | 0.3.1 | MIT |
| pycparser | 3.12 | BSD-3-Clause |
| pydantic | 2.14.3 | MIT |
| pydantic_core | 2.50.4 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| pypdf | 6.21.4 | BSD-3-Clause |
| pytest | 9.2.0 | MIT |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| python-multipart | 0.0.33 | Apache-2.0 |
| starlette | 1.10.0 | BSD-3-Clause |
| typing-inspection | 0.4.5 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| uvicorn | 0.54.0 | BSD-3-Clause |

## Publication license review

The optional local-model worker uses separately installed [Ollama](https://github.com/ollama/ollama) (MIT), [IBM Granite 4 Micro](https://huggingface.co/ibm-granite/granite-4.0-micro) (Apache-2.0) and [Hugging Face Tokenizers](https://github.com/huggingface/tokenizers) (Apache-2.0). These projects retain their upstream notices. No model weights, Ollama binaries or tokenizer artifacts are redistributed here. The worker's HTTPX dependency is BSD-3-Clause and is also part of the existing application dependency review. Review upstream terms before substituting a model. [Integration and verification](docs/OLLAMA_FALLBACK.md).

All 90 installed npm packages were inspected: 71 MIT, 14 ISC, 2 Apache-2.0, 2 BSD-3-Clause and 1 CC-BY-4.0 data package. The 86 upstream license files available at package roots are preserved above, with generated-bundle dependencies retaining their package notices. The CC-BY-4.0 data belongs to caniuse-lite; credit the [caniuse-lite contributors and upstream data](https://github.com/browserslist/caniuse-lite). No vendor UI assets or competitor application source were copied.

Python distributions use MIT/BSD/Apache/PSF-compatible licenses, plus the unmodified certifi certificate bundle under MPL-2.0. These dependency licenses retain their own scope; the project MIT license does not replace them. [Certifi upstream source](https://github.com/certifi/python-certifi) supplies the certificate-bundle source. Installed Python license and notice texts are retained in [third_party/python](third_party/python). Packaging is dual Apache-2.0/BSD-2-Clause; typing_extensions uses PSF-2.0. Dependencies are unmodified and installed through the lockfile.


## Public evidence research dependencies

Google Gen AI SDK and Trafilatura are unmodified Apache-2.0 components. The HTTP adapters use existing httpx; no search-engine HTML scraping or competitor application code was copied. The following additional distributions retain their license texts under `third_party/python/`. These licenses apply to their own components, not to original project code.

| Distribution | Version | License | Notice |
|---|---|---|---|
| babel | 2.18.0 | BSD-3-Clause | [license](third_party/python/babel/LICENSE.txt) |
| charset-normalizer | 3.5.2 | MIT | [license](third_party/python/charset-normalizer/LICENSE.txt) |
| courlan | 1.4.0 | Apache-2.0 | [license](third_party/python/courlan/LICENSE.txt) |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | [license](third_party/python/cryptography/LICENSE.txt) |
| dateparser | 1.5.0 | BSD-3-Clause | [license](third_party/python/dateparser/LICENSE.txt) |
| distro | 1.9.0 | Apache License, Version 2.0 | [license](third_party/python/distro/LICENSE.txt) |
| google-auth | 2.62.1 | Apache 2.0 | [license](third_party/python/google-auth/LICENSE.txt) |
| google-genai | 1.75.0 | Apache-2.0 | [license](third_party/python/google-genai/LICENSE.txt) |
| htmldate | 1.11.0 | Apache-2.0 | [license](third_party/python/htmldate/LICENSE.txt) |
| jusText | 3.0.2 | The BSD 2-Clause License | [license](third_party/python/justext/LICENSE.txt) |
| lxml | 6.1.3 | BSD-3-Clause | [license](third_party/python/lxml/LICENSE.txt) |
| lxml_html_clean | 0.4.6 | BSD-3-Clause | [license](third_party/python/lxml-html-clean/LICENSE.txt) |
| pyasn1 | 0.6.5 | BSD-2-Clause | [license](third_party/python/pyasn1/LICENSE.txt) |
| pyasn1_modules | 0.4.2 | BSD | [license](third_party/python/pyasn1-modules/LICENSE.txt) |
| python-dateutil | 4.0.0 | BSD-3-Clause | [license](third_party/python/python-dateutil/LICENSE.txt) |
| pytz | 2026.6 | MIT | [license](third_party/python/pytz/LICENSE.txt) |
| regex | 2026.9.29 | Apache-2.0 AND CNRI-Python | [license](third_party/python/regex/LICENSE.txt) |
| requests | 2.34.2 | Apache-2.0 | [license](third_party/python/requests/LICENSE.txt) |
| sniffio | 1.3.1 | MIT OR Apache-2.0 | [license](third_party/python/sniffio/LICENSE.txt) |
| tenacity | 9.1.4 | Apache 2.0 | [license](third_party/python/tenacity/LICENSE.txt) |
| tld | 0.13.2 | MPL-1.1 OR GPL-2.0-only OR LGPL-2.1-or-later | [license](third_party/python/tld/LICENSE.txt) |
| trafilatura | 2.3.1 | Apache-2.0 | [license](third_party/python/trafilatura/LICENSE.txt) |
| tzdata | 2026.6 | Apache-2.0 | [license](third_party/python/tzdata/LICENSE.txt) |
| tzlocal | 5.4.5 | MIT | [license](third_party/python/tzlocal/LICENSE.txt) |
| urllib3 | 2.8.0 | MIT | [license](third_party/python/urllib3/LICENSE.txt) |
| websockets | 16.1.1 | BSD-3-Clause | [license](third_party/python/websockets/LICENSE.txt) |

`tld` is used under its MPL-1.1 option; it is unmodified and installed as a separate dependency. Its corresponding source is available from [PyPI](https://pypi.org/project/tld/0.13.2/#files) and [upstream](https://github.com/barseghyanartur/tld). `regex` retains Apache-2.0 and CNRI-Python notices; `cryptography` and `lxml` retain their bundled notices. No copyleft component has been relabeled as project MIT code. Tavily/Wikimedia/Crossref/Google API services have separate terms; consuming their documented APIs does not vendor their server software.
