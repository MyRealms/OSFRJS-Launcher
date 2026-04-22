from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from .constants import DOWNLOAD_TIMEOUT
from .models import ClientFileEntry, ClientFolderEntry, ServerProfile
from .utils import join_url

try:
    import xxhash
except ImportError:
    xxhash = None


class LauncherWidgetClientFilesFlowMixin:
    def _verify_client_files(self, profile: ServerProfile, root_folder: ClientFolderEntry) -> None:
        files_to_download = self._collect_missing_files(profile, root_folder)
        if not files_to_download:
            return

        total = len(files_to_download)
        if not self.settings.parallel_download or total == 1:
            for index, (relative_path, entry) in enumerate(files_to_download, start=1):
                self._set_status_screen("Warming", f"Preparing game files ({index}/{total})", animate_detail=False)
                self._download_file(profile, relative_path, entry.name)
            return

        max_workers = min(max(1, self.settings.download_threads), total)
        self._set_status_screen("Warming", f"Preparing game files (0/{total}) with {max_workers} threads", animate_detail=False)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self._download_file, profile, relative_path, entry.name)
                for relative_path, entry in files_to_download
            ]
            for index, future in enumerate(as_completed(futures), start=1):
                future.result()
                self._set_status_screen("Warming", f"Preparing game files ({index}/{total}) with {max_workers} threads", animate_detail=False)

    def _collect_missing_files(
        self,
        profile: ServerProfile,
        folder: ClientFolderEntry,
        relative_path: str = "",
    ) -> list[tuple[str, ClientFileEntry]]:
        missing: list[tuple[str, ClientFileEntry]] = []

        for child_folder in folder.folders:
            child_relative = f"{relative_path}/{child_folder.name}" if relative_path else child_folder.name
            missing.extend(self._collect_missing_files(profile, child_folder, child_relative))

        client_dir = self._client_directory(profile)
        for entry in folder.files:
            local_path = client_dir / relative_path / entry.name if relative_path else client_dir / entry.name
            if not self._file_matches(local_path, entry):
                missing.append((relative_path, entry))

        return missing

    def _file_matches(self, file_path: Path, entry: ClientFileEntry) -> bool:
        if not file_path.exists():
            return False
        if file_path.stat().st_size != entry.size:
            return False
        if xxhash is None:
            if not self.hash_warning_shown:
                self.hash_warning_shown = True
            return True

        hasher = xxhash.xxh64()
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.intdigest() == entry.hash_value

    def _download_file(self, profile: ServerProfile, relative_path: str, file_name: str) -> None:
        url_parts = ["client"]
        if relative_path:
            url_parts.extend(relative_path.split("/"))
        url_parts.append(file_name)
        url = join_url(profile.server_url, *url_parts)

        target_dir = self._client_directory(profile) / relative_path if relative_path else self._client_directory(profile)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / file_name

        with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT) as response:
            response.raise_for_status()
            with target_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        handle.write(chunk)
