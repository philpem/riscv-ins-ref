PYTHON ?= python3
TARBALLS_DIR ?= tarballs
BUILD_DIR ?= build
CACHE_DIR ?= .cache/armref
VERSION ?=

GEN_ARGS = --tarballs-dir "$(TARBALLS_DIR)" --output "$(BUILD_DIR)" --work-dir "$(CACHE_DIR)" --clean
ifneq ($(strip $(VERSION)),)
GEN_ARGS += --version "$(VERSION)"
endif

.DEFAULT_GOAL := all

.PHONY: all build check-tarballs check-clean-dirs pagefind serve test check clean install-deps help

all: build

build: check-tarballs
	$(PYTHON) generate.py $(GEN_ARGS)

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

check-clean-dirs:
	@$(PYTHON) -c 'import pathlib, sys; \
	root = pathlib.Path(".").resolve(); \
	home = pathlib.Path.home().resolve(); \
	bad = {pathlib.Path("/"), home, root}; \
	paths = [pathlib.Path(value).resolve() for value in sys.argv[1:]]; \
	unsafe = [path for path in paths if path in bad or root.is_relative_to(path)]; \
	sys.exit("refusing to remove unsafe path: " + ", ".join(map(str, unsafe))) if unsafe else None' \
		"$(BUILD_DIR)" "$(CACHE_DIR)"

pagefind:
	$(PYTHON) generate.py $(GEN_ARGS) --pagefind

serve: build
	$(PYTHON) -m http.server --directory "$(BUILD_DIR)" 8000

test:
	$(PYTHON) -m unittest discover -s tests -v

check:
	$(PYTHON) -m compileall -q generate.py refsite tests
	$(PYTHON) -m unittest discover -s tests -v

clean: check-clean-dirs
	rm -rf -- "$(BUILD_DIR)" "$(CACHE_DIR)"

install-deps:
	$(PYTHON) -m pip install -r requirements.txt

help:
	@printf '%s\n' \
		'Targets:' \
		'  make            Build the site into $(BUILD_DIR)' \
		'  make pagefind   Build the site and generate the Pagefind index' \
		'  make serve      Build, then serve $(BUILD_DIR) on port 8000' \
		'  make test       Run the unit tests' \
		'  make check      Compile and run the unit tests' \
		'  make clean      Remove the build and extraction caches' \
		'  make install-deps  Install Python dependencies' \
		'' \
		'Variables:' \
		'  TARBALLS_DIR=$(TARBALLS_DIR)' \
		'  BUILD_DIR=$(BUILD_DIR)' \
		'  CACHE_DIR=$(CACHE_DIR)' \
		'  VERSION=$(VERSION)'
