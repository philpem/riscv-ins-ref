# Architecture reference site generator

The generator rebuilds the Arm reference at <https://arm.jonpalmisc.com/> from
Arm's Exploration Tools XML bundles. It also builds the RISC-V reference at
<https://philpem.github.io/riscv-ins-ref/> from the RISC-V Unified Database's
YAML resolved specification, with CHERIoT capability instructions added from the
CHERIoT Sail model. Both sites use the same page shell, CSS and Pagefind search
component.

## Quick start

You need Python 3.10 or newer, GNU Make and the packages in `requirements.txt`:

```sh
make install-deps
```

### Arm

Download the two `2026-09` Preview bundles into `tarballs/`, then build and
serve the site:

```sh
mkdir -p tarballs
version=2026-09
curl -fL -o "tarballs/ISA_A64_xml_A_profile-${version}.tar.gz" \
  "https://developer.arm.com/-/cdn-downloads/permalink/Exploration-Tools-A64-ISA/ISA_A64/ISA_A64_xml_A_profile-${version}.tar.gz"
curl -fL -o "tarballs/SysReg_xml_A_profile-${version}.tar.gz" \
  "https://developer.arm.com/-/cdn-downloads/permalink/Exploration-Tools-Arm-Architecture-System-Registers/SysReg/SysReg_xml_A_profile-${version}.tar.gz"
make
make serve
```

The site is written to `build/` and served at <http://localhost:8000/>. A
successful build reports:

```text
Generated 2315 instruction pages
Generated 1394 register pages
Generated 6 listing pages plus index.html
Copied 14 assets
```

### RISC-V

Clone and resolve the Unified Database, then build:

```sh
make riscv-clone UDB_REPO=../riscv-unified-db
make riscv-resolve UDB_REPO=../riscv-unified-db
make riscv-git UDB_REPO=../riscv-unified-db
make serve-riscv
```

`make riscv-resolve` runs `./do gen:resolved_arch` and needs the UDB Ruby
toolchain (mise, Ruby and the UDB gems). The resolved specification is written
to `gen/resolved_spec/` and is not committed. The first `./do` run installs
mise; keep it on `PATH`, or Bundler will fail when it tries to run `mise`.

Without the Ruby toolchain, use the published tarball:

```sh
mkdir -p tarballs
curl -fL -o tarballs/resolved_spec.tar.gz \
  https://riscv.github.io/riscv-unified-db/resolved_spec/resolved_spec.tar.gz
curl -fsSL https://riscv.github.io/riscv-unified-db/index.html \
  | grep -oE '[0-9a-f]{40}' | head -1 > tarballs/resolved_spec.revision
make riscv
make serve-riscv
```

The site is written to `build-riscv/`. Use the matching `*-pagefind` target
(for example `make riscv-git-pagefind`) to generate the search index.

### CHERIoT

```sh
git clone https://github.com/CHERIoT-Platform/cheriot-sail ../cheriot-sail
make riscv-git-cheriot
```

This adds the `Xcheriot` extension and its 33 capability instructions. CHERIoT
mnemonics use the `ct.` vendor prefix allocated by the RISC-V Toolchain
Conventions, for example `ct.cgetperm`, `ct.cseal` and `ct.auipcc`. The
extension page notes that CHERIoT Ibex and CHERIoT Kudu implement the same ISA.
## Requirements

- Python 3.10 or newer
- `lxml` 5.0 or newer
- `jinja2` 3.1 or newer
- `PyYAML` 6.0 or newer
- GNU Make
- Optional: the Pagefind CLI, or Node.js with `npx`

Install with `make install-deps` or:

```sh
python3 -m pip install -r requirements.txt
```

## Sources

### Arm

The generator needs the unsuffixed **Preview** bundles:

- `ISA_A64_xml_A_profile-YYYY-MM.tar.gz`
- `SysReg_xml_A_profile-YYYY-MM.tar.gz`

The `_md` bundles are older review collateral even when the date matches: for
`2026-09`, `_md` reaches Armv9.6 while the Preview bundle includes Armv9.8. The
generator prefers the unsuffixed bundle. `AARCHMRS_A_profile-*.tar.gz` is not
used.

Download from <https://developer.arm.com/downloads/-/exploration-tools>. Both
bundles must use the same release; the generator rejects a mismatch. If the
SysReg endpoint returns an uncompressed tar, recompress it:

```sh
gzip -c < tarballs/SysReg_xml_A_profile-2026-09.tar.gz > tarballs/SysReg_xml_A_profile-2026-09.tar.gz.new
mv tarballs/SysReg_xml_A_profile-2026-09.tar.gz.new tarballs/SysReg_xml_A_profile-2026-09.tar.gz
```

### RISC-V

Use a git checkout of <https://github.com/riscv/riscv-unified-db> when you can,
resolved with `make riscv-resolve`. `--udb-repo` reads
`git rev-parse --short HEAD`, so the footer shows the exact revision.

The tarball fallback is
<https://riscv.github.io/riscv-unified-db/resolved_spec/resolved_spec.tar.gz>.
Save the deployment page's 40-character commit in
`tarballs/resolved_spec.revision` to show it in short form. Without a sidecar,
the footer shows the build date and a SHA-256 prefix; `--version` overrides it.

The resolved layout is:

```text
gen/resolved_spec/_/
  index.yaml
  inst/<ext>/<name>.yaml
  csr/<ext>/<name>.yaml
  ext/<name>.yaml
```

Arm ships rendered HTML; the Unified Database doesn't. The generator builds the
pages from YAML instead, including bitfield diagrams, assembly formats, decode
variables, IDL pseudocode and access tables. `--overlay-dir` merges extra YAML
by `name`.

## Building

| Target | Effect |
| --- | --- |
| `make` | Build the Arm site into `build/` |
| `make pagefind` | Build Arm, then generate the Pagefind index |
| `make serve` | Build Arm, then serve it on port 8000 |
| `make riscv` | Build RISC-V from `tarballs/` into `build-riscv/` |
| `make riscv-git` | Build RISC-V from the `UDB_REPO` checkout |
| `make riscv-git-cheriot` | Build RISC-V and CHERIoT from both checkouts |
| `make riscv-git-cheriot-pagefind` | As above, then generate the Pagefind index |
| `make serve-riscv` | Build RISC-V, then serve it on port 8000 |
| `make test` | Run the unit tests |
| `make check` | Compile and run the unit tests |
| `make clean` | Remove build output and extraction caches |

Use `make help` for the full list, including tarball and Pagefind variants.

| Variable | Default | Purpose |
| --- | --- | --- |
| `TARBALLS_DIR` | `tarballs` | Source bundles |
| `BUILD_DIR` | `build` | Arm output |
| `RISCV_BUILD_DIR` | `build-riscv` | RISC-V output |
| `UDB_REPO` | `../riscv-unified-db` | Unified Database checkout |
| `CHERIOT_REPO` | `../cheriot-sail` | CHERIoT Sail checkout |
| `RISCV_BASE_URL` | empty | URL path prefix for a subpath deployment |
| `VERSION` | derived | Footer version override |

Each build replaces the previous output. Extractions are cached until a bundle
changes. `make clean` refuses to remove unsafe paths such as `/`, your home
directory or the repository root.

### Direct usage

`generate.py` is the underlying command:

```sh
python3 generate.py --arch riscv --udb-repo ../riscv-unified-db \
  --output build-riscv --clean
```

Options include `--tarballs-dir`, `--spec-dir`, `--overlay-dir`,
`--cheriot-repo`, `--base-url`, `--pagefind` and `--version`. Run
`python3 generate.py --help` for details.

`--base-url` prefixes root-relative links, CSS font URLs, the Pagefind component
path and `robots.txt`:

```sh
make riscv-git-cheriot-pagefind RISCV_BASE_URL=/riscv-ins-ref
```

## Deployment

`.github/workflows/pages.yml` builds the RISC-V site with CHERIoT on every push
to `main` and deploys `build-riscv/` to GitHub Pages. The workflow clones both
source repositories, generates the resolved specification, builds the site with
Pagefind, and uses the repository name as the base URL. Select **GitHub Actions**
as the Pages source.

## Output

```text
build/
  index.html
  robots.txt
  latest_aarch64/    # instructions, listings, SVG diagrams
  latest_sysreg/     # registers, system instructions, listings
  static/            # CSS, fonts, Pagefind bootstrap
  pagefind/          # component UI and optional search index

build-riscv/
  index.html
  robots.txt
  latest_riscv/
    index.html       # all instructions
    csrindex.html    # all CSRs
    extindex.html    # all extensions
    insn/<name>.html
    csr/<name>.html
    ext/<name>.html
  static/            # shared CSS, fonts and riscv.css
  pagefind/
```

Both trees are plain static files and can be served by any web server.
Pagefind indexes the content pages only. The home and listing pages are excluded
so they don't crowd out individual entries.

On the RISC-V site, the instruction, CSR and extension listings have a
client-side extension filter. Selections persist in `localStorage` and in the
`ext` query parameter, so they survive navigation and can be shared.

## How it works

The Arm pipeline uses Arm's own XHTML pages as the source markup.
`archive.py` selects and extracts the bundles, `arm_isa.py` and `arm_sysreg.py`
choose the pages, `html_transform.py` strips Arm's chrome and adds Pagefind
attributes, `indexes.py` runs Arm's XSLT indexes, and `site.py` writes the tree.

The RISC-V pipeline starts from YAML. `riscv_archive.py` extracts the resolved
specification, `riscv_spec.py` loads the objects and any overlays,
`riscv_render.py` builds the page markup, and `riscv_site.py` writes the tree.
`cheriot.py` parses `src/cheri_insts.sail`, applies the official CHERI aliases
and the `ct.` vendor prefix, and adds the `Xcheriot` extension.
`render.py` and `templates/` supply the shell shared by both pipelines.

The Arm build reproduces the published `2026-09` site byte-for-byte: 2,315
instruction pages, 1,394 register pages and six listings. Older `_md` bundles
produce version drift because they contain earlier architecture data.

## Repository layout

```text
generate.py              CLI entry point
Makefile                 Build, test and preview targets
refsite/
  archive.py             Arm bundle discovery and extraction
  arm_isa.py             A64 instruction selection
  arm_sysreg.py          Register selection and link closure
  html_transform.py      Arm XHTML transformations
  indexes.py             Arm XSLT listings
  site.py                Arm build orchestration
  riscv_archive.py       RISC-V bundle discovery and extraction
  riscv_spec.py          RISC-V YAML model and overlays
  riscv_render.py        RISC-V page markup
  riscv_site.py          RISC-V build orchestration
  cheriot.py             CHERIoT Sail loader
  render.py              Jinja rendering helpers
  output.py              Shared output and asset helpers
  model.py               Page and BuildStats types
  pagefind.py            Pagefind invocation
templates/               Jinja templates and chrome
static/                  CSS, fonts and Pagefind bootstrap
riscv/                   RISC-V stylesheet
pagefind/                Pagefind component UI
tests/                   Unit tests
```

Tarballs, build output and extraction caches are ignored by Git.

## Troubleshooting

**No Arm bundle**: put both `ISA_A64_xml_A_profile-*.tar.gz` and
`SysReg_xml_A_profile-*.tar.gz` in `tarballs/`, or set `TARBALLS_DIR`.

**Mismatched Arm releases**: download both bundles for the same `YYYY-MM`.

**`not gzip-compressed`**: recompress the SysReg tar as shown above.

**No RISC-V bundle**: download `resolved_spec.tar.gz` into `tarballs/`, or set
`TARBALLS_DIR`.

**`no resolved specification found`**: the archive must contain
`gen/resolved_spec/_/` with `index.yaml` and a sibling `inst/` directory.

**No Pagefind index**: install the Pagefind CLI or Node.js with `npx`. The site
still builds without Pagefind; only search is unavailable.
