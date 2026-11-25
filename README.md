# Architecture reference site generator

This repository rebuilds the community site published at
`arm.jonpalmisc.com` from Arm's official Exploration Tools XML bundles, and
generates an equivalent RISC-V reference site from the RISC-V Unified
Database. Each build produces a self-contained static site with instruction
pages, register pages, alphabetic indexes, the home page, CSS, fonts and the
Pagefind search component.

The code is split into architecture-specific content layers and an
architecture-neutral presentation layer. The ARM adapters consume Arm's XML
bundles; the RISC-V adapters consume the Unified Database's YAML resolved
specification. The page shell, chrome and listing templates are shared.

## Quick start

You need Python 3.10 or newer, GNU Make, and the Python packages in
`requirements.txt`. Pagefind is optional and needs Node.js if it is not already
installed.

1. Install the Python dependencies:

   ```sh
   make install-deps
   ```

2. Download the two ARM bundles into `tarballs/` (skip this step if you only
   want the RISC-V site):

   ```sh
   mkdir -p tarballs
   version=2026-09
   curl -fL -o "tarballs/ISA_A64_xml_A_profile-${version}.tar.gz" \
     "https://developer.arm.com/-/cdn-downloads/permalink/Exploration-Tools-A64-ISA/ISA_A64/ISA_A64_xml_A_profile-${version}.tar.gz"
   curl -fL -o "tarballs/SysReg_xml_A_profile-${version}.tar.gz" \
     "https://developer.arm.com/-/cdn-downloads/permalink/Exploration-Tools-Arm-Architecture-System-Registers/SysReg/SysReg_xml_A_profile-${version}.tar.gz"
   ```

3. Build the site:

   ```sh
   make
   ```

The output is written to `build/`. A successful build reports:

```text
Generated 2315 instruction pages
Generated 1394 register pages
Generated 6 listing pages plus index.html
Copied 14 assets
Output: .../build
```

To preview it locally:

```sh
make serve
```

Then open <http://localhost:8000/>.

### RISC-V quick start

Preferred: clone the Unified Database and generate its resolved specification
from the checkout. The short commit hash is used as the footer revision.

```sh
make riscv-clone UDB_REPO=../riscv-unified-db
make riscv-resolve UDB_REPO=../riscv-unified-db
make riscv-git UDB_REPO=../riscv-unified-db
make serve-riscv
```

`make riscv-resolve` runs `./do gen:resolved_arch` inside the checkout. It needs
the UDB project's native toolchain (mise, Ruby and the UDB gems); see the
Unified Database README. The resolved specification is generated into
`gen/resolved_spec/` and is not committed to git. The first `./do` run
bootstraps mise; make sure the installed `mise` is on `PATH` (the bootstrap
prints its location) or the bundler step cannot find it.

If you do not want the Ruby toolchain, use the published resolved-spec tarball
instead:

```sh
mkdir -p tarballs
curl -fL -o tarballs/resolved_spec.tar.gz \
  https://riscv.github.io/riscv-unified-db/resolved_spec/resolved_spec.tar.gz
curl -fsSL https://riscv.github.io/riscv-unified-db/index.html \
  | grep -oE '[0-9a-f]{40}' | head -1 > tarballs/resolved_spec.revision
make riscv
make serve-riscv
```

For the Pagefind search index, use `make riscv-git-pagefind` or
`make riscv-pagefind` instead of the plain build target.

The output is written to `build-riscv/`. A successful build reports:

```text
Generated 1397 instruction pages
Generated 417 register pages
Generated 186 extension pages
Generated 3 listing pages plus index.html
Copied 8 assets
Output: .../build-riscv
```

The two architectures are independent: `make` builds the ARM site and
`make riscv` builds the RISC-V site. They share templates, CSS, fonts and the
Pagefind component, but each has its own output and extraction cache.

## Requirements

- Python 3.10 or newer
- `lxml` 5.0 or newer
- `jinja2` 3.1 or newer
- `PyYAML` 6.0 or newer
- GNU Make
- Optional: the Pagefind CLI, or Node.js with `npx`, for the Pagefind targets

Install the Python dependencies with `make install-deps` or:

```sh
python3 -m pip install -r requirements.txt
```

## Source bundles

### ARM Exploration Tools

The generator uses the unsuffixed **Preview** packages:

- `ISA_A64_xml_A_profile-YYYY-MM.tar.gz`
- `SysReg_xml_A_profile-YYYY-MM.tar.gz`

These contain the current architecture data, including Armv9.8 and future
architecture technologies. Arm also publishes `*_YYYY-MM_md.tar.gz` bundles
alongside Architecture Reference Manual revisions. Those are older review/EAC
collateral even when the date matches: for `2026-09`, `_md` is M.d and reaches
only Armv9.6. The generator prefers the unsuffixed Preview bundle when both are
present under the same date, and falls back to `_md` if that is all it finds.

`AARCHMRS_A_profile-*.tar.gz` is not used. It contains schema and feature
metadata, not the generated instruction or register pages.

### Downloading the bundles

Arm's download page is:

<https://developer.arm.com/downloads/-/exploration-tools>

It currently redirects to the A-profile architecture page:

<https://support.arm.com/architectures/a-profile-architecture>

The direct CDN URLs for the `2026-09` Preview bundles are:

- A64 ISA:
  <https://developer.arm.com/-/cdn-downloads/permalink/Exploration-Tools-A64-ISA/ISA_A64/ISA_A64_xml_A_profile-2026-09.tar.gz>
- System registers:
  <https://developer.arm.com/-/cdn-downloads/permalink/Exploration-Tools-Arm-Architecture-System-Registers/SysReg/SysReg_xml_A_profile-2026-09.tar.gz>

To fetch another release, replace `2026-09` in both URLs with the desired
`YYYY-MM`. The download page's embedded metadata is authoritative if the URL
scheme changes. Both bundles must be from the same release; the generator
rejects a mismatched pair.

The SysReg endpoint has occasionally served an uncompressed tar with a
`.tar.gz` name. If the generator reports that the file is not gzip-compressed,
recompress it:

```sh
gzip -c < tarballs/SysReg_xml_A_profile-2026-09.tar.gz > tarballs/SysReg_xml_A_profile-2026-09.tar.gz.new
mv tarballs/SysReg_xml_A_profile-2026-09.tar.gz.new tarballs/SysReg_xml_A_profile-2026-09.tar.gz
```

### RISC-V Unified Database

The RISC-V source is the **resolved specification** published by the
[RISC-V Unified Database](https://github.com/riscv/riscv-unified-db). It is a
single tarball of YAML documents with one file per instruction, CSR and
extension:

<https://riscv.github.io/riscv-unified-db/resolved_spec/resolved_spec.tar.gz>

The preferred source is a git checkout of the Unified Database. The resolved
specification is generated from that checkout with `./do gen:resolved_arch` (see
`make riscv-resolve`); it is written to `gen/resolved_spec/_` and is not
committed to git. `make riscv-git` or `--udb-repo` reads
`git rev-parse --short HEAD`, so the footer shows git's shortest unambiguous
commit hash for the exact checkout.

The published tarball is a fallback for machines without the UDB Ruby
toolchain. It is rebuilt from `main` and does not embed a commit, so the
deployment page's commit can be saved beside it as
`tarballs/resolved_spec.revision` (one line, for example
`5d1ded1f93ab36d3bb6720880a3d12d1d5a8c67e`). The footer shows that hash in
short form. Without a sidecar, the generator shows the specification build
date and a SHA-256 prefix of the tarball; `--version` overrides either.

The generator locates the inner `_` directory automatically. The layout is:

```text
gen/resolved_spec/_/
  index.yaml              # list of every YAML document in the bundle
  inst/<ext>/<name>.yaml  # 1,397 instruction definitions
  csr/<ext>/<name>.yaml   # 417 CSR definitions
  ext/<name>.yaml         # 186 extension definitions
```

There is no published HTML tree to reproduce, so the generator renders the
pages itself from the YAML data: bitfield diagrams, assembly formats, decode
variables, IDL execution pseudocode and access tables. Descriptions are
cleaned of AsciiDoc and ERB scaffolding before rendering.

Additional instruction, CSR or extension YAML can be layered on top with
`--overlay-dir`. Files with the same `name` replace the base object; new names
are appended. This is the hook used for the CHERIoT extensions.

## Building

Run `make` with no arguments to build the site. The default targets and
variables are listed in the table below.

| Target | Effect |
| --- | --- |
| `make` | Build the site into `build/` |
| `make pagefind` | Build the site, then generate the Pagefind index |
| `make riscv-pagefind` | Build the RISC-V site, then generate the Pagefind index |
| `make serve` | Build the site, then serve `build/` on port 8000 |
| `make riscv` | Build the RISC-V site into `build-riscv/` |
| `make riscv-git` | Build RISC-V from a UDB checkout (`UDB_REPO`) |
| `make riscv-clone` | Clone the Unified Database into `UDB_REPO` |
| `make riscv-resolve` | Run `./do gen:resolved_arch` in the UDB checkout |
| `make riscv-git-pagefind` | Build from the checkout, then generate the Pagefind index |
| `make riscv-cheriot` | Build RISC-V plus CHERIoT from a tarball-resolved UDB |
| `make riscv-git-cheriot` | Build RISC-V plus CHERIoT from the UDB and CHERIoT checkouts |
| `make riscv-cheriot-pagefind` | Build RISC-V plus CHERIoT and generate the Pagefind index |
| `make riscv-git-cheriot-pagefind` | Build from both checkouts and generate the Pagefind index |
| `make serve-riscv` | Build the RISC-V site, then serve it on port 8000 |
| `make test` | Run the unit tests |
| `make check` | Compile the Python sources and run the unit tests |
| `make clean` | Remove `build/` and the extraction cache |
| `make install-deps` | Install the Python dependencies |
| `make help` | Show the available targets and variables |

Override the defaults on the command line or in the environment:

| Variable | Default | Purpose |
| --- | --- | --- |
| `TARBALLS_DIR` | `tarballs` | Directory containing the two ARM bundles |
| `BUILD_DIR` | `build` | Output directory |
| `CACHE_DIR` | `.cache/armref` | Cached extraction directory |
| `VERSION` | Derived from the tarball name | Footer version override |
| `RISCV_BUILD_DIR` | `build-riscv` | RISC-V output directory |
| `RISCV_CACHE_DIR` | `.cache/riscv` | RISC-V extraction cache |
| `UDB_REPO` | `../riscv-unified-db` | Unified Database git checkout |
| `CHERIOT_REPO` | `../cheriot-sail` | CHERIoT Sail checkout or `cheri_insts.sail` |
| `PYTHON` | `python3` | Python interpreter |

For example, to use bundles stored in the parent directory:

```sh
make TARBALLS_DIR=..
```

`make` removes the previous output before writing a new one. The extraction
cache is reused between builds and is invalidated when either tarball changes.
`make clean` refuses to remove `/`, your home directory, the repository root or
an ancestor of the repository root.

### Direct Python usage

The Makefile is a wrapper around `generate.py`:

```sh
python3 generate.py \
  --tarballs-dir tarballs \
  --output build \
  --work-dir .cache/armref \
  --clean
```

Use `--pagefind` to run Pagefind after the build, or `--version 2026.09` to
override the footer version. Run `python3 generate.py --help` for all options.

For the RISC-V site, select the RISC-V adapters with `--arch riscv`:

```sh
python3 generate.py \
  --arch riscv \
  --tarballs-dir tarballs \
  --output build-riscv \
  --work-dir .cache/riscv \
  --clean
```

To build from a Unified Database checkout instead of a tarball:

```sh
python3 generate.py --arch riscv --udb-repo ../riscv-unified-db \
  --output build-riscv --clean
```

The checkout must already contain `gen/resolved_spec/` (run
`./do gen:resolved_arch` there). `--spec-dir path/to/resolved_spec/_` uses an
already-resolved directory directly; combine it with `--udb-repo` to take the
footer revision from git, or pass `--version`.

Add `--overlay-dir path/to/overlay` to merge extra instruction, CSR or
extension YAML into the resolved specification. The overlay is a directory of
`*.yaml` files searched recursively; objects are matched by `name`.

Add `--cheriot-repo ../cheriot-sail` to include the CHERIoT capability
instructions from the Sail model. The footer version then becomes
`<udb-revision>+cheriot.<cheriot-revision>` unless `--version` is given.

## Output

```text
build/
  index.html
  robots.txt
  latest_aarch64/    # instruction pages, four listings and SVG diagrams
  latest_sysreg/     # register and system-instruction pages, two listings
  static/            # CSS, fonts and Pagefind bootstrap
  pagefind/          # Pagefind component UI, and the index with make pagefind
```

The generated tree is self-contained. All links are absolute or page-relative,
so it can be served from any static web server.

The RISC-V build has the same shape:

```text
build-riscv/
  index.html
  robots.txt
  latest_riscv/
    index.html          # all instructions
    csrindex.html       # all CSRs
    extindex.html       # all extensions
    insn/<name>.html
    csr/<name>.html
    ext/<name>.html
  static/               # shared CSS and fonts, plus riscv.css
  pagefind/             # Pagefind component UI, and the index with make riscv-pagefind
```

Pagefind indexes the instruction, CSR and extension pages. The home page and
the three listing pages are deliberately excluded so that a listing of every
instruction does not compete with the individual pages in search results.

## How it works

### ARM pipeline

1. **Archive discovery** (`refsite/archive.py`) finds the newest A64 and SysReg
   bundles, checks that their release dates match, and extracts them safely.
   Links and special files are skipped or rejected, and paths cannot escape the
   extraction directory. A marker records each tarball's size and modification
   time so a replaced bundle invalidates the cached extraction.

2. **Content selection** (`refsite/arm_isa.py`, `refsite/arm_sysreg.py`) uses
   Arm's pre-generated `xhtml/*.html` pages as the canonical markup. These are
   the pages produced by Arm's own XSLT, so the generator preserves their
   whitespace and serialisation details.

   - Instruction pages: every `xhtml/*.html` page except the alphabetic and
     encoding indexes and `notice.html`. `shared_pseudocode.html` is included.
   - Register pages: the generator starts from the entries in
     `AArch64-regindex.xml` and `AArch32-regindex.xml`, then follows local links
     transitively. This publishes ordinary registers, extension registers
     reachable from them, and only those system-instruction pages that a
     register page references. Index pages and `notice.html` are never followed
     or emitted.
   - Seven SVG diagrams are copied from the A64 `xhtml/` directory.

3. **DOM transformation** (`refsite/html_transform.py`) removes Arm's top bar
   and footer, rebuilds the page metadata, converts Arm's heading hierarchy to
   the site's, and adds the Pagefind indexing attributes. It also normalises
   instruction encoding labels, register field headings, conditional headings,
   note headers and access-instruction blocks.

4. **Indexes** (`refsite/indexes.py`) runs Arm's own `alphaindex.xsl` and
   `reg_alphaindex.xsl`, keeps the listing region, and rewrites local `.xml`
   links to `.html`.

5. **Presentation** (`refsite/render.py`, `templates/`) supplies the page shell,
   site header, search box, footer, listing top bars and home page. The head
   fragments and shared chrome are separate templates so another architecture
   can reuse the shell.

6. **Assets** (`refsite/site.py`) copies the published CSS, fonts and Pagefind
   component files, copies the SVG diagrams, and writes `robots.txt`.

### RISC-V pipeline

1. **Archive discovery** (`refsite/riscv_archive.py`) finds
   `resolved_spec*.tar.gz`, extracts it safely and caches the result using the
   same size-and-modification-time marker as the ARM adapter.

2. **Specification loading** (`refsite/riscv_spec.py`) reads `index.yaml`,
   loads every referenced YAML document and turns it into `Instruction`, `Csr`
   and `Extension` objects. It handles per-RV32/RV64 encodings, disjoint
   variable bit ranges, `definedBy` expressions and overlay files.

3. **Rendering** (`refsite/riscv_render.py`) produces the body markup: bitfield
   tables, decode-variable tables, IDL pseudocode blocks, access tables,
   extension version tables and the three listings. Pages carry the same
   Pagefind attributes as the ARM pages. Descriptions are cleaned of AsciiDoc
   and ERB scaffolding, and extension pages follow each extension's
   `requirements` tree when they have no direct members, so category
   extensions such as `V`, `A` and `C` list their constituent extensions'
   instructions and CSRs.

4. **Site assembly** (`refsite/riscv_site.py`) writes `latest_riscv/insn/`,
   `latest_riscv/csr/` and `latest_riscv/ext/`, the three listings, the home
   page, the shared assets and `robots.txt`. `refsite/render.py` and the
   templates supply the page shell.

## Fidelity and version drift

With the `2026-09` Preview bundles, the generator reproduces the published site
exactly:

- `latest_aarch64/`: 2,315 content pages and four listings, all byte-identical.
- `latest_sysreg/`: 1,394 content pages and two listings, all byte-identical.
- The home page, `robots.txt`, `static/` and `pagefind/` are byte-identical.
- In a full tree comparison, all 3,731 generated files match. The published
  tree has ten extra names under `latest_sysreg/`; each is a byte-identical copy
  of the site's home page (soft-404 output), not a register description.

Using the older `*_md` bundles instead produces version drift, because that
collateral corresponds to an earlier Architecture Reference Manual revision.
Some newer instructions (for example `LUTI6`, `CFLT`, `ADDQP`, `LDA64B` and
`STL64B`) and newer fields (`FEAT_GCIE_LEGACY`, `FEAT_NV3`, `FEAT_MPAMv2`,
`FEAT_LSC64B`) are then missing. This is a property of the input, not a
generator error. The generator does not patch in newer material.

## RISC-V implementation and CHERIoT overlays

The RISC-V adapters live alongside the ARM ones and reuse the presentation
layer:

- `refsite/riscv_archive.py` — bundle discovery, safe extraction and caching.
- `refsite/riscv_spec.py` — resolved-spec YAML loader and object model.
- `refsite/riscv_render.py` — instruction, CSR, extension and listing markup.
- `refsite/riscv_site.py` — output layout, assets and home page.
- `refsite/cheriot.py` — CHERIoT Sail model loader.

`Renderer` accepts `site_title`, `copyright_text`, `disclaimer` and
`chrome_template` as constructor arguments, so the RISC-V site gets its own
title, copyright, disclaimer and chrome partial without duplicating
`templates/page.html` or `templates/listing.html`.

### CHERIoT extensions

CHERIoT is a capability extension to RISC-V, implemented by both CHERIoT Ibex
and CHERIoT Kudu. It is not part of the Unified Database, so the generator
reads the authoritative encodings from the CHERIoT Sail model:

<https://github.com/CHERIoT-Platform/cheriot-sail>

`refsite/cheriot.py` parses `src/cheri_insts.sail` and adds the `Xcheriot`
extension and its 33 capability instructions (`cgetperm`, `cseal`, `lc`, `sc`,
`auicgp`, `cjal`, ...). The extension page notes that the same ISA is
implemented by Ibex and Kudu; there are no core-specific variants.

Clone the model next to the UDB checkout and build:

```sh
git clone https://github.com/CHERIoT-Platform/cheriot-sail ../cheriot-sail
make riscv-git-cheriot
```

or, from a tarball-resolved UDB:

```sh
make riscv-cheriot
```

Set `CHERIOT_REPO` if the checkout is elsewhere. The footer version becomes
`<udb-revision>+cheriot.<cheriot-revision>` unless `VERSION` is set.
`--cheriot-repo` is the equivalent direct-CLI option and accepts either a
checkout or a path to `src/cheri_insts.sail`.

CHERIoT also changes the meaning of some base instructions (capability-relative
`cjal`/`cjalr`/`lc`/`sc` and the standard load/store forms). The loader
publishes the dedicated capability mnemonics; the extension page describes the
ISA as a whole, and the base instruction pages remain the Unified Database's
RISC-V definitions.

## Repository layout

```text
generate.py              CLI entry point
Makefile                 Build, test and preview targets
requirements.txt         Python dependencies
refsite/
  archive.py             ARM bundle discovery, safe extraction, release selection
  model.py               Page and BuildStats data classes
  output.py              Shared output paths, asset copying and robots.txt
  arm_isa.py             A64 instruction page selection
  arm_sysreg.py          Register page selection and link closure
  html_transform.py      Arm XHTML to site markup transformations
  indexes.py             XSLT-driven alphabetic listings
  riscv_archive.py       RISC-V resolved-spec discovery and extraction
  riscv_spec.py          RISC-V YAML object model and overlay loading
  riscv_render.py        RISC-V page and listing markup
  riscv_site.py          RISC-V build orchestration and assets
  cheriot.py             CHERIoT Sail capability-instruction loader
  render.py              Jinja environment and page render helpers
  site.py                ARM build orchestration, assets and robots.txt
  pagefind.py            Optional Pagefind invocation
templates/               Jinja templates, head fragments and chrome
static/                  Published CSS, fonts and Pagefind bootstrap
riscv/                   RISC-V stylesheet copied to static/riscv.css
pagefind/                Published Pagefind component UI
tests/                   Unit tests
```

The tarballs, build output and extraction cache are ignored by Git. Download
the bundles into `tarballs/` before the first build.

## Troubleshooting

**`no ISA_A64_xml_A_profile-*.tar.gz`**

The bundle is missing or in the wrong directory. Put both bundles in
`tarballs/`, or set `TARBALLS_DIR` to the directory that contains them.

**`A64 and SysReg tarballs are from different releases`**

Download both bundles for the same `YYYY-MM` release. Mixing releases produces
an inconsistent site.

**`not gzip-compressed` when extracting SysReg**

The endpoint returned an uncompressed tar. Recompress it with the `gzip`
command in [Downloading the bundles](#downloading-the-bundles).

**Pagefind index is not generated**

`make pagefind` and `make riscv-pagefind` need either the `pagefind` executable
or Node.js with `npx`. The site itself is already complete without the index;
the search box will not return results until the index exists.

**`no resolved_spec*.tar.gz`**

The RISC-V bundle is missing or in the wrong directory. Download it with the
`curl` command in [RISC-V quick start](#riscv-quick-start), or set
`TARBALLS_DIR` to the directory that contains it.

**`no resolved specification found`**

The tarball extracted, but the loader could not find `index.yaml` with a
sibling `inst/` directory. Check that the archive contains
`gen/resolved_spec/_/`, or point `--tarballs-dir` at the correct bundle.
