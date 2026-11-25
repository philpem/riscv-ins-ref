"""Reusable static-site generator for architecture reference manuals.

The ARM-specific adapters live in :mod:`refsite.arm_isa`,
:mod:`refsite.arm_sysreg`, and :mod:`refsite.indexes`.  The RISC-V adapters
live in :mod:`refsite.riscv_spec`, :mod:`refsite.riscv_render` and
:mod:`refsite.riscv_site`; :mod:`refsite.cheriot` adds the CHERIoT
capability instructions from the Sail model.  The shell, chrome and listing
templates are architecture-neutral and shared by both.
"""

__all__ = [
    "archive",
    "arm_isa",
    "arm_sysreg",
    "cheriot",
    "html_transform",
    "indexes",
    "model",
    "output",
    "pagefind",
    "render",
    "riscv_archive",
    "riscv_render",
    "riscv_site",
    "riscv_spec",
    "site",
]
