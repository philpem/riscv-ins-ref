# ARM reference site generator

This repository rebuilds the community site published at
`arm.jonpalmisc.com` from Arm's official Exploration Tools XML bundles. The
generator produces a self-contained static site with instruction pages, system
register pages, alphabetic indexes, the home page, CSS, fonts and the Pagefind
search component.

The code is split into an ARM-specific content layer and an architecture-neutral
presentation layer. The templates can be reused for a RISC-V reference site;
see [Reusing this for RISC-V](#reusing-this-for-risc-v).

## Quick start

You need Python 3.10 or newer, GNU Make, and the Python packages in
`requirements.txt`. Pagefind is optional and needs Node.js if it is not already
installed.

1. Install the Python dependencies:

   ```sh
   make install-deps
   ```

2. Download the two ARM bundles into `tarballs/`:

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

## Requirements

- Python 3.10 or newer
- `lxml` 5.0 or newer
- `jinja2` 3.1 or newer
- GNU Make
- Optional: the Pagefind CLI, or Node.js with `npx`, for `make pagefind`

Install the Python dependencies with `make install-deps` or:

```sh
python3 -m pip install -r requirements.txt
```

## Source bundles

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

## Building

Run `make` with no arguments to build the site. The default targets and
variables are listed in the table below.

| Target | Effect |
| --- | --- |
| `make` | Build the site into `build/` |
| `make pagefind` | Build the site, then generate the Pagefind index |
| `make serve` | Build the site, then serve `build/` on port 8000 |
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

The generated tree is self-contained. All links are absolute or relative to the
site root, so it can be served from any static web server.

## How it works

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

## Reusing this for RISC-V

The presentation layer is architecture-neutral. A RISC-V generator needs to
provide:

1. An archive or discovery module that locates the RISC-V source bundles.
2. A content adapter that turns each source document into `Page` objects with
   `path`, `html`, `title`, `description` and `kind` fields. The adapter is
   responsible for the body markup and Pagefind attributes.
3. Index builders that produce listing regions in the same shape as
   `refsite/indexes.py`.
4. Site constants for the title, description, navigation links and output
   directory names, plus a footer copyright/disclaimer and a chrome partial for
   the site notice.

`Renderer` accepts `site_title`, `copyright_text`, `disclaimer` and
`chrome_template` as constructor arguments. `templates/page.html`,
`templates/listing.html`, `templates/home.html` and `refsite/render.py` can then
be reused, including the search box, footer and Pagefind wiring.

## Repository layout

```text
generate.py              CLI entry point
Makefile                 Build, test and preview targets
requirements.txt         Python dependencies
refsite/
  archive.py             Bundle discovery, safe extraction, release selection
  model.py               Page and BuildStats data classes
  arm_isa.py             A64 instruction page selection
  arm_sysreg.py          Register page selection and link closure
  html_transform.py      Arm XHTML to site markup transformations
  indexes.py             XSLT-driven alphabetic listings
  render.py              Jinja environment and page render helpers
  site.py                Build orchestration, assets and robots.txt
  pagefind.py            Optional Pagefind invocation
templates/               Jinja templates, head fragments and chrome
static/                  Published CSS, fonts and Pagefind bootstrap
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

`make pagefind` needs either the `pagefind` executable or Node.js with `npx`.
The site itself is already complete without the index; the search box will not
return results until the index exists.
