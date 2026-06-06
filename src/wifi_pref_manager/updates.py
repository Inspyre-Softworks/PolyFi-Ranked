"""
GitHub Release update checks and Windows installer downloads.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from wifi_pref_manager.paths import AppPaths


DOCS_URL = 'https://polyfi-ranked.readthedocs.io/'
GITHUB_REPOSITORY_URL = 'https://github.com/Inspyre-Softworks/PolyFi-Ranked'
GITHUB_RELEASES_URL = f'{GITHUB_REPOSITORY_URL}/releases'
GITHUB_RELEASES_API_URL = (
    'https://api.github.com/repos/Inspyre-Softworks/PolyFi-Ranked/releases?per_page=20'
)
UPDATE_DOWNLOAD_CHUNK_SIZE = 1024 * 128
_VERSION_RE = re.compile(
    r'^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)'
    r'(?:(?:[-.])(?P<label>[A-Za-z]+)\.?(?P<label_number>\d+)?)?$'
)
_LABEL_RANKS = {
    'dev': 0,
    'a': 1,
    'alpha': 1,
    'b': 2,
    'beta': 2,
    'rc': 3,
}


class UpdateError(RuntimeError):
    """Raised when update metadata, download, or launch work fails."""


@dataclass(frozen=True)
class UpdateAsset:
    """Release asset that can be downloaded."""

    name: str
    download_url: str
    size: int | None = None


@dataclass(frozen=True)
class UpdateInfo:
    """Available update metadata."""

    version: str
    tag_name: str
    release_url: str
    prerelease: bool = False
    installer_asset: UpdateAsset | None = None


def parse_version_sort_key(version: str) -> tuple[int, int, int, int, int] | None:
    """
    Parse PolyFi release tags into sortable tuples.
    """
    normalized = version.strip()
    match = _VERSION_RE.match(normalized)
    if match is None:
        return None

    major = int(match.group('major'))
    minor = int(match.group('minor'))
    patch = int(match.group('patch'))
    label = (match.group('label') or '').lower()
    label_number = int(match.group('label_number') or 0)
    label_rank = _LABEL_RANKS.get(label, 4 if not label else -1)
    return major, minor, patch, label_rank, label_number


def is_newer_version(candidate: str, current: str) -> bool:
    """
    Return whether ``candidate`` is newer than ``current``.
    """
    candidate_key = parse_version_sort_key(candidate)
    current_key = parse_version_sort_key(current)
    if candidate_key is None or current_key is None:
        return candidate.strip().lstrip('v') != current.strip().lstrip('v')
    return candidate_key > current_key


def _asset_from_payload(payload: dict[str, Any]) -> UpdateAsset | None:
    name = str(payload.get('name', '')).strip()
    download_url = str(payload.get('browser_download_url', '')).strip()
    if not name or not download_url:
        return None
    size = payload.get('size')
    try:
        parsed_size = int(size) if size is not None else None
    except (TypeError, ValueError):
        parsed_size = None
    return UpdateAsset(name=name, download_url=download_url, size=parsed_size)


def select_windows_installer_asset(assets: list[dict[str, Any]]) -> UpdateAsset | None:
    """
    Select the Windows setup executable from a GitHub Release asset list.
    """
    parsed_assets = [
        asset
        for payload in assets
        if isinstance(payload, dict)
        for asset in [_asset_from_payload(payload)]
        if asset is not None
    ]
    for asset in parsed_assets:
        normalized = asset.name.casefold()
        if normalized.endswith('.exe') and 'polyfi' in normalized and 'setup' in normalized:
            return asset
    for asset in parsed_assets:
        if asset.name.casefold().endswith('.exe'):
            return asset
    return None


def update_from_release_payload(
    payload: dict[str, Any],
    current_version: str,
) -> UpdateInfo | None:
    """
    Convert a GitHub Release payload into update metadata when it is newer.
    """
    if payload.get('draft'):
        return None

    tag_name = str(payload.get('tag_name', '')).strip()
    if not tag_name:
        return None
    version = tag_name.removeprefix('v')
    if not is_newer_version(version, current_version):
        return None

    release_url = str(payload.get('html_url') or f'{GITHUB_RELEASES_URL}/tag/{tag_name}')
    raw_assets = payload.get('assets', [])
    assets = raw_assets if isinstance(raw_assets, list) else []
    return UpdateInfo(
        version=version,
        tag_name=tag_name,
        release_url=release_url,
        prerelease=bool(payload.get('prerelease')),
        installer_asset=select_windows_installer_asset(assets),
    )


def choose_latest_update(
    releases: list[dict[str, Any]],
    current_version: str,
) -> UpdateInfo | None:
    """
    Pick the highest newer release from GitHub Release payloads.
    """
    candidates: list[UpdateInfo] = []
    for payload in releases:
        if not isinstance(payload, dict):
            continue
        update = update_from_release_payload(payload, current_version)
        if update is not None:
            candidates.append(update)
    if not candidates:
        return None

    def _sort_key(update: UpdateInfo) -> tuple[int, int, int, int, int]:
        return parse_version_sort_key(update.version) or (0, 0, 0, -1, 0)

    return max(candidates, key=_sort_key)


class UpdateManager:
    """
    Check GitHub Releases and install downloaded Windows setup executables.
    """

    def __init__(
        self,
        paths: AppPaths | None = None,
        *,
        api_url: str = GITHUB_RELEASES_API_URL,
    ) -> None:
        self.paths = paths or AppPaths()
        self.api_url = api_url

    def _request(self, url: str) -> Request:
        return Request(
            url,
            headers={
                'Accept': 'application/vnd.github+json',
                'User-Agent': 'PolyFi-Ranked update checker',
            },
        )

    def fetch_releases(self, *, timeout: float = 6.0) -> list[dict[str, Any]]:
        """
        Fetch recent GitHub Releases.
        """
        try:
            with urlopen(self._request(self.api_url), timeout=timeout) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except (OSError, URLError, json.JSONDecodeError) as exc:
            raise UpdateError(f'Could not check GitHub Releases: {exc}') from exc
        if not isinstance(payload, list):
            raise UpdateError('GitHub Releases response was not a list.')
        return [entry for entry in payload if isinstance(entry, dict)]

    def check_for_update(self, current_version: str, *, timeout: float = 6.0) -> UpdateInfo | None:
        """
        Return update metadata when a newer release is available.
        """
        return choose_latest_update(self.fetch_releases(timeout=timeout), current_version)

    @staticmethod
    def _safe_asset_name(name: str) -> str:
        cleaned = re.sub(r'[^A-Za-z0-9._-]+', '-', name).strip('.-')
        return cleaned or 'polyfi-ranked-setup.exe'

    def download_installer(
        self,
        update: UpdateInfo,
        *,
        timeout: float = 30.0,
    ) -> Path:
        """
        Download the release installer and return its local path.
        """
        if update.installer_asset is None:
            raise UpdateError(f'Release {update.tag_name} does not include a Windows installer asset.')

        self.paths.ensure_directories()
        updates_dir = self.paths.local_data_dir / 'updates'
        updates_dir.mkdir(parents=True, exist_ok=True)
        destination = updates_dir / self._safe_asset_name(update.installer_asset.name)
        partial_destination = destination.with_suffix(destination.suffix + '.download')

        try:
            with (
                urlopen(self._request(update.installer_asset.download_url), timeout=timeout) as response,
                partial_destination.open('wb') as handle,
            ):
                while True:
                    chunk = response.read(UPDATE_DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    handle.write(chunk)
            partial_destination.replace(destination)
        except (OSError, URLError) as exc:
            try:
                partial_destination.unlink()
            except OSError:
                pass
            raise UpdateError(f'Could not download installer: {exc}') from exc

        return destination

    @staticmethod
    def launch_installer(installer_path: Path) -> None:
        """
        Launch a downloaded installer.
        """
        if not installer_path.exists():
            raise UpdateError(f'Installer file does not exist: {installer_path}')
        try:
            subprocess.Popen(  # noqa: S603
                [str(installer_path)],
                cwd=str(installer_path.parent),
                close_fds=True,
            )
        except OSError as exc:
            raise UpdateError(f'Could not launch installer: {exc}') from exc
