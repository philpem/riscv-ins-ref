"""Optional Pagefind index generation."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class PagefindError(RuntimeError):
    pass


def run_pagefind(site_dir: str | Path) -> None:
    """Run the Pagefind CLI against *site_dir*.

    Pagefind's generated index is not vendored in this repository; it is
    produced as a post-build step.  ``npx`` is used so no global install is
    required.
    """

    site_dir = Path(site_dir)
    if shutil.which("pagefind"):
        command = ["pagefind", "--site", str(site_dir)]
    elif shutil.which("npx"):
        command = ["npx", "--yes", "pagefind", "--site", str(site_dir)]
    else:
        raise PagefindError("neither 'pagefind' nor 'npx' is available")
    try:
        subprocess.run(command, check=True, timeout=600)
    except subprocess.CalledProcessError as error:
        raise PagefindError(f"{command[0]} exited with status {error.returncode}") from error
    except subprocess.TimeoutExpired as error:
        raise PagefindError(f"{command[0]} timed out after 600 seconds") from error
    except OSError as error:
        raise PagefindError(f"could not run {command[0]}: {error}") from error
