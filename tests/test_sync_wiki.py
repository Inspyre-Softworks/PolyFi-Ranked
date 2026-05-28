from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / 'scripts' / 'sync_wiki.py'

_SPEC = spec_from_file_location('sync_wiki', SCRIPT_PATH)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(f'Could not load {SCRIPT_PATH}')
sync_wiki = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = sync_wiki
_SPEC.loader.exec_module(sync_wiki)


class SyncWikiTests(unittest.TestCase):
    def _git(self, cwd: Path, *args: str) -> None:
        subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True)

    def _make_clean_wiki_repo(self, root: Path) -> Path:
        wiki_dir = root / 'PolyFi-Ranked.wiki'
        wiki_dir.mkdir()
        self._git(wiki_dir, 'init')
        self._git(wiki_dir, 'config', 'user.email', 'tests@example.test')
        self._git(wiki_dir, 'config', 'user.name', 'Tests')
        (wiki_dir / 'Home.md').write_text('old home\n', encoding='utf-8')
        self._git(wiki_dir, 'add', 'Home.md')
        self._git(wiki_dir, 'commit', '-m', 'Initial wiki')
        return wiki_dir

    def test_sync_copies_markdown_and_rewrites_local_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_dir = root / 'repo' / 'docs' / 'wiki'
            source_dir.mkdir(parents=True)
            (source_dir / 'Home.md').write_text(
                '# Home\n\nSee [Docs](Contributing-Docs.md#sync).\n',
                encoding='utf-8',
            )
            (source_dir / 'Contributing-Docs.md').write_text('# Sync\n', encoding='utf-8')
            wiki_dir = self._make_clean_wiki_repo(root)

            summary = sync_wiki.sync_wiki(
                source_dir=source_dir,
                wiki_dir=wiki_dir,
                include_patterns=['*.md'],
                wiki_base_url='https://github.com/Inspyre-Softworks/PolyFi-Ranked/wiki',
                dry_run=False,
                prune=False,
                force=False,
            )

            self.assertEqual([path.name for path in summary.copied], ['Contributing-Docs.md'])
            self.assertEqual([path.name for path in summary.changed], ['Home.md'])
            self.assertIn(
                'https://github.com/Inspyre-Softworks/PolyFi-Ranked/wiki/Contributing-Docs#sync',
                (wiki_dir / 'Home.md').read_text(encoding='utf-8'),
            )

    def test_dry_run_does_not_write_target_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_dir = root / 'repo' / 'docs' / 'wiki'
            source_dir.mkdir(parents=True)
            (source_dir / 'Home.md').write_text('new home\n', encoding='utf-8')
            wiki_dir = self._make_clean_wiki_repo(root)

            summary = sync_wiki.sync_wiki(
                source_dir=source_dir,
                wiki_dir=wiki_dir,
                include_patterns=['*.md'],
                wiki_base_url='https://example.test/wiki',
                dry_run=True,
                prune=False,
                force=False,
            )

            self.assertEqual([path.name for path in summary.changed], ['Home.md'])
            self.assertEqual((wiki_dir / 'Home.md').read_text(encoding='utf-8'), 'old home\n')

    def test_refuses_dirty_wiki_repo_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_dir = root / 'repo' / 'docs' / 'wiki'
            source_dir.mkdir(parents=True)
            (source_dir / 'Home.md').write_text('new home\n', encoding='utf-8')
            wiki_dir = self._make_clean_wiki_repo(root)
            (wiki_dir / 'scratch.md').write_text('dirty\n', encoding='utf-8')

            with self.assertRaisesRegex(RuntimeError, 'uncommitted or untracked'):
                sync_wiki.sync_wiki(
                    source_dir=source_dir,
                    wiki_dir=wiki_dir,
                    include_patterns=['*.md'],
                    wiki_base_url='https://example.test/wiki',
                    dry_run=True,
                    prune=False,
                    force=False,
                )

    def test_prune_required_before_deleting_unexpected_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_dir = root / 'repo' / 'docs' / 'wiki'
            source_dir.mkdir(parents=True)
            (source_dir / 'Home.md').write_text('old home\n', encoding='utf-8')
            wiki_dir = self._make_clean_wiki_repo(root)
            (wiki_dir / 'Legacy.md').write_text('legacy\n', encoding='utf-8')
            self._git(wiki_dir, 'add', 'Legacy.md')
            self._git(wiki_dir, 'commit', '-m', 'Add legacy page')

            with self.assertRaisesRegex(RuntimeError, 'Unexpected wiki Markdown files'):
                sync_wiki.sync_wiki(
                    source_dir=source_dir,
                    wiki_dir=wiki_dir,
                    include_patterns=['*.md'],
                    wiki_base_url='https://example.test/wiki',
                    dry_run=False,
                    prune=False,
                    force=False,
                )

            summary = sync_wiki.sync_wiki(
                source_dir=source_dir,
                wiki_dir=wiki_dir,
                include_patterns=['*.md'],
                wiki_base_url='https://example.test/wiki',
                dry_run=False,
                prune=True,
                force=False,
            )

            self.assertEqual([path.name for path in summary.deleted], ['Legacy.md'])
            self.assertFalse((wiki_dir / 'Legacy.md').exists())


if __name__ == '__main__':
    unittest.main()
