PYTHON ?= python3
TARBALLS_DIR ?= tarballs
BUILD_DIR ?= build
CACHE_DIR ?= .cache/armref
RISCV_BUILD_DIR ?= build-riscv
RISCV_CACHE_DIR ?= .cache/riscv
UDB_REPO ?= ../riscv-unified-db
VERSION ?=

GEN_ARGS = --tarballs-dir "$(TARBALLS_DIR)" --output "$(BUILD_DIR)" --work-dir "$(CACHE_DIR)" --clean
RISCV_GEN_ARGS = --arch riscv --tarballs-dir "$(TARBALLS_DIR)" --output "$(RISCV_BUILD_DIR)" --work-dir "$(RISCV_CACHE_DIR)" --clean
RISCV_GIT_ARGS = --arch riscv --udb-repo "$(UDB_REPO)" --output "$(RISCV_BUILD_DIR)" --work-dir "$(RISCV_CACHE_DIR)" --clean
ifneq ($(strip $(VERSION)),)
GEN_ARGS += --version "$(VERSION)"
RISCV_GEN_ARGS += --version "$(VERSION)"
endif

.DEFAULT_GOAL := all

.PHONY: all build riscv riscv-git riscv-clone riscv-resolve check-udb-repo check-tarballs check-tarballs-riscv check-clean-dirs pagefind riscv-pagefind serve serve-riscv test check clean install-deps help

all: build

build: check-tarballs
	$(PYTHON) generate.py $(GEN_ARGS)

riscv: check-tarballs-riscv
	$(PYTHON) generate.py $(RISCV_GEN_ARGS)

riscv-clone:
	@test -d "$(UDB_REPO)/.git" || git clone --depth 1 https://github.com/riscv/riscv-unified-db "$(UDB_REPO)"

riscv-resolve: riscv-clone
	cd "$(UDB_REPO)" && ./do gen:resolved_arch

check-udb-repo:
	@test -d "$(UDB_REPO)/gen/resolved_spec" || { \
		echo "error: no resolved specification in $(UDB_REPO)/gen/resolved_spec" >&2; \
		echo "Run 'make riscv-resolve UDB_REPO=...' in a UDB checkout with mise/Ruby available." >&2; \
		exit 1; \
	}

riscv-git: check-udb-repo
	$(PYTHON) generate.py $(RISCV_GIT_ARGS)

check-tarballs:
	@test -d "$(TARBALLS_DIR)" || { \
		echo "error: tarball directory not found: $(TARBALLS_DIR)" >&2; \
		echo "Download the two ARM bundles into it, or set TARBALLS_DIR=..." >&2; \
		exit 1; \
	}
	@test -n "$$(find "$(TARBALLS_DIR)" -maxdepth 1 -name 'ISA_A64_xml_A_profile-*.tar.gz' -print -quit)" || { \
		echo "error: no ISA_A64_xml_A_profile-*.tar.gz in $(TARBALLS_DIR)" >&2; \
		exit 1; \
	}
	@test -n "$$(find "$(TARBALLS_DIR)" -maxdepth 1 -name 'SysReg_xml_A_profile-*.tar.gz' -print -quit)" || { \
		echo "error: no SysReg_xml_A_profile-*.tar.gz in $(TARBALLS_DIR)" >&2; \
		exit 1; \
	}

check-tarballs-riscv:
	@test -d "$(TARBALLS_DIR)" || { \
		echo "error: tarball directory not found: $(TARBALLS_DIR)" >&2; \
		echo "Download resolved_spec.tar.gz into it, or set TARBALLS_DIR=..." >&2; \
		exit 1; \
	}
	@test -n "$$(find "$(TARBALLS_DIR)" -maxdepth 1 \( -name 'resolved_spec*.tar.gz' -o -name 'resolved_spec*.tgz' -o -name 'resolved_spec*.tar' \) -print -quit)" || { \
		echo "error: no resolved_spec*.tar.gz in $(TARBALLS_DIR)" >&2; \
		echo "Download it from https://riscv.github.io/riscv-unified-db/resolved_spec/resolved_spec.tar.gz" >&2; \
		exit 1; \
	}

check-clean-dirs:
	@$(PYTHON) -c 'import pathlib, sys; \
	root = pathlib.Path(".").resolve(); \
	home = pathlib.Path.home().resolve(); \
	bad = {pathlib.Path("/"), home, root}; \
	paths = [pathlib.Path(value).resolve() for value in sys.argv[1:]]; \
	unsafe = [path for path in paths if path in bad or root.is_relative_to(path)]; \
	sys.exit("refusing to remove unsafe path: " + ", ".join(map(str, unsafe))) if unsafe else None' \
		"$(BUILD_DIR)" "$(CACHE_DIR)" "$(RISCV_BUILD_DIR)" "$(RISCV_CACHE_DIR)"

pagefind:
	$(PYTHON) generate.py $(GEN_ARGS) --pagefind

riscv-pagefind:
	$(PYTHON) generate.py $(RISCV_GEN_ARGS) --pagefind

riscv-git-pagefind: check-udb-repo
	$(PYTHON) generate.py $(RISCV_GIT_ARGS) --pagefind

serve: build
	$(PYTHON) -m http.server --directory "$(BUILD_DIR)" 8000

serve-riscv: riscv
	$(PYTHON) -m http.server --directory "$(RISCV_BUILD_DIR)" 8000

test:
	$(PYTHON) -m unittest discover -s tests -v

check:
	$(PYTHON) -m compileall -q generate.py refsite tests
	$(PYTHON) -m unittest discover -s tests -v

clean: check-clean-dirs
	rm -rf -- "$(BUILD_DIR)" "$(CACHE_DIR)" "$(RISCV_BUILD_DIR)" "$(RISCV_CACHE_DIR)"

install-deps:
	$(PYTHON) -m pip install -r requirements.txt

help:
	@printf '%s\n' \
		'Targets:' \
		'  make            Build the ARM site into $(BUILD_DIR)' \
		'  make riscv      Build the RISC-V site into $(RISCV_BUILD_DIR)' \
		'  make riscv-git  Build RISC-V from $(UDB_REPO)/gen/resolved_spec' \
		'  make riscv-clone  Clone the Unified Database into $(UDB_REPO)' \
		'  make riscv-resolve  Run ./do gen:resolved_arch in $(UDB_REPO)' \
		'  make pagefind   Build the ARM site and generate the Pagefind index' \
		'  make riscv-pagefind  Build the RISC-V site and generate the Pagefind index' \
		'  make riscv-git-pagefind  Build from the UDB checkout and generate the Pagefind index' \
		'  make serve      Build, then serve $(BUILD_DIR) on port 8000' \
		'  make serve-riscv  Build, then serve $(RISCV_BUILD_DIR) on port 8000' \
		'  make test       Run the unit tests' \
		'  make check      Compile and run the unit tests' \
		'  make clean      Remove the build and extraction caches' \
		'  make install-deps  Install Python dependencies' \
		'' \
		'Variables:' \
		'  TARBALLS_DIR=$(TARBALLS_DIR)' \
		'  BUILD_DIR=$(BUILD_DIR)' \
		'  CACHE_DIR=$(CACHE_DIR)' \
		'  RISCV_BUILD_DIR=$(RISCV_BUILD_DIR)' \
		'  RISCV_CACHE_DIR=$(RISCV_CACHE_DIR)' \
		'  UDB_REPO=$(UDB_REPO)' \
		'  VERSION=$(VERSION)'
