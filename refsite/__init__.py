"""Reusable static-site generator for architecture reference manuals.

The ARM-specific adapters live in :mod:`refsite.arm_isa`,
:mod:`refsite.arm_sysreg`, and :mod:`refsite.indexes`.  The shell, chrome and
listing templates are intentionally architecture-neutral so a second adapter
(for example RISC-V) can reuse them.
"""

__all__ = ["archive", "arm_isa", "arm_sysreg", "html_transform", "indexes", "model", "pagefind", "render", "site"]
