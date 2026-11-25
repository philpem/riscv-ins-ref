"""Render RISC-V instruction, CSR and extension pages as HTML fragments.

The Unified Database provides structured YAML rather than pre-rendered HTML, so
this module owns the content markup.  It emits the same kind of body fragments
as the ARM adapters (an ``<h1>`` followed by sections) and leaves the document
shell, navigation and search wiring to the shared templates.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from .html_transform import escape_attribute, escape_text
from .riscv_spec import Csr, CsrField, Encoding, Extension, Instruction, Spec, parse_location_ranges

ACCESS_ORDER = ("m", "s", "u", "vs", "vu")


def _text(value: object) -> str:
    return escape_text(str(value))


def _attr(value: object) -> str:
    return escape_attribute(str(value))


_ERB_RE = re.compile(r"<%.*?%>", re.DOTALL)
_BLOCK_DELIMITER_RE = re.compile(r"^(?:\|===|!===|,===|={3,}|-{4,}|\.{4,})$")
_ATTRIBUTE_LINE_RE = re.compile(r"^\[[^\]]*\]$")
_ANCHOR_RE = re.compile(r"\[\[[^\]]*\]\]")
_INDEX_MARK_RE = re.compile(r"\(\(\((.*?)\)\)\)")
_LATEX_RE = re.compile(r"latexmath:\[(.*?)\]")
_LINK_RE = re.compile(r"link:([^\[]+)\[([^\]]*)\]")
_IMAGE_RE = re.compile(r"image:[^\[]+\[[^\]]*\]")


def clean_description(value: str) -> str:
    """Strip the AsciiDoc and ERB scaffolding that the Unified Database keeps.

    The resolved specification stores the ISA manual prose verbatim, including
    AsciiDoc attribute lines, anchors, table delimiters and ERB conditionals.
    None of that is meaningful in the generated HTML, so remove the scaffolding
    while keeping the readable text.
    """

    text = _ERB_RE.sub("", value)
    text = _ANCHOR_RE.sub("", text)
    text = _IMAGE_RE.sub("", text)
    text = _LATEX_RE.sub(r"\1", text)
    text = _LINK_RE.sub(lambda match: match.group(2) or match.group(1), text)
    text = _INDEX_MARK_RE.sub(r"\1", text)
    text = re.sub(
        r"\[(NOTE|TIP|WARNING|IMPORTANT|CAUTION)\]",
        lambda match: match.group(1).capitalize() + ":",
        text,
    )

    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if _BLOCK_DELIMITER_RE.fullmatch(stripped):
            continue
        if stripped.startswith("//"):
            continue
        if _ATTRIBUTE_LINE_RE.fullmatch(stripped):
            if stripped.upper().startswith("[NOTE]"):
                lines.append("Note:")
            continue
        heading = re.fullmatch(r"=+\s+(.*)", stripped)
        if heading:
            lines.append(heading.group(1))
            continue
        if stripped.startswith("|"):
            cells = [
                cell.strip()
                for cell in stripped.strip("|").split("|")
                if cell.strip() and not re.fullmatch(r"-+", cell.strip())
            ]
            if cells:
                lines.append(" — ".join(cells))
            continue
        lines.append(line)
    return "\n".join(lines)


def _summary(long_name: str, description: str) -> str:
    return long_name or clean_description(description).split("\n", 1)[0]


def paragraphs(value: str) -> str:
    """Turn a plain-text block into escaped ``<p>`` elements."""

    value = clean_description(value)
    blocks = [block.strip() for block in re.split(r"\n\s*\n", value.strip()) if block.strip()]
    return "\n".join(
        "<p>" + _text(re.sub(r"\s*\n\s*", " ", block)) + "</p>" for block in blocks
    )


def _pre(value: str, css_class: str = "pseudocode", *, pagefind: bool = False) -> str:
    attribute = ' data-pagefind-body="1"' if pagefind else ""
    return f'<pre class="{css_class}"{attribute}>{_text(value)}</pre>'


def _format_location(value: str | None) -> str:
    if not value:
        return ""
    return ", ".join(
        f"[{hi}]" if hi == lo else f"[{hi}:{lo}]"
        for hi, lo in parse_location_ranges(value)
    )


def _bit_number_row(width: int, group: int = 1) -> str:
    cells: list[str] = []
    hi = width - 1
    while hi >= 0:
        lo = max(0, hi - group + 1)
        label = str(hi) if group == 1 else f"{hi}:{lo}"
        cells.append(f'<th colspan="{hi - lo + 1}">{label}</th>')
        hi = lo - 1
    return '<tr class="encoding-bitnumbers">' + "".join(cells) + "</tr>"


def _runs(width: int, labels: Mapping[int, tuple[str, str]]) -> list[tuple[str, str, int]]:
    """Group adjacent bit positions with the same (label, css class)."""

    runs: list[tuple[str, str, int]] = []
    bit = width - 1
    while bit >= 0:
        label, css_class = labels.get(bit, ("", "encoding-reserved"))
        span = 1
        while bit - span >= 0 and labels.get(bit - span, ("", "encoding-reserved")) == (
            label,
            css_class,
        ):
            span += 1
        runs.append((label, css_class, span))
        bit -= span
    return runs


def _bitfield_cell(label: str, css_class: str, span: int) -> str:
    if css_class == "encoding-fixed" and label:
        text = _text(label) * span
    else:
        text = _text(label) if label else "&mdash;"
    title = (
        f' title="{_attr(label)}"'
        if css_class == "encoding-variable" and label
        else ""
    )
    return f'<td colspan="{span}" class="{css_class}"{title}>{text}</td>'


def encoding_table(encoding: Encoding) -> str:
    """Render a fixed/variable bitfield diagram for one instruction encoding."""

    width = encoding.width
    if width <= 0:
        return ""
    labels: dict[int, tuple[str, str]] = {}
    for variable in encoding.variables:
        for bit in variable.bits:
            if 0 <= bit < width:
                labels[bit] = (variable.name, "encoding-variable")
    for index, char in enumerate(encoding.match):
        bit = width - 1 - index
        if char != "-":
            labels.setdefault(bit, (char, "encoding-fixed"))
    runs = _runs(width, labels)
    cells = "".join(_bitfield_cell(*run) for run in runs)
    return (
        '<table class="encoding-table" data-pagefind-body="1">'
        f"<thead>{_bit_number_row(width)}</thead>"
        f'<tbody><tr class="encoding-fields">{cells}</tr></tbody>'
        "</table>"
    )


def decode_table(encoding: Encoding, *, pagefind: bool = False) -> str:
    """Render the variable names and bit ranges for one encoding."""

    if not encoding.variables:
        return ""
    attribute = ' data-pagefind-body="1"' if pagefind else ""
    rows = "".join(
        "<tr>"
        f'<td><code>{_text(variable.name)}</code></td>'
        f"<td>{_format_location(variable.location_text())}</td>"
        f"<td>{variable.width}</td>"
        "</tr>"
        for variable in encoding.variables
    )
    return (
        f'<table class="decode-table"{attribute}><thead><tr>'
        "<th>Variable</th><th>Bits</th><th>Width</th>"
        "</tr></thead><tbody>"
        f"{rows}</tbody></table>"
    )


def access_table(access: Iterable[tuple[str, str]]) -> str:
    """Render the privilege-mode access table for one instruction."""

    values = dict(access)
    keys = [key for key in ACCESS_ORDER if key in values]
    keys.extend(key for key in values if key not in ACCESS_ORDER)
    if not keys:
        return ""
    header = "".join(f"<th>{_text(key.upper())}</th>" for key in keys)
    row = "".join(
        f"<td>{_text(str(values.get(key, '-')).capitalize())}</td>" for key in keys
    )
    return (
        '<table class="access-table"><thead><tr>'
        f"{header}</tr></thead><tbody><tr>{row}</tr></tbody></table>"
    )


def render_instruction(  # pylint: disable=too-many-branches,too-many-statements
    instruction: Instruction,
    *,
    known_extensions: set[str] | None = None,
    known_instructions: set[str] | None = None,
) -> tuple[str, str, str]:
    """Return ``(title, description, body_html)`` for one instruction."""

    known_extensions = known_extensions or set()
    known_instructions = known_instructions or set()
    title = instruction.name
    description = _summary(instruction.long_name, instruction.description)

    parts = [
        f'<h1 class="instruction-section" data-pagefind-body="1" data-pagefind-weight="10" '
        f'data-pagefind-sort="title:{_attr(title)}">{_text(title)}</h1>'
    ]
    if instruction.long_name:
        parts.append(
            f'<p class="insn_subtitle" data-pagefind-body="1">'
            f"{_text(instruction.long_name)}</p>"
        )
    if instruction.description:
        parts.append(f'<div data-pagefind-body="1">{paragraphs(instruction.description)}</div>')
    if instruction.data_independent_timing:
        parts.append(
            '<p class="timing-note">This instruction has data-independent execution timing.</p>'
        )

    parts.append("<h2>Assembly format</h2>")
    syntax = f"{instruction.name} {instruction.assembly}".strip()
    parts.append(_pre(syntax, pagefind=True))

    if instruction.encodings:
        parts.append("<h2>Encoding</h2>")
        for variant, encoding in instruction.encodings:
            if variant:
                parts.append(f"<h3>{_text(variant)}</h3>")
            table = encoding_table(encoding)
            if table:
                parts.append(table)

    variables = [
        variable
        for _, encoding in instruction.encodings
        for variable in encoding.variables
    ]
    if variables:
        parts.append("<h2>Decode variables</h2>")
        for variant, encoding in instruction.encodings:
            if variant:
                parts.append(f"<h3>{_text(variant)}</h3>")
            table = decode_table(encoding, pagefind=True)
            if table:
                parts.append(table)

    if instruction.operation:
        parts.append("<h2>Execution</h2>")
        parts.append(_pre(instruction.operation, pagefind=True))
    else:
        parts.append(
            '<p class="note">No execution pseudocode is available for this instruction.</p>'
        )

    if instruction.defined_by:
        parts.append("<h2>Defined by</h2>")
        parts.append(f"<p>{_text(instruction.defined_by)}</p>")
        if instruction.extension and instruction.extension in known_extensions:
            parts.append(
                '<p class="extension-link">'
                f'<a href="../ext/{_attr(instruction.extension)}.html">'
                f"{_text(instruction.extension)} extension</a></p>"
            )

    table = access_table(instruction.access)
    if table:
        parts.append("<h2>Access</h2>")
        parts.append(table)

    if instruction.hints:
        parts.append("<h2>Hints</h2>")
        parts.append("<ul>")
        for hint in instruction.hints:
            if hint in known_instructions:
                parts.append(f'<li><a href="{_attr(hint)}.html">{_text(hint)}</a></li>')
            else:
                parts.append(f"<li>{_text(hint)}</li>")
        parts.append("</ul>")

    if instruction.pseudoinstructions:
        parts.append("<h2>Pseudoinstructions</h2>")
        parts.append(
            '<table class="pseudo-table"><thead><tr>'
            "<th>When</th><th>Use</th></tr></thead><tbody>"
        )
        for when, to in instruction.pseudoinstructions:
            parts.append(f"<tr><td>{_text(when)}</td><td><code>{_text(to)}</code></td></tr>")
        parts.append("</tbody></table>")

    return title, description, "\n".join(parts)


def _csr_field_location(field: CsrField, mode: str | None) -> str | None:
    if mode == "rv32":
        return field.location_rv32 or field.location
    if mode == "rv64":
        return field.location_rv64 or field.location
    return field.location


def _csr_bitfield(fields: Iterable[CsrField], width: int, mode: str | None) -> str:
    labels: dict[int, tuple[str, str]] = {}
    for field in fields:
        location = _csr_field_location(field, mode)
        if not location:
            # Fields without a location (aliases, derived values) do not occupy
            # bits, so they should not suppress the diagram for the others.
            continue
        try:
            ranges = parse_location_ranges(location)
        except ValueError:
            return ""
        if all(hi < 0 or lo >= width for hi, lo in ranges):
            # This field is not present in this view (for example an RV64-only
            # field while drawing the RV32 diagram).
            continue
        if any(lo < 0 or hi >= width for hi, lo in ranges):
            return ""  # partially outside the view: a diagram would mislead
        for hi, lo in ranges:
            for bit in range(lo, hi + 1):
                if bit in labels:
                    return ""  # overlapping/aliased fields: a diagram would mislead
                labels[bit] = (field.name, "encoding-variable")
    if not labels:
        return ""
    runs = _runs(width, labels)
    cells = "".join(_bitfield_cell(*run) for run in runs)
    return (
        '<table class="encoding-table csr-bitfield">'
        f"<thead>{_bit_number_row(width, group=8)}</thead>"
        f'<tbody><tr class="encoding-fields">{cells}</tr></tbody>'
        "</table>"
    )


def _field_value(value: str) -> str:
    if not value:
        return ""
    if "\n" in value or len(value) > 40 or "{" in value or ";" in value:
        return f'<pre class="field-code">{_text(value)}</pre>'
    return f"<code>{_text(value)}</code>"


def _csr_field_rows(csr: Csr) -> str:
    rows: list[str] = []
    for field in csr.fields:
        if field.location_rv32 or field.location_rv64:
            bits = []
            if field.location_rv32:
                bits.append(f"RV32 {_format_location(field.location_rv32)}")
            if field.location_rv64:
                bits.append(f"RV64 {_format_location(field.location_rv64)}")
            bits_text = "<br>".join(bits)
        else:
            bits_text = _format_location(field.location)
        detail = clean_description(field.description or field.long_name)
        rows.append(
            "<tr>"
            f'<td class="field-bits">{bits_text}</td>'
            f"<td><code>{_text(field.name)}</code></td>"
            f"<td>{_field_value(field.alias or '')}</td>"
            f"<td>{_text(detail)}</td>"
            f"<td>{_field_value(field.type_text)}</td>"
            f"<td>{_field_value(field.reset_text)}</td>"
            "</tr>"
        )
    return "".join(rows)


def render_csr(csr: Csr) -> tuple[str, str, str]:  # pylint: disable=too-many-branches
    """Return ``(title, description, body_html)`` for one CSR."""

    title = csr.name
    description = _summary(csr.long_name, csr.description)
    parts = [
        f'<h1 class="register-section" data-pagefind-body="1" data-pagefind-weight="10" '
        f'data-pagefind-sort="title:{_attr(title)}">{_text(title)}</h1>'
    ]
    if csr.long_name:
        parts.append(f'<p class="insn_subtitle" data-pagefind-body="1">{_text(csr.long_name)}</p>')

    metadata = []
    if csr.address is not None:
        metadata.append(f"Address: <code>0x{csr.address:03X}</code> ({csr.address})")
    if csr.priv_mode:
        metadata.append(f"Privilege: {_text(csr.priv_mode)}")
    if csr.length:
        metadata.append(f"Length: {_text(csr.length)}")
    metadata.append("Writable" if csr.writable else "Read-only")
    if csr.defined_by:
        metadata.append(f"Defined by: {_text(csr.defined_by)}")
    if csr.virtual_address:
        metadata.append(f"Virtual address: {_text(csr.virtual_address)}")
    if csr.indirect_address:
        metadata.append(f"Indirect address: {_text(csr.indirect_address)}")
    if csr.indirect_slot:
        metadata.append(f"Indirect slot: {_text(csr.indirect_slot)}")
    if metadata:
        parts.append(
            '<p class="csr-metadata" data-pagefind-body="1">'
            + " &middot; ".join(metadata)
            + "</p>"
        )

    if csr.description:
        parts.append('<div data-pagefind-body="1">' + paragraphs(csr.description) + "</div>")

    if csr.fields:
        parts.append("<h2>Fields</h2>")
        diagrams: list[str] = []
        if any(field.location_rv32 or field.location_rv64 for field in csr.fields):
            for mode, label, width in (("rv32", "RV32", 32), ("rv64", "RV64", 64)):
                diagram = _csr_bitfield(csr.fields, width, mode)
                if diagram:
                    diagrams.append(f"<h3>{label}</h3>{diagram}")
        elif csr.length.upper() in {"MXLEN", "SXLEN", "XLEN", "VSXLEN"}:
            for mode, label, width in (("rv32", "RV32", 32), ("rv64", "RV64", 64)):
                diagram = _csr_bitfield(csr.fields, width, mode)
                if diagram:
                    diagrams.append(f"<h3>{label}</h3>{diagram}")
        else:
            width = int(csr.length) if csr.length.isdigit() else 64
            diagram = _csr_bitfield(csr.fields, width, None)
            if diagram:
                diagrams.append(diagram)
        parts.extend(diagrams)
        parts.append(
            '<table class="fields-table" data-pagefind-body="1"><thead><tr>'
            "<th>Bits</th><th>Field</th><th>Alias</th><th>Description</th>"
            "<th>Type</th><th>Reset</th>"
            "</tr></thead><tbody>"
            + _csr_field_rows(csr)
            + "</tbody></table>"
        )

    if csr.sw_read:
        parts.append("<h2>Software read</h2>")
        parts.append(_pre(csr.sw_read, pagefind=True))

    return title, description, "\n".join(parts)


def render_extension(
    extension: Extension,
    *,
    instructions: Iterable[Instruction] = (),
    csrs: Iterable[Csr] = (),
) -> tuple[str, str, str]:
    """Return ``(title, description, body_html)`` for one extension."""

    title = extension.name
    description = _summary(extension.long_name, extension.description)
    parts = [
        f'<h1 class="extension-section" data-pagefind-body="1" data-pagefind-weight="10" '
        f'data-pagefind-sort="title:{_attr(title)}">{_text(title)}</h1>'
    ]
    if extension.long_name:
        parts.append(
            f'<p class="insn_subtitle" data-pagefind-body="1">'
            f"{_text(extension.long_name)}</p>"
        )
    if extension.type:
        parts.append(f'<p class="extension-type">Type: {_text(extension.type)}</p>')

    if extension.requirements:
        parts.append("<h2>Requirements</h2>")
        parts.append(f"<p>{_text(extension.requirements)}</p>")

    if extension.versions:
        parts.append("<h2>Versions</h2>")
        rows = "".join(
            "<tr>"
            f"<td>{_text(version.version)}</td>"
            f"<td>{_text(version.state)}</td>"
            f"<td>{_text(version.ratification_date)}</td>"
            "</tr>"
            for version in extension.versions
        )
        parts.append(
            '<table class="versions-table" data-pagefind-body="1"><thead><tr>'
            "<th>Version</th><th>State</th><th>Ratified</th>"
            "</tr></thead><tbody>"
            f"{rows}</tbody></table>"
        )

    if extension.description:
        parts.append("<h2>Description</h2>")
        parts.append('<div data-pagefind-body="1">' + paragraphs(extension.description) + "</div>")

    instruction_list = sorted(instructions, key=lambda item: item.name)
    if instruction_list:
        parts.append("<h2>Instructions</h2>")
        parts.append("<ul>")
        for instruction in instruction_list:
            label = instruction.long_name or instruction.name
            parts.append(
                f'<li><a href="../insn/{_attr(instruction.name)}.html">'
                f"<code>{_text(instruction.name)}</code></a> &mdash; {_text(label)}</li>"
            )
        parts.append("</ul>")

    csr_list = sorted(csrs, key=lambda item: item.name)
    if csr_list:
        parts.append("<h2>CSRs</h2>")
        parts.append("<ul>")
        for csr in csr_list:
            label = csr.long_name or csr.name
            parts.append(
                f'<li><a href="../csr/{_attr(csr.name)}.html">'
                f"<code>{_text(csr.name)}</code></a> &mdash; {_text(label)}</li>"
            )
        parts.append("</ul>")

    if not instruction_list and not csr_list:
        parts.append(
            "<p>No instructions or CSRs are directly attributed to this extension. "
            "It may be a category that is satisfied by other extensions.</p>"
        )

    return title, description, "\n".join(parts)


def instruction_listing(spec: Spec) -> str:
    """Render the alphabetic table of all instructions."""

    rows = "".join(
        "<tr>"
        f'<td><a href="insn/{_attr(item.name)}.html"><code>{_text(item.name)}</code></a></td>'
        f"<td>{_text(item.long_name)}</td>"
        f"<td>{_text(item.extension or item.defined_by)}</td>"
        "</tr>"
        for item in spec.instructions
    )
    return (
        '<table class="listing-table"><thead><tr>'
        "<th>Instruction</th><th>Summary</th><th>Extension</th>"
        "</tr></thead><tbody>"
        f"{rows}</tbody></table>"
    )


def csr_listing(spec: Spec) -> str:
    """Render the alphabetic table of all CSRs."""

    rows = "".join(
        "<tr>"
        f'<td><a href="csr/{_attr(item.name)}.html"><code>{_text(item.name)}</code></a></td>'
        f"<td>{_text(item.long_name)}</td>"
        f"<td>{f'0x{item.address:03X}' if item.address is not None else ''}</td>"
        f"<td>{_text(item.priv_mode)}</td>"
        "</tr>"
        for item in spec.csrs
    )
    return (
        '<table class="listing-table"><thead><tr>'
        "<th>CSR</th><th>Summary</th><th>Address</th><th>Privilege</th>"
        "</tr></thead><tbody>"
        f"{rows}</tbody></table>"
    )


def extension_listing(spec: Spec) -> str:
    """Render the table of all extensions and their versions."""

    rows = []
    for item in spec.extensions:
        versions = ", ".join(version.version for version in item.versions if version.version)
        rows.append(
            "<tr>"
            f'<td><a href="ext/{_attr(item.name)}.html"><code>{_text(item.name)}</code></a></td>'
            f"<td>{_text(item.long_name)}</td>"
            f"<td>{_text(item.type)}</td>"
            f"<td>{_text(versions)}</td>"
            "</tr>"
        )
    return (
        '<table class="listing-table"><thead><tr>'
        "<th>Extension</th><th>Summary</th><th>Type</th><th>Versions</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def extension_members(
    spec: Spec,
    extension: Extension,
    *,
    include_requirements: bool = True,
) -> tuple[list[Instruction], list[Csr]]:
    """Select the instructions and CSRs provided by *extension*.

    Direct membership uses the structured positive/negative extension sets, so
    an extension named under ``not`` is never listed.  Category extensions with
    no direct members inherit the members of the extensions they require.
    """

    return _extension_members(
        spec, extension, include_requirements=include_requirements, visited={extension.name}
    )


def _extension_members(
    spec: Spec,
    extension: Extension,
    *,
    include_requirements: bool,
    visited: set[str],
) -> tuple[list[Instruction], list[Csr]]:
    name = extension.name
    instructions = [
        item
        for item in spec.instructions
        if name in item.defined_by_extensions and name not in item.defined_by_excluded
    ]
    csrs = [
        item
        for item in spec.csrs
        if name in item.defined_by_extensions and name not in item.defined_by_excluded
    ]

    if include_requirements and not instructions and not csrs:
        for required in extension.required_extensions:
            if required in visited:
                continue
            visited.add(required)
            required_extension = spec.extension_map().get(required)
            if required_extension is None:
                continue
            sub_instructions, sub_csrs = _extension_members(
                spec,
                required_extension,
                include_requirements=True,
                visited=visited,
            )
            instructions.extend(sub_instructions)
            csrs.extend(sub_csrs)

    return _unique_by_name(instructions), _unique_by_name(csrs)


def _unique_by_name(items: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for item in items:
        if item.name not in seen:
            seen.add(item.name)
            result.append(item)
    return result
