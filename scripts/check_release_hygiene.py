"""Validate PR release policy and metadata shared by both publishers.

Author: Taylor B. | Inspyre-Softworks.
"""

from __future__ import annotations

import argparse
import ast
from datetime import date
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tomllib

from packaging.version import Version


RELEASE_FILES = ('CHANGELOG.md', 'pyproject.toml', 'src/wifi_pref_manager/__init__.py')
VERSION_FILES = RELEASE_FILES[1:]
EXEMPT_FILES = {
    '.gitattributes', '.gitignore', '.readthedocs.yaml', 'AGENTS.md',
    'CHANGELOG.md', 'CONTRIBUTING.md', 'LICENSE', 'README.md',
    '.github/copilot-instructions.md', '.github/git-commit-instructions.md',
    '.github/pull_request_template.md',
}
EXEMPT_PREFIXES = ('.github/ISSUE_TEMPLATE/', '.zencoder/', 'docs/', 'tests/')


def normalize_repo_path(path: str) -> str:
    """Normalize repo-relative input from either supported shell."""
    normalized = path.strip().replace('\\', '/')
    while normalized.startswith('./'):
        normalized = normalized[2:]
    return str(PurePosixPath(normalized))


def is_release_file(path: str) -> bool:
    return normalize_repo_path(path) in RELEASE_FILES


def is_exempt_change(path: str) -> bool:
    normalized = normalize_repo_path(path)
    return normalized in EXEMPT_FILES or normalized.startswith(EXEMPT_PREFIXES)


def load_changed_files(values: list[str]) -> list[str]:
    values = values or sys.stdin.read().splitlines()
    return [normalize_repo_path(value) for value in values if value.strip()]


def release_hygiene_triggers(changed_files: list[str]) -> list[str]:
    return [path for path in changed_files if not is_release_file(path) and not is_exempt_change(path)]


def has_version_bump(changed_files: list[str]) -> bool:
    return set(VERSION_FILES).issubset(changed_files)


def missing_release_files(changed_files: list[str]) -> list[str]:
    return [path for path in RELEASE_FILES if path not in changed_files]


def git_output(*args: str) -> str:
    """Read Git output, failing closed when a ref or command is unavailable."""
    try:
        return subprocess.run(
            ['git', *args], capture_output=True, text=True, encoding='utf-8', check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f'Cannot read Git comparison: {exc}') from exc


def read_file(path: str, ref: str | None = None) -> str:
    return git_output('show', f'{ref}:{path}') if ref else Path(path).read_text(encoding='utf-8')


def _parse_pyproject_version(text: str) -> str:
    version = tomllib.loads(text)['tool']['poetry']['version']
    if not isinstance(version, str) or not re.fullmatch(r'[0-9][A-Za-z0-9.!+_-]*', version):
        raise ValueError('pyproject.toml must contain a valid version string.')
    parsed = Version(version)
    if parsed.local is not None or parsed.epoch:
        raise ValueError('Public releases cannot contain a local version or epoch.')
    return version


def version_actually_changed(base_ref: str, head_ref: str | None = None) -> bool:
    """Require a PEP 440 increase, including dev/RC/stable ordering."""
    previous = _parse_pyproject_version(read_file('pyproject.toml', base_ref))
    current = _parse_pyproject_version(read_file('pyproject.toml', head_ref))
    return Version(current) > Version(previous)


def validate_metadata(ref: str | None = None, tag: str | None = None) -> tuple[str, str]:
    """Return the validated version and its dated, nonempty release notes.

    Parse the package version without importing Windows runtime dependencies.
    The current version must be the first dated changelog release.
    """
    version = _parse_pyproject_version(read_file('pyproject.toml', ref))
    module = ast.parse(read_file('src/wifi_pref_manager/__init__.py', ref))
    assignments = [
        node for node in module.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == '__version__' for target in node.targets)
    ]
    if len(assignments) != 1 or ast.literal_eval(assignments[0].value) != version:
        raise ValueError('Package __version__ must exactly match pyproject.toml.')
    if tag is not None and tag != f'v{version}':
        raise ValueError(f'Tag {tag!r} must match v{version}.')

    changelog = read_file('CHANGELOG.md', ref)
    headings = list(re.finditer(r'^## \[([^\]]+)\](.*)$', changelog, re.MULTILINE))
    names = [heading[1] for heading in headings]
    if not names or names[0] != 'Unreleased' or len(names) != len(set(names)):
        raise ValueError('Changelog must start with [Unreleased] and have unique release headings.')
    if len(headings) < 2 or headings[1][1] != version:
        raise ValueError(f'First dated changelog release must be [{version}].')
    heading = headings[1]
    if not re.fullmatch(r' - \d{4}-\d{2}-\d{2}', heading[2]):
        raise ValueError(f'Changelog [{version}] needs an ISO release date.')
    date.fromisoformat(heading[2][3:])
    end = headings[2].start() if len(headings) > 2 else len(changelog)
    notes = changelog[heading.end():end].strip()
    if not re.search(r'^[-*] \S', notes, re.MULTILINE):
        raise ValueError(f'Changelog [{version}] needs release notes with at least one entry.')
    return version, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='*', help='Changed paths; otherwise read stdin.')
    parser.add_argument('--base', help='Base ref for the complete PR comparison.')
    parser.add_argument('--head', help='Head ref to compare and validate; requires --base.')
    parser.add_argument('--metadata-only', action='store_true', help='Validate release metadata only.')
    parser.add_argument('--tag', help='Require this exact v<version> tag.')
    parser.add_argument('--notes', type=Path, help='Write the current release notes to this file.')
    parser.add_argument('--github-output', action='store_true', help='Append validated Actions outputs.')
    args = parser.parse_args(argv)
    if args.head and not args.base:
        parser.error('--head requires --base')
    try:
        version, notes = validate_metadata(args.head, args.tag)
        if not args.metadata_only:
            if args.head:
                paths = git_output('diff', '--name-only', args.base, args.head, '--').splitlines()
                changed = [normalize_repo_path(path) for path in paths if path.strip()]
            else:
                changed = load_changed_files(args.files)
            triggers = release_hygiene_triggers(changed)
            version_edits = set(VERSION_FILES).intersection(changed)
            if triggers or version_edits:
                missing = missing_release_files(changed)
                if missing:
                    raise ValueError('Update these files in the same PR: ' + ', '.join(missing))
                if args.base and not version_actually_changed(args.base, args.head):
                    raise ValueError('Version must increase relative to the PR base; unchanged or lower versions are invalid.')
        if args.notes:
            args.notes.write_text(notes + '\n', encoding='utf-8')
        if args.github_output:
            parsed = Version(version)
            with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as output:
                output.write(f'version={version}\ntag=v{version}\nprerelease={str(parsed.is_prerelease).lower()}\n')
    except (ValueError, OSError, KeyError, SyntaxError, TypeError) as exc:
        print(f'Release hygiene check failed: {exc}', file=sys.stderr)
        return 1
    print(f'Release hygiene satisfied ({version}).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

