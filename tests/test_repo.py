"""Smoke tests for the repository contract (KICKOFF Section 3, rules 7 and 8)."""

import subprocess

from bo import paths


def test_repo_root_contains_spec():
    assert (paths.REPO_ROOT / "KICKOFF.md").is_file()


def test_large_data_dirs_are_symlinks_outside_repo():
    for p in paths.SYMLINKED:
        assert p.is_symlink(), f"{p} must be a symlink to ~/Data/Power_Grid"
        target = p.resolve()
        assert target.is_dir()
        assert paths.REPO_ROOT not in target.parents


def test_labels_dir_is_inside_repo():
    assert paths.LABELS.is_dir() and not paths.LABELS.is_symlink()


def test_secrets_and_data_are_git_ignored():
    for rel in (".env", "data/raw", "data/chips", "data/processed", "data/checkpoints"):
        r = subprocess.run(
            ["git", "check-ignore", "-q", rel], cwd=paths.REPO_ROOT, check=False
        )
        assert r.returncode == 0, f"{rel} is not ignored by git"


def test_env_example_has_no_values():
    for line in (paths.REPO_ROOT / ".env.example").read_text().splitlines():
        if line and not line.startswith("#"):
            name, _, value = line.partition("=")
            assert name.isupper() or "_" in name
            assert value == "", f"{name} must be empty in .env.example"
