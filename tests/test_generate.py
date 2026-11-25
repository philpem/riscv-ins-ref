"""Tests for the RISC-V CLI paths that do not use a tarball."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

import generate

HERE = Path(__file__).resolve().parent.parent

ADD_YAML = """\
kind: instruction
name: add
long_name: Integer add
description: Add two integers.
definedBy:
  extension:
    name: I
assembly: xd, xs1, xs2
encoding:
  match: '00000000000000000000000000000011'
  variables: []
access:
  s: always
operation(): |
  X[xd] = 1;
"""


def write_spec(root: Path) -> Path:
    spec = root / "resolved_spec" / "_"
    (spec / "inst" / "I").mkdir(parents=True)
    (spec / "index.yaml").write_text("- inst/I/add.yaml\n", encoding="utf-8")
    (spec / "inst" / "I" / "add.yaml").write_text(ADD_YAML, encoding="utf-8")
    return spec


class CliSourceTests(unittest.TestCase):
    def test_spec_dir_builds_without_a_tarball(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            spec = write_spec(base)
            output = base / "build"
            status = generate.main(
                [
                    "--arch",
                    "riscv",
                    "--spec-dir",
                    str(spec),
                    "--output",
                    str(output),
                    "--assets-dir",
                    str(HERE),
                    "--version",
                    "test",
                ]
            )
            self.assertEqual(status, 0)
            page = (output / "latest_riscv/insn/add.html").read_text(encoding="utf-8")
            self.assertIn("Version test", page)

    def test_udb_repo_uses_short_git_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = base / "udb"
            spec = write_spec(repo / "gen")
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.com",
                    "commit",
                    "-m",
                    "fixture",
                ],
                check=True,
                capture_output=True,
            )
            short = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            output = base / "build"
            status = generate.main(
                [
                    "--arch",
                    "riscv",
                    "--udb-repo",
                    str(repo),
                    "--output",
                    str(output),
                    "--assets-dir",
                    str(HERE),
                ]
            )
            self.assertEqual(status, 0)
            page = (output / "latest_riscv/insn/add.html").read_text(encoding="utf-8")
            self.assertIn(f"Version {short} ", page)
            self.assertEqual(spec.name, "_")

    def test_udb_repo_requires_a_resolved_spec(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = base / "udb"
            repo.mkdir()
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.com",
                    "commit",
                    "--allow-empty",
                    "-m",
                    "empty",
                ],
                check=True,
                capture_output=True,
            )
            status = generate.main(
                [
                    "--arch",
                    "riscv",
                    "--udb-repo",
                    str(repo),
                    "--output",
                    str(base / "build"),
                    "--assets-dir",
                    str(HERE),
                ]
            )
            self.assertEqual(status, 2)

    def test_udb_repo_is_riscv_only(self) -> None:
        status = generate.main(["--arch", "arm", "--udb-repo", "somewhere"])
        self.assertEqual(status, 2)


if __name__ == "__main__":
    unittest.main()
