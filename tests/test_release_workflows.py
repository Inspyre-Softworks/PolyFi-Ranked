"""Guard the publication gates shared by the two release entry points."""

from pathlib import Path
import os
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[1]


class ReleaseWorkflowTests(unittest.TestCase):
    def test_auto_release_resumes_matching_tags_and_rejects_reused_versions(self) -> None:
        workflow = yaml.safe_load((ROOT / '.github/workflows/auto-release.yml').read_text(encoding='utf-8'))
        steps = workflow['jobs']['detect-version-bump']['steps']
        source = next(step['run'] for step in steps if step.get('id') == 'check')
        source = '\n'.join(source.splitlines()[1:-1])
        tag = 'refs/tags/v1.0.0-rc.2'
        for remote, expected in (
            ('', True),
            (f'head\t{tag}\n', True),
            (f'tag-object\t{tag}\nhead\t{tag}^{{}}\n', True),
            (f'other-commit\t{tag}\n', False),
        ):
            with self.subTest(remote=remote), TemporaryDirectory() as directory:
                output = Path(directory) / 'output'
                results = [
                    subprocess.CompletedProcess([], 0, '[tool.poetry]\nversion = "1.0.0-rc.1"\n'),
                    subprocess.CompletedProcess([], 0, remote),
                    subprocess.CompletedProcess([], 0, ''),
                ]
                with patch.dict(os.environ, {'BEFORE_SHA': 'base', 'RELEASE_SHA': 'head', 'GITHUB_OUTPUT': str(output)}), patch.object(
                    Path, 'read_text', return_value='[tool.poetry]\nversion = "1.0.0-rc.2"\n',
                ), patch('subprocess.run', side_effect=results):
                    if expected:
                        exec(compile(source, 'auto-release.yml', 'exec'), {})
                    else:
                        with self.assertRaisesRegex(SystemExit, 'another commit'):
                            exec(compile(source, 'auto-release.yml', 'exec'), {})
                if expected:
                    self.assertIn('bumped=true', output.read_text(encoding='utf-8'))
                else:
                    self.assertFalse(output.exists())

    def test_both_publishers_wait_for_tested_windows_artifacts(self) -> None:
        groups = set()
        for filename in ('auto-release.yml', 'release.yml'):
            with self.subTest(workflow=filename):
                workflow = yaml.safe_load((ROOT / '.github/workflows' / filename).read_text(encoding='utf-8'))
                groups.add(workflow['concurrency']['group'])
                self.assertFalse(workflow['concurrency']['cancel-in-progress'])
                jobs = workflow['jobs']
                self.assertIn('build-windows-artifacts', jobs['publish-package-index']['needs'])
                windows_steps = jobs['build-windows-artifacts']['steps']
                test_index = next(i for i, step in enumerate(windows_steps) if step.get('run') == 'poetry run pytest')
                build_index = next(i for i, step in enumerate(windows_steps) if 'build_windows_installer.ps1' in step.get('run', ''))
                self.assertLess(test_index, build_index)
                release_steps = jobs['publish-github-release']['steps']
                publisher = next(step for step in release_steps if step.get('uses', '').startswith('softprops/action-gh-release'))
                self.assertEqual(publisher['with']['body_path'], 'release-metadata/release-notes.md')
                self.assertTrue(publisher['with']['fail_on_unmatched_files'])
                self.assertNotIn('generate_release_notes', publisher['with'])
                if filename == 'auto-release.yml':
                    self.assertEqual(publisher['with']['target_commitish'], '${{ github.sha }}')
        self.assertEqual(len(groups), 1)

    def test_hygiene_checks_exact_pr_head_without_a_shell_pipeline(self) -> None:
        workflow = yaml.safe_load((ROOT / '.github/workflows/release-hygiene.yml').read_text(encoding='utf-8'))
        steps = workflow['jobs']['require-changelog-and-version-bump']['steps']
        checkout = next(step for step in steps if step.get('uses', '').startswith('actions/checkout'))
        self.assertEqual(checkout['with']['ref'], '${{ github.event.pull_request.head.sha }}')
        command = steps[-1]['run']
        self.assertIn('--base', command)
        self.assertIn('--head', command)
        self.assertNotIn('|', command)
