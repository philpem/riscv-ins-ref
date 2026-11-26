"""Load the CHERIoT capability instructions from the cheriot-sail model.

CHERIoT extends RISC-V with a capability instruction set that is implemented by
both CHERIoT Ibex and CHERIoT Kudu.  The authoritative encodings live in the
Sail model, so this module parses the ``mapping clause encdec`` statements in
``src/cheri_insts.sail`` rather than duplicating a hand-written table.
"""

from __future__ import annotations

import re
from pathlib import Path

from .riscv_spec import (
    Encoding,
    EncodingVariable,
    Extension,
    ExtensionVersion,
    Instruction,
    Spec,
)


class CheriotError(RuntimeError):
    """Raised when the CHERIoT Sail sources cannot be read or parsed."""


EXTENSION_NAME = "Xcheriot"
VENDOR_PREFIX = "ct."

_LABEL_RE = re.compile(r"\\insnriscvlabel\{([^}]+)\}")
_ALIAS_RE = re.compile(
    r"\\asm\{([^}]+)\}\s+is an alias for this instruction\."
)

# Constructor name -> (mnemonic, assembly operands).  The renderer prepends the
# mnemonic, so only the operand list is stored here.
_MNEMONICS: dict[str, tuple[str, str]] = {
    "AUICGP": ("auicgp", "cd, imm"),
    "AUIPCC": ("auipcc", "cd, imm"),
    "CJAL": ("cjal", "cd, imm"),
    "CJALR": ("cjalr", "cd, cs1, imm"),
    "CGetPerm": ("cgetperm", "rd, cs1"),
    "CGetType": ("cgettype", "rd, cs1"),
    "CGetBase": ("cgetbase", "rd, cs1"),
    "CGetLen": ("cgetlen", "rd, cs1"),
    "CGetTag": ("cgettag", "rd, cs1"),
    "CGetAddr": ("cgetaddr", "rd, cs1"),
    "CGetHigh": ("cgethigh", "rd, cs1"),
    "CGetTop": ("cgettop", "rd, cs1"),
    "CMove": ("cmove", "cd, cs1"),
    "CClearTag": ("ccleartag", "cd, cs1"),
    "CRRL": ("crrl", "rd, rs1"),
    "CRAM": ("cram", "rd, rs1"),
    "CSeal": ("cseal", "cd, cs1, cs2"),
    "CUnseal": ("cunseal", "cd, cs1, cs2"),
    "CAndPerm": ("candperm", "cd, cs1, rs2"),
    "CSetAddr": ("csetaddr", "cd, cs1, rs2"),
    "CSetHigh": ("csethigh", "cd, cs1, rs2"),
    "CIncAddr": ("cincaddr", "cd, cs1, rs2"),
    "CSetBounds": ("csetbounds", "cd, cs1, rs2"),
    "CSetBoundsExact": ("csetboundsexact", "cd, cs1, rs2"),
    "CSetBoundsRoundDown": ("csetboundsrounddown", "cd, cs1, rs2"),
    "CSub": ("csub", "rd, cs1, cs2"),
    "CTestSubset": ("ctestsubset", "rd, cs1, cs2"),
    "CSpecialRW": ("cspecialrw", "cd, scr, cs1"),
    "CIncAddrImmediate": ("cincaddrimm", "cd, cs1, imm"),
    "CSetBoundsImmediate": ("csetboundsimm", "cd, cs1, imm"),
    "CSEQX": ("cseqx", "rd, cs1, cs2"),
    "LoadCapImm": ("lc", "cd, offset(cs1)"),
    "StoreCapImm": ("sc", "cs2, offset(cs1)"),
}

_REGISTER_WIDTH = 5
_VARIABLE_WIDTHS = {
    "imm12": 12,
    "offset": 12,
    "off7": 7,
    "off5": 5,
}
# AUICGP/AUIPCC take a 20-bit immediate; CJALR takes a 12-bit one.
_IMMEDIATE_WIDTHS = {"AUICGP": 20, "AUIPCC": 20, "CJALR": 12}

_FALLBACK_DESCRIPTIONS = {
    "auicgp": (
        "Add a 20-bit immediate to the address of the current code capability "
        "and write the result to capability register cd."
    ),
    "auipcc": (
        "Add a 20-bit immediate to the address of the current code capability "
        "and write the result to capability register cd, preserving its tag."
    ),
    "crrl": (
        "Round an integer length up to the next length that a capability can "
        "represent, and write the result to rd."
    ),
    "cram": (
        "Return a mask that aligns an address to the representable alignment "
        "for a capability with the length in rs1."
    ),
    "candperm": (
        "Replace cd with cs1 after intersecting the permissions of cs1 with "
        "the integer in rs2."
    ),
    "csub": (
        "Subtract the address of cs2 from the address of cs1 and write the "
        "integer result to rd."
    ),
    "lc": (
        "Load a capability from memory at offset from the capability in cs1 "
        "into cd.  The tag is cleared if the address is out of bounds or the "
        "load is not aligned."
    ),
    "sc": (
        "Store the capability in cs2 to memory at offset from the capability "
        "in cs1.  The tag of cs2 is cleared if the store is out of bounds or "
        "not aligned."
    ),
}

_ENCDEC_RE = re.compile(
    r"mapping\s+clause\s+(?:encdec|encdec_capmode)\s*=\s*"
    r"(?P<ctor>\w+)\s*\((?P<args>[^)]*)\)"
    r"(?:\s+if\s*\(.*\))?\s*<->\s*(?P<rhs>.*?)\s*$",
    re.MULTILINE,
)
_DOC_RE = re.compile(r"/\*!(.*?)\*/", re.DOTALL)
_EXECUTE_RE = re.compile(
    r"function\s+clause\s+execute\s*\(?\s*(?P<name>\w+)\s*\("
)


def _clean_doc(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^\s*\*+\s?", "", line).rstrip()
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"2\^\{?\[?\{?xlen\}?\]?xlen\}?", "2^XLEN", text)
    text = text.replace("\\bmod", "mod").replace("\\ne", "!=").replace("~", " ")
    text = re.sub(r"\^\{([^{}]*)\}", r"^\1", text)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\[([A-Za-z0-9_.]+)\]", r"\1", text)
    text = re.sub(r"\$([^$]*)\$", lambda match: _latex(match.group(1)), text)
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", text).strip()


def _latex(value: str) -> str:
    replacements = {
        r"\lt": "<",
        r"\gt": ">",
        r"\le": "<=",
        r"\ge": ">=",
        r"\times": "x",
        r"\div": "/",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def _documentation(text: str) -> dict[str, str]:
    """Pair each ``function clause execute`` with the doc comment above it."""

    documents = [(match.end(), match.group(1)) for match in _DOC_RE.finditer(text)]
    functions = list(_EXECUTE_RE.finditer(text))
    result: dict[str, str] = {}
    for function in functions:
        preceding = [item for item in documents if item[0] <= function.start()]
        if not preceding:
            continue
        end, body = preceding[-1]
        if any(end <= other.start() < function.start() for other in functions):
            continue
        result[function.group("name")] = _clean_doc(body)
    return result


def _split_rhs(rhs: str) -> list[str]:
    rhs = re.sub(r"/\*.*?\*/", "", rhs)
    rhs = re.sub(r"\s+if\s*\(.*\)\s*$", "", rhs)
    return [token.strip() for token in rhs.split("@") if token.strip()]


def _token_width(token: str, ctor: str, unknown: list[str]) -> int:
    literal = re.fullmatch(r"0b([01]+)", token)
    if literal:
        return len(literal.group(1))
    sized = re.fullmatch(r"\w+\s*:\s*bits\((\d+)\)", token)
    if sized:
        return int(sized.group(1))
    name = token.strip()
    if name in {"rd", "cd", "cs1", "cs2", "rs1", "rs2", "scr"}:
        return _REGISTER_WIDTH
    if name in _VARIABLE_WIDTHS:
        return _VARIABLE_WIDTHS[name]
    if name == "imm" and ctor in _IMMEDIATE_WIDTHS:
        return _IMMEDIATE_WIDTHS[ctor]
    unknown.append(name)
    return 0


def _display_name(name: str, ctor: str) -> str:
    if ctor in {"LoadCapImm", "StoreCapImm"} and name == "rs1":
        return "cs1"
    if name.startswith("imm"):
        return "imm"
    if name in {"off7", "off5"}:
        return "offset"
    return name


def _merge_ranges(ranges: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    merged: list[tuple[int, int]] = []
    for hi, lo in sorted(ranges, reverse=True):
        if merged and hi == merged[-1][1] - 1:
            merged[-1] = (merged[-1][0], lo)
        else:
            merged.append((hi, lo))
    return tuple(merged)


def _encoding(ctor: str, rhs: str) -> Encoding:
    unknown: list[str] = []
    tokens = _split_rhs(rhs)
    widths = [_token_width(token, ctor, unknown) for token in tokens]
    if unknown:
        raise CheriotError(f"unknown CHERIoT encoding field(s) for {ctor}: {', '.join(unknown)}")

    position = 31
    match: list[str] = []
    ranges: dict[str, list[tuple[int, int]]] = {}
    for token, width in zip(tokens, widths):
        literal = re.fullmatch(r"0b([01]+)", token)
        if literal:
            match.append(literal.group(1))
        else:
            match.append("-" * width)
            name = re.sub(r"\s*:\s*bits\(\d+\)", "", token).strip()
            ranges.setdefault(_display_name(name, ctor), []).append(
                (position, position - width + 1)
            )
        position -= width

    if position != -1:
        raise CheriotError(f"CHERIoT encoding for {ctor} is {31 - position} bits, expected 32")

    variables = tuple(
        EncodingVariable(name, _merge_ranges(values))
        for name, values in ranges.items()
    )
    return Encoding(match="".join(match), variables=variables)


def _extension() -> Extension:
    return Extension(
        name=EXTENSION_NAME,
        long_name="CHERIoT capability instructions",
        type="unprivileged",
        description=(
            "CHERIoT extends RISC-V with capabilities: unforgeable references "
            "that carry bounds and permissions.  This is the CHERIoT 1.0 "
            "capability instruction set, implemented by both CHERIoT Ibex and "
            "CHERIoT Kudu.  Instruction mnemonics use the ct. vendor prefix "
            "allocated by the RISC-V Toolchain Conventions."
        ),
        versions=(ExtensionVersion("1.0", "ratified", ""),),
        path="cheriot:Xcheriot",
        requirements="",
        required_extensions=(),
    )


def _extra_instructions() -> list[Instruction]:
    """Return CHERIoT instructions that reuse standard RISC-V encodings.

    The Sail model does not list the capability word loads and stores because
    they share the standard ``LW`` and ``SW`` encodings; the capability check is
    applied to the base register.
    """

    load = Instruction(
        name="ct.clw",
        long_name="",
        description=(
            "Load a 32-bit word through a capability. The capability's tag and "
            "bounds are checked before the access."
        ),
        defined_by=EXTENSION_NAME,
        assembly="rd, offset(cs1)",
        encodings=(
            (
                None,
                Encoding(
                    match="-----------------010-----0000011",
                    variables=(
                        EncodingVariable("offset", ((31, 20),)),
                        EncodingVariable("cs1", ((19, 15),)),
                        EncodingVariable("rd", ((11, 7),)),
                    ),
                ),
            ),
        ),
        access=(("s", "always"), ("u", "always")),
        operation=None,
        data_independent_timing=False,
        hints=(),
        pseudoinstructions=(),
        extension=EXTENSION_NAME,
        path="cheriot:ct.clw",
        defined_by_extensions=(EXTENSION_NAME,),
    )
    store = Instruction(
        name="ct.csw",
        long_name="",
        description=(
            "Store a 32-bit word through a capability. The capability's tag and "
            "bounds are checked before the access."
        ),
        defined_by=EXTENSION_NAME,
        assembly="rs2, offset(cs1)",
        encodings=(
            (
                None,
                Encoding(
                    match="-----------------010-----0100011",
                    variables=(
                        EncodingVariable("offset", ((31, 25), (11, 7))),
                        EncodingVariable("rs2", ((24, 20),)),
                        EncodingVariable("cs1", ((19, 15),)),
                    ),
                ),
            ),
        ),
        access=(("s", "always"), ("u", "always")),
        operation=None,
        data_independent_timing=False,
        hints=(),
        pseudoinstructions=(),
        extension=EXTENSION_NAME,
        path="cheriot:ct.csw",
        defined_by_extensions=(EXTENSION_NAME,),
    )
    return [load, store]


def _alias_mnemonics(repo_root: Path) -> dict[str, str]:
    """Return CHERIoT mnemonic -> official CHERI mnemonic aliases.

    The CHERIoT per-instruction files record the names used by the wider CHERI
    ISA specification, for example ``CIncOffset`` for the instruction the Sail
    model calls ``CIncAddr``.
    """

    directory = repo_root / "archdoc" / "insn-riscv"
    if not directory.is_dir():
        return {}
    aliases: dict[str, str] = {}
    for path in sorted(directory.glob("*.tex")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            raise CheriotError(f"could not read {path}: {error}") from error
        label = _LABEL_RE.search(text)
        alias = _ALIAS_RE.search(text)
        if label and alias:
            aliases[label.group(1).lower()] = alias.group(1).lower()
    return aliases


def load_cheriot(  # pylint: disable=too-many-locals
    repo: str | Path,
) -> tuple[Extension, list[Instruction]]:
    """Parse ``src/cheri_insts.sail`` from a cheriot-sail checkout."""

    root = Path(repo)
    if root.is_file():
        source = root
        repo_root = root.parent.parent
    else:
        repo_root = root
        source = root / "src" / "cheri_insts.sail"
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as error:
        raise CheriotError(
            f"could not read the CHERIoT Sail model at {source}: {error}"
        ) from error

    aliases = _alias_mnemonics(repo_root)
    docs = _documentation(text)
    instructions: list[Instruction] = []
    seen: set[str] = set()
    for match in _ENCDEC_RE.finditer(text):
        ctor = match.group("ctor")
        if ctor not in _MNEMONICS:
            continue
        original_mnemonic, assembly = _MNEMONICS[ctor]
        mnemonic = VENDOR_PREFIX + aliases.get(original_mnemonic, original_mnemonic)
        if mnemonic in seen:
            raise CheriotError(f"duplicate CHERIoT instruction: {mnemonic}")
        seen.add(mnemonic)
        description = docs.get(ctor) or _FALLBACK_DESCRIPTIONS.get(original_mnemonic, "")
        if not description:
            raise CheriotError(f"no description for CHERIoT instruction: {mnemonic}")
        instructions.append(
            Instruction(
                name=mnemonic,
                long_name="",
                description=description,
                defined_by=EXTENSION_NAME,
                assembly=assembly,
                encodings=((None, _encoding(ctor, match.group("rhs"))),),
                access=(("s", "always"), ("u", "always")),
                operation=None,
                data_independent_timing=False,
                hints=(),
                pseudoinstructions=(),
                extension=EXTENSION_NAME,
                path=f"cheriot:{mnemonic}",
                defined_by_extensions=(EXTENSION_NAME,),
            )
        )

    for extra in _extra_instructions():
        if extra.name in seen:
            raise CheriotError(f"duplicate CHERIoT instruction: {extra.name}")
        seen.add(extra.name)
        instructions.append(extra)

    expected = {
        (VENDOR_PREFIX + aliases.get(name, name), operands)
        for name, operands in _MNEMONICS.values()
    }
    found = {(item.name, item.assembly) for item in instructions}
    absent = sorted(name for name, operands in expected if (name, operands) not in found)
    if absent:
        raise CheriotError(
            "the CHERIoT Sail model is missing expected instructions: " + ", ".join(absent)
        )

    instructions.sort(key=lambda item: item.name)
    return _extension(), instructions


def apply_cheriot(spec: Spec, repo: str | Path) -> None:
    """Add the CHERIoT extension and instructions to *spec* in place."""

    extension, instructions = load_cheriot(repo)
    names = {instruction.name for instruction in instructions}
    spec.instructions = [
        instruction for instruction in spec.instructions if instruction.name not in names
    ] + list(instructions)
    spec.instructions.sort(key=lambda item: item.name)
    spec.extensions = [
        item for item in spec.extensions if item.name != extension.name
    ] + [extension]
    spec.extensions.sort(key=lambda item: item.name)
