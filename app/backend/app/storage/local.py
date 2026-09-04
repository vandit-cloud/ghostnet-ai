"""Local filesystem storage. Production deployments can swap this for an
S3/GCS-backed implementation behind the same StorageBackend interface."""

import hashlib
import os
import uuid
from pathlib import Path
from typing import BinaryIO, Protocol

from app.core.config import get_settings

settings = get_settings()


class StorageBackend(Protocol):
    def save(self, survey_id: str, filename: str, stream: BinaryIO) -> tuple[str, int, str]: ...
    def path_for(self, storage_reference: str) -> Path: ...
    def open(self, storage_reference: str) -> BinaryIO: ...


class LocalStorageBackend:
    def __init__(self, root: str | None = None):
        self.root = Path(root or settings.storage_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_name(self, filename: str) -> str:
        base = os.path.basename(filename)
        base = base.replace("..", "_").strip()
        return base or "file"

    def save(self, survey_id: str, filename: str, stream: BinaryIO) -> tuple[str, int, str]:
        safe_name = self._safe_name(filename)
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        survey_dir = self.root / str(survey_id)
        survey_dir.mkdir(parents=True, exist_ok=True)

        dest_path = survey_dir / unique_name
        resolved = dest_path.resolve()
        if not str(resolved).startswith(str(self.root.resolve())):
            raise ValueError("Unsafe storage path detected.")

        sha256 = hashlib.sha256()
        size = 0
        with open(dest_path, "wb") as out:
            while chunk := stream.read(1024 * 1024):
                out.write(chunk)
                sha256.update(chunk)
                size += len(chunk)

        storage_reference = f"{survey_id}/{unique_name}"
        return storage_reference, size, sha256.hexdigest()

    def path_for(self, storage_reference: str) -> Path:
        path = (self.root / storage_reference).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError("Unsafe storage path detected.")
        return path

    def open(self, storage_reference: str) -> BinaryIO:
        return open(self.path_for(storage_reference), "rb")


def get_storage_backend() -> StorageBackend:
    return LocalStorageBackend()
