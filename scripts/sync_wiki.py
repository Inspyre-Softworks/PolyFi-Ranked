from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from posixpath import normpath
import re
import subprocess
import sys
from urllib.parse import quote, unquote, urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = PROJECT_ROOT / 'docs' / 'wiki'
DEFAULT_WIKI_DIR = PROJECT_ROOT.parent / 'PolyFi-Ranked.wiki'
DEFAULT_WIKI_BASE_URL = 'https://github.com/Inspyre-Softworks/PolyFi-Ranked/wiki'
MARKDOWN_LINK_RE = re.compile(r'(!?)\[([^\]]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\)')


@dataclass
class SyncSummary:
    copied: list[Path] = field(default_factory=list)
    changed: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    deleted: list[Path] = field(default_factory=list)


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ['git', *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def ensure_clean_wiki_repo(wiki_dir: Path, *, force: bool) -> None:
    if not wiki_dir.exists() or not (wiki_dir / '.git').is_dir():
        raise RuntimeError(f'Wiki repo is missing or is not a git checkout: {wiki_dir}')

    if force:
        return

    status = _run_git(['status', '--porcelain'], wiki_dir).stdout.strip()
    if status:
        raise RuntimeError(
            'Wiki repo has uncommitted or untracked changes. '
            'Commit, clean, or rerun with --force.'
        )


def selected_markdown_files(source_dir: Path, include_patterns: list[str]) -> list[Path]:
    files: dict[Path, Path] = {}
    for pattern in include_patterns:
        for path in source_dir.glob(pattern):
            if path.is_file() and path.suffix.lower() == '.md':
                files[path.relative_to(source_dir)] = path
    return [files[key] for key in sorted(files)]


def target_name_for(source_file: Path, source_dir: Path) -> str:
    return source_file.relative_to(source_dir).name


def wiki_slug(path: str) -> str:
    path_without_fragment = path.split('#', 1)[0]
    name = Path(unquote(path_without_fragment)).name
    stem = name[:-3] if name.lower().endswith('.md') else name
    if stem == 'Home':
        return 'Home'
    return quote(stem.replace(' ', '-'), safe='-()_')


def is_local_docs_link(target: str) -> bool:
    if target.startswith('#'):
        return False

    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return False

    path = parsed.path.replace('\\', '/')
    return path.lower().endswith('.md')


def resolve_link_path(source_file: Path, source_dir: Path, target: str) -> Path:
    parsed_path = unquote(urlsplit(target).path).replace('\\', '/')
    if parsed_path.startswith('/'):
        relative = parsed_path.lstrip('/')
    else:
        base = source_file.relative_to(source_dir).parent.as_posix()
        relative = normpath(f'{base}/{parsed_path}' if base != '.' else parsed_path)

    if relative.startswith('../'):
        relative = normpath(relative)
    return Path(relative)


def rewrite_markdown_links(content: str, source_file: Path, source_dir: Path, wiki_base_url: str) -> str:
    wiki_base_url = wiki_base_url.rstrip('/')

    def replace(match: re.Match[str]) -> str:
        image_marker, label, target = match.groups()
        if image_marker or not is_local_docs_link(target):
            return match.group(0)

        parsed = urlsplit(target)
        resolved = resolve_link_path(source_file, source_dir, target)
        if not (source_dir / resolved).is_file():
            return match.group(0)

        slug = wiki_slug(resolved.as_posix())
        fragment = f'#{parsed.fragment}' if parsed.fragment else ''
        return f'[{label}]({wiki_base_url}/{slug}{fragment})'

    return MARKDOWN_LINK_RE.sub(replace, content)


def sync_wiki(
    *,
    source_dir: Path,
    wiki_dir: Path,
    include_patterns: list[str],
    wiki_base_url: str,
    dry_run: bool,
    prune: bool,
    force: bool,
) -> SyncSummary:
    source_dir = source_dir.resolve()
    wiki_dir = wiki_dir.resolve()
    ensure_clean_wiki_repo(wiki_dir, force=force)

    if not source_dir.is_dir():
        raise RuntimeError(f'Wiki source directory is missing: {source_dir}')

    summary = SyncSummary()
    source_files = selected_markdown_files(source_dir, include_patterns)
    expected_targets: set[Path] = set()
    target_names: set[str] = set()

    for source_file in source_files:
        target_name = target_name_for(source_file, source_dir)
        if target_name in target_names:
            raise RuntimeError(f'Multiple source files map to wiki page {target_name}')
        target_names.add(target_name)
        expected_targets.add((wiki_dir / target_name).resolve())

    unexpected_files = [
        path
        for path in sorted(wiki_dir.glob('*.md'))
        if path.resolve() not in expected_targets
    ]
    if unexpected_files and not prune:
        formatted = '\n'.join(f'  - {path.name}' for path in unexpected_files)
        raise RuntimeError(
            'Unexpected wiki Markdown files would be left unmanaged. '
            'Rerun with --prune to delete them after review:\n'
            f'{formatted}'
        )

    for source_file in source_files:
        target_file = wiki_dir / target_name_for(source_file, source_dir)
        content = source_file.read_text(encoding='utf-8')
        rewritten = rewrite_markdown_links(content, source_file, source_dir, wiki_base_url)

        if target_file.exists():
            current = target_file.read_text(encoding='utf-8')
            if current == rewritten:
                summary.skipped.append(target_file)
                continue
            summary.changed.append(target_file)
        else:
            summary.copied.append(target_file)

        if not dry_run:
            target_file.write_text(rewritten, encoding='utf-8', newline='')

    for path in unexpected_files:
        summary.deleted.append(path)
        if not dry_run:
            path.unlink()

    return summary


def print_summary(summary: SyncSummary, *, dry_run: bool) -> None:
    prefix = 'Dry run summary' if dry_run else 'Sync summary'
    print(f'{prefix}:')

    groups = (
        ('copied', summary.copied),
        ('changed', summary.changed),
        ('skipped', summary.skipped),
        ('deleted', summary.deleted),
    )
    for label, paths in groups:
        print(f'  {label}: {len(paths)}')
        for path in paths:
            print(f'    - {path.name}')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Sync docs/wiki Markdown pages into the adjacent GitHub Wiki checkout.'
    )
    parser.add_argument(
        '--source',
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help='Source directory for wiki Markdown pages. Defaults to docs/wiki/.',
    )
    parser.add_argument(
        '--wiki',
        type=Path,
        default=DEFAULT_WIKI_DIR,
        help='Target GitHub Wiki checkout. Defaults to ../PolyFi-Ranked.wiki.',
    )
    parser.add_argument(
        '--include',
        action='append',
        default=None,
        help='Source glob to include. May be repeated. Defaults to *.md.',
    )
    parser.add_argument(
        '--wiki-base-url',
        default=DEFAULT_WIKI_BASE_URL,
        help='Base URL used when rewriting local Markdown links.',
    )
    parser.add_argument('--dry-run', action='store_true', help='Print actions without writing files.')
    parser.add_argument('--prune', action='store_true', help='Delete unexpected target wiki Markdown files.')
    parser.add_argument(
        '--force',
        action='store_true',
        help='Run even when the wiki checkout has uncommitted or untracked changes.',
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    include_patterns = args.include or ['*.md']

    try:
        summary = sync_wiki(
            source_dir=args.source,
            wiki_dir=args.wiki,
            include_patterns=include_patterns,
            wiki_base_url=args.wiki_base_url,
            dry_run=args.dry_run,
            prune=args.prune,
            force=args.force,
        )
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1

    print_summary(summary, dry_run=args.dry_run)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
