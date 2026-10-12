"""
Resumable multipart uploads to the Superbio Data Hub.

File bytes go straight from disk to S3 through presigned URLs; the API only
issues URLs and finalises the upload. Progress is saved after initiation, so
re-running the same upload continues from the parts already in S3.
"""

import hashlib
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Tuple

import requests

DEFAULT_CONCURRENCY = 8
PART_RETRIES = 3
DEFAULT_STATE_DIR = Path.home() / ".superbio" / "uploads"

ProgressCallback = Callable[[str, int, int], None]
ApiRequest = Callable[..., dict]


def print_progress(file_name: str, uploaded_bytes: int, total_bytes: int) -> None:
    percent = (uploaded_bytes / total_bytes * 100) if total_bytes else 100.0
    print(f"{file_name}: {percent:.1f}% ({uploaded_bytes}/{total_bytes} bytes)")


def join_datahub_path(*segments: str) -> str:
    return "/".join(s.strip("/") for s in segments if s and s.strip("/"))


def iter_upload_targets(local_path: str, datahub_path: str = "") -> Iterator[Tuple[str, str]]:
    """Yield ``(local_file, datahub_folder)`` pairs; folders are walked recursively."""
    root = Path(local_path)
    if root.is_file():
        yield str(root), join_datahub_path(datahub_path)
        return
    if not root.is_dir():
        raise FileNotFoundError(f"No such file or directory: {local_path}")
    for file_path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative_folder = file_path.parent.relative_to(root).as_posix()
        if relative_folder == ".":
            relative_folder = ""
        yield str(file_path), join_datahub_path(datahub_path, root.name, relative_folder)


class _FileSlice:
    """Read-only view of ``length`` bytes of a file, streamed by ``requests``."""

    def __init__(self, path: str, offset: int, length: int):
        self._file = open(path, "rb")
        self._file.seek(offset)
        self._remaining = length
        self._length = length

    def __len__(self) -> int:
        return self._length

    def read(self, size: int = -1) -> bytes:
        if self._remaining <= 0:
            return b""
        if size is None or size < 0 or size > self._remaining:
            size = self._remaining
        chunk = self._file.read(size)
        self._remaining -= len(chunk)
        return chunk

    def close(self) -> None:
        self._file.close()


class DataHubUploader:
    def __init__(
        self,
        api_request: ApiRequest,
        concurrency: int = DEFAULT_CONCURRENCY,
        on_progress: Optional[ProgressCallback] = print_progress,
        state_dir: Path = DEFAULT_STATE_DIR,
    ):
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        self._api_request = api_request
        self._concurrency = concurrency
        self._on_progress = on_progress
        self._state_dir = Path(state_dir)

    def upload_file(self, local_path: str, namespace: str, datahub_folder: str = "") -> dict:
        file_size = os.path.getsize(local_path)
        if file_size == 0:
            raise ValueError(f"Cannot upload an empty file: {local_path}")
        file_name = os.path.basename(local_path)
        state_path = self._state_path(local_path, namespace, datahub_folder)

        session = self._resume(state_path)
        if session is None:
            session = self._initiate(file_name, file_size, namespace, datahub_folder)
            self._save_state(state_path, session["upload_token"])

        etags = self._upload_parts(local_path, file_size, session)
        result = self._api_request(
            "POST",
            "api/data_hub/upload/complete",
            _json={
                "upload_token": session["upload_token"],
                "parts": [{"PartNumber": n, "ETag": etags[n]} for n in sorted(etags)],
                "file_size": file_size,
            },
        )
        state_path.unlink()
        return result

    def _initiate(self, file_name: str, file_size: int, namespace: str, datahub_folder: str) -> dict:
        response = self._api_request(
            "POST",
            "api/data_hub/upload/initiate",
            _json={
                "namespace": namespace,
                "file_name": file_name,
                "file_size": file_size,
                "file_path": datahub_folder,
                "client": "sdk",
            },
        )
        return {
            "upload_token": response["upload_token"],
            "part_size": response["part_size"],
            "num_parts": response["num_parts"],
            "urls": {u["part_number"]: u["url"] for u in response["presigned_urls"]},
            "etags": {},
        }

    def _resume(self, state_path: Path) -> Optional[dict]:
        if not state_path.exists():
            return None
        upload_token = json.loads(state_path.read_text())["upload_token"]
        try:
            response = self._refresh(upload_token)
        except requests.HTTPError:
            state_path.unlink()
            return None
        return {
            "upload_token": upload_token,
            "part_size": response["part_size"],
            "num_parts": response["num_parts"],
            "urls": {u["part_number"]: u["url"] for u in response["presigned_urls"]},
            "etags": {p["PartNumber"]: p["ETag"] for p in response.get("uploaded_parts_detail", [])},
        }

    def _refresh(self, upload_token: str, part_numbers: Optional[List[int]] = None) -> dict:
        payload = {"upload_token": upload_token}
        if part_numbers is not None:
            payload["part_numbers"] = part_numbers
        return self._api_request("POST", "api/data_hub/upload/refresh", _json=payload)

    def _upload_parts(self, local_path: str, file_size: int, session: dict) -> Dict[int, str]:
        part_size = session["part_size"]
        etags: Dict[int, str] = dict(session["etags"])
        pending = sorted(n for n in range(1, session["num_parts"] + 1) if n not in etags)
        file_name = os.path.basename(local_path)
        lock = threading.Lock()
        uploaded_bytes = sum(self._part_length(n, part_size, file_size) for n in etags)
        self._report(file_name, uploaded_bytes, file_size)

        def upload(part_number: int) -> None:
            nonlocal uploaded_bytes
            etag = self._upload_part(local_path, file_size, session, part_number)
            with lock:
                etags[part_number] = etag
                uploaded_bytes += self._part_length(part_number, part_size, file_size)
                self._report(file_name, uploaded_bytes, file_size)

        with ThreadPoolExecutor(max_workers=self._concurrency) as pool:
            for future in [pool.submit(upload, n) for n in pending]:
                future.result()
        return etags

    def _upload_part(self, local_path: str, file_size: int, session: dict, part_number: int) -> str:
        part_size = session["part_size"]
        offset = (part_number - 1) * part_size
        length = self._part_length(part_number, part_size, file_size)
        url = session["urls"].get(part_number)

        for attempt in range(PART_RETRIES):
            if url is None:
                refreshed = self._refresh(session["upload_token"], [part_number])
                url = {u["part_number"]: u["url"] for u in refreshed["presigned_urls"]}[part_number]
            body = _FileSlice(local_path, offset, length)
            try:
                response = requests.put(url, data=body)
                response.raise_for_status()
                return response.headers["ETag"]
            except requests.RequestException:
                if attempt == PART_RETRIES - 1:
                    raise
                url = None
                time.sleep(2**attempt)
            finally:
                body.close()

    @staticmethod
    def _part_length(part_number: int, part_size: int, file_size: int) -> int:
        return min(part_size, file_size - (part_number - 1) * part_size)

    def _report(self, file_name: str, uploaded_bytes: int, total_bytes: int) -> None:
        if self._on_progress is not None:
            self._on_progress(file_name, uploaded_bytes, total_bytes)

    def _state_path(self, local_path: str, namespace: str, datahub_folder: str) -> Path:
        stat = os.stat(local_path)
        identity = json.dumps(
            [os.path.abspath(local_path), stat.st_size, stat.st_mtime_ns, namespace, datahub_folder]
        )
        return self._state_dir / f"{hashlib.sha256(identity.encode()).hexdigest()}.json"

    def _save_state(self, state_path: Path, upload_token: str) -> None:
        self._state_dir.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"upload_token": upload_token}))
