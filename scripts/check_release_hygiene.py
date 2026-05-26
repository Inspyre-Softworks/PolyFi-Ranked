from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tomllib


RELEASE_FILES = (
    'CHANGELOG.md',
    'pyproject.toml',
    'src/wifi_pref_manager/__init__.py',
)

VERSION_FILES = (
    'pyproject.toml',
    'src/wifi_pref_manager/__init__.py',
)

EXEMPT_FILES = {
    '.gitattributes',
    '.gitignore',
    '.readthedocs.yaml',
    'AGENTS.md',
    'CHANGELOG.md',
    'CONTRIBUTING.md',
    'LICENSE',
    'README.md',
    '.github/copilot-instructions.md',
    '.github/pull_request_template.md',
}

EXEMPT_PREFIXES = (
    '.github/ISSUE_TEMPLATE/',
    '.zencoder/',
    'docs/',
)


def normalize_repo_path(path: str) -> str:
    normalized = path.strip().replace('\\', '/')
    while normalized.startswith('./'):
        normalized = normalized[2:]
    return str(PurePosixPath(normalized))


def is_release_file(path: str) -> bool:
    return normalize_repo_path(path) in RELEASE_FILES


def is_exempt_change(path: str) -> bool:
    normalized = normalize_repo_path(path)
    if normalized in EXEMPT_FILES:
        return True
    return any(normalized.startswith(prefix) for prefix in EXEMPT_PREFIXES)


def load_changed_files(values: list[str]) -> list[str]:
    if values:
        return [normalize_repo_path(value) for value in values if value.strip()]
    return [
        normalize_repo_path(line)
        for line in sys.stdin.read().splitlines()
        if line.strip()
    ]


def release_hygiene_triggers(changed_files: list[str]) -> list[str]:
    return [
        path
        for path in changed_files
        if not is_release_file(path) and not is_exempt_change(path)
    ]


def has_version_bump(changed_files: list[str]) -> bool:
    changed = set(changed_files)
    return all(path in changed for path in VERSION_FILES)


def _parse_pyproject_version(text: str) -> str:
    """Return the version string from pyproject.toml content."""
    return tomllib.loads(text)['tool']['poetry']['version']


def version_actually_changed(base_ref: str) -> bool:
    """Return True when the version in pyproject.toml differs between *base_ref* and HEAD.

    Falls back to True (treat as changed) when the comparison cannot be made,
    e.g. pyproject.toml did not exist at *base_ref* or git is unavailable.
    """
    try:
        result = subprocess.run(
            ['git', 'show', f'{base_ref}:pyproject.toml'],
            capture_output=True,
            text=True,
            check=True,
        )
        old_version = _parse_pyproject_version(result.stdout)
    except (subprocess.CalledProcessError, KeyError, tomllib.TOMLDecodeError):
        return True

    try:
        new_version = _parse_pyproject_version(
            Path('pyproject.toml').read_text(encoding='utf-8')
        )
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return True

    return old_version != new_version


def missing_release_files(changed_files: list[str]) -> list[str]:
    changed = set(changed_files)
    missing: list[str] = []

    if 'CHANGELOG.md' not in changed:
        missing.append('CHANGELOG.md')

    if not has_version_bump(changed_files):
        for path in VERSION_FILES:
            if path not in changed:
                missing.append(path)

    return missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            'Fail when release-sensitive changes do not also update the changelog '
            'and version metadata.'
        )
    )
    parser.add_argument(
        'files',
        nargs='*',
        help='Changed repo-relative paths. If omitted, newline-delimited paths are read from stdin.',
    )
    parser.add_argument(
        '--base',
        metavar='REF',
        help=(
            'Git ref for the base of the comparison. When provided, the version '
            'in pyproject.toml is also compared against that ref to verify it '
            'actually changed, not just that the file was touched.'
        ),
    )
    args = parser.parse_args(argv)

    changed_files = load_changed_files(args.files)
    if not changed_files:
        print('No changed files were provided; skipping release hygiene check.')
        return 0

    triggering_files = release_hygiene_triggers(changed_files)
    if not triggering_files:
        print('Only docs/template/release files changed; no release bump required.')
        return 0

    missing = missing_release_files(changed_files)
    if missing:
        print('Release hygiene check failed.', file=sys.stderr)
        print('These files triggered the requirement:', file=sys.stderr)
        for path in triggering_files:
            print(f'  - {path}', file=sys.stderr)
        print('Add these files to the same change:', file=sys.stderr)
        for path in missing:
            print(f'  - {path}', file=sys.stderr)
        return 1

    if args.base and has_version_bump(changed_files) and not version_actually_changed(args.base):
        print('Release hygiene check failed.', file=sys.stderr)
        print(
            'The version files are present in the change set but the version '
            'value in pyproject.toml has not changed relative to the base.',
            file=sys.stderr,
        )
        print(
            'Increment the version in pyproject.toml and '
            'src/wifi_pref_manager/__init__.py.',
            file=sys.stderr,
        )
        return 1

    print('Release hygiene satisfied for this change set.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
