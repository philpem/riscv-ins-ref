"""Load the RISC-V Unified Database resolved specification.

The Unified Database publishes a ``resolved_spec.tar.gz`` archive containing
the complete ISA database as YAML.  This module turns that archive's contents
into small, presentation-oriented dataclasses.  It is deliberately independent
of the ARM adapters: nothing here knows how the pages are rendered.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class SpecError(RuntimeError):
    """Raised when the resolved specification cannot be loaded."""


@dataclass(frozen=True)
class EncodingVariable:
    """One named field inside an instruction encoding.

    A field may occupy several disjoint bit ranges, which the Unified Database
    writes as e.g. ``31|7|30-25|11-8``.
    """

    name: str
    ranges: tuple[tuple[int, int], ...]

    @property
    def width(self) -> int:
        """Total number of bits covered by all ranges."""

        return sum(hi - lo + 1 for hi, lo in self.ranges)

    @property
    def bits(self) -> tuple[int, ...]:
        """Every bit position occupied by the variable, high to low."""

        return tuple(bit for hi, lo in self.ranges for bit in range(lo, hi + 1))

    def location_text(self) -> str:
        """Return the ranges in Unified Database ``hi-lo`` notation."""

        return "|".join(
            f"{hi}-{lo}" if hi != lo else str(hi) for hi, lo in self.ranges
        )


@dataclass(frozen=True)
class Encoding:
    """A fixed bit pattern plus the named variables carved out of it."""

    match: str
    variables: tuple[EncodingVariable, ...] = ()

    @property
    def width(self) -> int:
        """Instruction width in bits (16 for compressed instructions)."""

        return len(self.match)


@dataclass(frozen=True)
class Instruction:  # pylint: disable=too-many-instance-attributes
    """One instruction definition from the resolved specification."""
    name: str
    long_name: str
    description: str
    defined_by: str
    assembly: str
    encodings: tuple[tuple[str | None, Encoding], ...]
    access: tuple[tuple[str, str], ...]
    operation: str | None
    data_independent_timing: bool
    hints: tuple[str, ...]
    pseudoinstructions: tuple[tuple[str, str], ...]
    extension: str | None
    path: str
    defined_by_extensions: tuple[str, ...] = ()
    defined_by_excluded: tuple[str, ...] = ()


@dataclass(frozen=True)
class CsrField:  # pylint: disable=too-many-instance-attributes
    """One field within a CSR."""
    name: str
    long_name: str
    description: str
    location: str | None
    location_rv32: str | None
    location_rv64: str | None
    type_text: str
    reset_text: str
    alias: str | None


@dataclass(frozen=True)
class Csr:  # pylint: disable=too-many-instance-attributes
    """One control and status register definition."""
    name: str
    long_name: str
    address: int | None
    writable: bool
    description: str
    priv_mode: str
    length: str
    defined_by: str
    fields: tuple[CsrField, ...]
    sw_read: str | None
    virtual_address: str | None
    indirect_address: str | None
    indirect_slot: str | None
    path: str
    defined_by_extensions: tuple[str, ...] = ()
    defined_by_excluded: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtensionVersion:
    """One version entry for an extension."""
    version: str
    state: str
    ratification_date: str


@dataclass(frozen=True)
class Extension:  # pylint: disable=too-many-instance-attributes
    """One extension definition, including its version history."""
    name: str
    long_name: str
    type: str
    description: str
    versions: tuple[ExtensionVersion, ...]
    path: str
    requirements: str = ""
    required_extensions: tuple[str, ...] = ()


@dataclass
class Spec:
    """The complete set of objects loaded from one resolved specification."""

    instructions: list[Instruction] = field(default_factory=list)
    csrs: list[Csr] = field(default_factory=list)
    extensions: list[Extension] = field(default_factory=list)
    spec_dir: Path = Path(".")

    def instruction_map(self) -> dict[str, Instruction]:
        """Index instructions by name."""

        return {item.name: item for item in self.instructions}

    def csr_map(self) -> dict[str, Csr]:
        """Index CSRs by name."""

        return {item.name: item for item in self.csrs}

    def extension_map(self) -> dict[str, Extension]:
        """Index extensions by name."""

        return {item.name: item for item in self.extensions}


def find_spec_root(path: str | Path) -> Path:
    """Locate the directory containing ``index.yaml`` and the data folders."""

    path = Path(path)
    candidates = [
        path,
        path / "_",
        path / "gen" / "resolved_spec",
        path / "gen" / "resolved_spec" / "_",
        path / "resolved_spec",
        path / "resolved_spec" / "_",
    ]
    for candidate in candidates:
        if (candidate / "index.yaml").is_file() and (candidate / "inst").is_dir():
            return candidate
    for index in sorted(path.rglob("index.yaml")):
        if (index.parent / "inst").is_dir():
            return index.parent
    raise SpecError(f"no resolved specification found under {path}")


def load_spec(spec_dir: str | Path, overlay_dir: str | Path | None = None) -> Spec:
    """Load every instruction, CSR and extension from *spec_dir*.

    *overlay_dir* may contain additional or replacement ``inst/``, ``csr/``
    and ``ext/`` YAML trees.  Objects are matched by name, so an overlay file
    replaces a base file with the same name and otherwise appends to it.
    """

    root = find_spec_root(spec_dir)
    instructions: dict[str, Instruction] = {}
    csrs: dict[str, Csr] = {}
    extensions: dict[str, Extension] = {}

    for path in _yaml_paths(root):
        _load_object(path, instructions, csrs, extensions, replace=False)

    if overlay_dir is not None:
        overlay_root = Path(overlay_dir)
        if not overlay_root.is_dir():
            raise SpecError(f"overlay directory not found: {overlay_root}")
        overlay_resolved = overlay_root.resolve()
        overlay_names: set[tuple[str, str]] = set()
        for path in sorted(overlay_root.rglob("*.yaml")):
            if not path.resolve().is_relative_to(overlay_resolved):
                raise SpecError(f"overlay file escapes the overlay directory: {path}")
            kind, name = _load_object(path, instructions, csrs, extensions, replace=True)
            if kind not in {"instruction", "csr", "extension"}:
                raise SpecError(f"unsupported overlay kind {kind!r} in {path}")
            key = (kind, name)
            if key in overlay_names:
                raise SpecError(f"duplicate overlay {kind} name {name!r} in {path}")
            overlay_names.add(key)

    if not instructions and not csrs and not extensions:
        raise SpecError(f"no specification objects found under {root}")

    return Spec(
        instructions=sorted(instructions.values(), key=lambda item: item.name),
        csrs=sorted(csrs.values(), key=lambda item: item.name),
        extensions=sorted(extensions.values(), key=lambda item: item.name),
        spec_dir=root,
    )


def _load_object(
    path: Path,
    instructions: dict[str, Instruction],
    csrs: dict[str, Csr],
    extensions: dict[str, Extension],
    *,
    replace: bool,
) -> tuple[str, str]:
    """Load one YAML document into the appropriate mapping.

    Returns ``(kind, name)`` so overlay callers can detect duplicates.  Base
    documents must be unique; overlay documents intentionally replace them.
    """

    data = _read_yaml(path)
    kind = data.get("kind")
    try:
        if kind == "instruction":
            instruction = _parse_instruction(data, path)
            _store(instructions, instruction, path, "instruction", replace)
            return kind, instruction.name
        if kind == "csr":
            csr = _parse_csr(data, path)
            _store(csrs, csr, path, "CSR", replace)
            return kind, csr.name
        if kind == "extension":
            extension = _parse_extension(data, path)
            _store(extensions, extension, path, "extension", replace)
            return kind, extension.name
    except ValueError as error:
        raise SpecError(f"invalid {kind} in {path}: {error}") from error
    return (str(kind) if kind else ""), ""


def _store(
    mapping: dict[str, Any],
    item: Any,
    path: Path,
    kind: str,
    replace: bool,
) -> None:
    existing = mapping.get(item.name)
    if existing is not None and not replace:
        raise SpecError(
            f"duplicate {kind} name {item.name!r} in {path} and {existing.path}"
        )
    mapping[item.name] = item


def describe_defined_by(  # pylint: disable=too-many-return-statements,too-many-branches
    node: Any,
) -> str:
    """Render a ``definedBy`` expression as readable text."""

    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return " and ".join(filter(None, (describe_defined_by(item) for item in node)))
    if not isinstance(node, dict):
        return str(node)
    if "not" in node:
        return "not " + _parenthesise_any(describe_defined_by(node["not"]))
    if "extension" in node:
        return describe_defined_by(node["extension"])
    if "name" in node:
        name = str(node["name"])
        version = node.get("version")
        return f"{name} ({version})" if version else name
    if "xlen" in node:
        return f"RV{node['xlen']}"
    if "allOf" in node:
        parts = [
            _parenthesise(describe_defined_by(item), " or ")
            for item in _as_list(node["allOf"])
        ]
        return " and ".join(filter(None, parts))
    if "anyOf" in node:
        parts = [
            _parenthesise(describe_defined_by(item), " and ")
            for item in _as_list(node["anyOf"])
        ]
        return " or ".join(filter(None, parts))
    if "oneOf" in node:
        parts = [
            _parenthesise_any(describe_defined_by(item))
            for item in _as_list(node["oneOf"])
        ]
        return "one of " + ", ".join(filter(None, parts))
    if "param" in node:
        return _describe_param(node["param"])
    if "if" in node and "then" in node:
        return (
            f"if {describe_defined_by(node['if'])} "
            f"then {describe_defined_by(node['then'])}"
        )
    # Unknown shape: keep it readable rather than failing the whole build.
    parts = [
        f"{key}: {describe_defined_by(value)}"
        for key, value in node.items()
        if key not in {"$source", "idl()", "idl_ast"}
    ]
    return ", ".join(parts)


def _describe_param(node: Any) -> str:
    if not isinstance(node, dict):
        return f"parameter {node}"
    name = str(node.get("name", "parameter"))
    for key, operator in (
        ("greaterThanOrEqual", ">="),
        ("greaterThan", ">"),
        ("lessThanOrEqual", "<="),
        ("lessThan", "<"),
        ("notEqual", "!="),
        ("equal", "=="),
        ("includes", "includes"),
    ):
        if key in node:
            return f"{name} {operator} {node[key]}"
    return name


def _parenthesise(text: str, operator: str) -> str:
    return f"({text})" if operator in text else text


def _parenthesise_any(text: str) -> str:
    if text.startswith("not ") or " and " in text or " or " in text:
        return f"({text})"
    return text


def _extension_sets(
    node: Any,
    *,
    negated: bool = False,
    positive: set[str] | None = None,
    negative: set[str] | None = None,
) -> tuple[set[str], set[str]]:
    """Collect extensions named in a ``definedBy``/``requirements`` tree.

    Extensions under a ``not`` are returned separately so callers can exclude
    them from membership rather than listing an instruction under a feature it
    explicitly does not require.
    """

    if positive is None:
        positive = set()
    if negative is None:
        negative = set()
    if isinstance(node, list):
        for item in node:
            _extension_sets(
                item, negated=negated, positive=positive, negative=negative
            )
        return positive, negative
    if not isinstance(node, dict):
        return positive, negative
    if "not" in node:
        _extension_sets(
            node["not"], negated=not negated, positive=positive, negative=negative
        )
    elif "extension" in node:
        _extension_sets(
            node["extension"], negated=negated, positive=positive, negative=negative
        )
    elif "name" in node:
        (negative if negated else positive).add(str(node["name"]))
    else:
        for key in ("allOf", "anyOf", "oneOf"):
            if key in node:
                for item in _as_list(node[key]):
                    _extension_sets(
                        item,
                        negated=negated,
                        positive=positive,
                        negative=negative,
                    )
    return positive, negative


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


def _first_extension(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    if "not" in node:
        return None
    if "extension" in node:
        return _first_extension(node["extension"])
    if "name" in node and isinstance(node["name"], str):
        return node["name"]
    for key in ("allOf", "anyOf", "oneOf"):
        if key in node:
            for item in _as_list(node[key]):
                found = _first_extension(item)
                if found:
                    return found
    return None


def _yaml_paths(root: Path) -> Iterable[Path]:
    index = root / "index.yaml"
    root_resolved = root.resolve()
    if index.is_file():
        try:
            entries = yaml.safe_load(index.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise SpecError(f"could not read {index}: {error}") from error
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, str):
                    continue
                candidate = (root / entry).resolve()
                if not candidate.is_relative_to(root_resolved):
                    raise SpecError(f"index entry escapes the specification: {entry}")
                if candidate.suffix == ".yaml":
                    if not candidate.is_file():
                        raise SpecError(f"index entry not found: {entry}")
                    yield candidate
            return
    for path in sorted(root.rglob("*.yaml")):
        if path.name == "index.yaml":
            continue
        if not path.resolve().is_relative_to(root_resolved):
            raise SpecError(f"specification file escapes the spec directory: {path}")
        yield path


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise SpecError(f"could not read {path}: {error}") from error
    if not isinstance(data, dict):
        raise SpecError(f"expected a mapping in {path}")
    return data


def _parse_instruction(data: dict[str, Any], path: Path) -> Instruction:
    encodings = _parse_encodings(data.get("encoding"))
    hints = tuple(
        name
        for item in _as_list(data.get("hints", []))
        if (name := _reference_name(item)) is not None
    )
    pseudo = tuple(
        (_text_value(item.get("when")), _text_value(item.get("to")))
        for item in _as_list(data.get("pseudoinstructions", []))
        if isinstance(item, dict)
    )
    access = data.get("access")
    access_items = (
        tuple(sorted((str(key), _text_value(value)) for key, value in access.items()))
        if isinstance(access, dict)
        else ()
    )
    positive, negative = _extension_sets(data.get("definedBy"))
    return Instruction(
        name=_object_name(data, path),
        long_name=_text_value(data.get("long_name")),
        description=_text_value(data.get("description")),
        defined_by=describe_defined_by(data.get("definedBy")),
        assembly=_text_value(data.get("assembly")),
        encodings=encodings,
        access=access_items,
        operation=_optional_text(data.get("operation()")),
        data_independent_timing=_bool_value(data.get("data_independent_timing", False)),
        hints=hints,
        pseudoinstructions=pseudo,
        extension=_first_extension(data.get("definedBy")),
        path=str(path),
        defined_by_extensions=tuple(sorted(positive)),
        defined_by_excluded=tuple(sorted(negative)),
    )


def _parse_encodings(value: Any) -> tuple[tuple[str | None, Encoding], ...]:
    if not isinstance(value, dict):
        return ()
    if "match" in value:
        return ((None, _parse_encoding(value)),)
    encodings: list[tuple[str | None, Encoding]] = []
    for variant in ("RV32", "RV64"):
        if isinstance(value.get(variant), dict):
            encodings.append((variant, _parse_encoding(value[variant])))
    return tuple(encodings)


def _parse_encoding(value: dict[str, Any]) -> Encoding:
    variables: list[EncodingVariable] = []
    for item in _as_list(value.get("variables", [])):
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        location = item.get("location")
        if name is None or location is None:
            continue
        ranges = parse_location_ranges(location)
        if not ranges:
            raise ValueError(f"variable {name!r} has an empty location")
        variables.append(EncodingVariable(name=str(name), ranges=ranges))
    match = str(value.get("match", ""))
    if len(match) > 4096:
        raise ValueError(f"encoding is unreasonably wide: {len(match)} bits")
    seen_bits: dict[int, str] = {}
    for variable in variables:
        for bit in variable.bits:
            if bit >= len(match) or bit < 0:
                raise ValueError(
                    f"variable {variable.name!r} lies outside the {len(match)}-bit encoding"
                )
            if bit in seen_bits:
                raise ValueError(
                    f"variables {seen_bits[bit]!r} and {variable.name!r} overlap at bit {bit}"
                )
            seen_bits[bit] = variable.name
    return Encoding(match=match, variables=tuple(variables))


def parse_location_ranges(value: Any) -> tuple[tuple[int, int], ...]:
    """Parse a Unified Database location such as ``24-20`` or ``12|6-4``."""

    ranges: list[tuple[int, int]] = []
    for part in str(value).strip().split("|"):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            hi_text, lo_text = part.split("-", 1)
        else:
            hi_text = lo_text = part
        hi, lo = int(hi_text), int(lo_text)
        if lo < 0 or hi < lo:
            raise ValueError(f"invalid bit range: {part}")
        if hi > 4095:
            raise ValueError(f"bit range is unreasonably large: {part}")
        ranges.append((hi, lo))
    return tuple(ranges)


def _parse_csr(data: dict[str, Any], path: Path) -> Csr:
    raw_fields = data.get("fields")
    fields: list[CsrField] = []
    if isinstance(raw_fields, dict):
        for name, raw in raw_fields.items():
            if not isinstance(raw, dict):
                continue
            for key in ("location", "location_rv32", "location_rv64"):
                if raw.get(key) is not None:
                    parse_location_ranges(raw[key])
            fields.append(
                CsrField(
                    name=str(name),
                    long_name=str(raw.get("long_name", "")),
                    description=str(raw.get("description", "")),
                    location=_optional_text(raw.get("location")),
                    location_rv32=_optional_text(raw.get("location_rv32")),
                    location_rv64=_optional_text(raw.get("location_rv64")),
                    type_text=_optional_text(raw.get("type()", raw.get("type"))) or "",
                    reset_text=_optional_text(
                        raw.get("reset_value()", raw.get("reset_value"))
                    )
                    or "",
                    alias=_optional_text(raw.get("alias")),
                )
            )
    length = data.get("length", "MXLEN")
    length_text = _text_value(length) or "MXLEN"
    if length_text.isdigit() and int(length_text) > 4096:
        raise ValueError(f"CSR length is unreasonably large: {length_text}")
    positive, negative = _extension_sets(data.get("definedBy"))
    return Csr(
        name=_object_name(data, path),
        long_name=_text_value(data.get("long_name")),
        address=_optional_int(data.get("address")),
        writable=_bool_value(data.get("writable", False)),
        description=_text_value(data.get("description")),
        priv_mode=_text_value(data.get("priv_mode")),
        length=length_text,
        defined_by=describe_defined_by(data.get("definedBy")),
        fields=tuple(fields),
        sw_read=_optional_text(data.get("sw_read()")),
        virtual_address=_optional_text(data.get("virtual_address")),
        indirect_address=_optional_text(data.get("indirect_address")),
        indirect_slot=_optional_text(data.get("indirect_slot")),
        path=str(path),
        defined_by_extensions=tuple(sorted(positive)),
        defined_by_excluded=tuple(sorted(negative)),
    )


def _parse_extension(data: dict[str, Any], path: Path) -> Extension:
    versions = []
    for raw in _as_list(data.get("versions", [])):
        if not isinstance(raw, dict):
            continue
        versions.append(
            ExtensionVersion(
                version=str(raw.get("version", "")),
                state=str(raw.get("state", "")),
                ratification_date=str(raw.get("ratification_date", "")),
            )
        )
    positive, _ = _extension_sets(data.get("requirements"))
    return Extension(
        name=_object_name(data, path),
        long_name=_text_value(data.get("long_name")),
        type=_text_value(data.get("type")),
        description=_text_value(data.get("description")),
        versions=tuple(versions),
        path=str(path),
        requirements=describe_defined_by(data.get("requirements")),
        required_extensions=tuple(sorted(positive)),
    )


def _reference_name(item: Any) -> str | None:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return None
    reference = item.get("$ref")
    if not isinstance(reference, str):
        return None
    name = reference.split("#", 1)[0].rsplit("/", 1)[-1]
    return name[:-5] if name.endswith(".yaml") else name


def _object_name(data: dict[str, Any], path: Path) -> str:
    """Return a name that is safe to use as a single output path component."""

    raw = data.get("name")
    name = path.stem if raw is None else str(raw)
    if not _NAME_RE.fullmatch(name):
        raise SpecError(
            f"invalid object name {name!r} in {path}; "
            "names must be URL-safe and contain no path separators"
        )
    return name


def _text_value(value: Any) -> str:
    return "" if value is None else str(value)


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return bool(value)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).rstrip("\n")


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
