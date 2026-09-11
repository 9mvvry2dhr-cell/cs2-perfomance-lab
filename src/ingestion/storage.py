from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4


DEFAULT_MAX_DEMO_BYTES = (
    512 * 1024 * 1024
)

CHUNK_SIZE = 1024 * 1024


class DemoStorageError(Exception):
    pass


class InvalidDemoFileError(
    DemoStorageError
):
    pass


class DemoTooLargeError(
    DemoStorageError
):
    pass


@dataclass(frozen=True)
class StoredDemo:
    original_filename: str
    storage_key: str
    file_sha256: str
    size_bytes: int


def normalize_original_filename(
    filename: str,
) -> str:
    normalized = (
        filename
        .replace("\\", "/")
        .rsplit("/", 1)[-1]
        .strip()
    )

    if (
        len(normalized) <= 4
        or not normalized.lower().endswith(
            ".dem"
        )
    ):
        raise InvalidDemoFileError(
            "Only .dem files are supported"
        )

    return normalized


class LocalDemoStorage:
    def __init__(
        self,
        root: Path,
        *,
        max_bytes: int = (
            DEFAULT_MAX_DEMO_BYTES
        ),
    ):
        if max_bytes <= 0:
            raise ValueError(
                "max_bytes must be positive"
            )

        self.root = Path(root)
        self.max_bytes = max_bytes

    def store(
        self,
        *,
        original_filename: str,
        source: BinaryIO,
    ) -> StoredDemo:
        filename = (
            normalize_original_filename(
                original_filename
            )
        )

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_id = str(uuid4())

        storage_key = (
            f"{file_id}.dem"
        )

        final_path = (
            self.root / storage_key
        )

        temporary_path = (
            self.root
            / f".{file_id}.part"
        )

        digest = sha256()
        size_bytes = 0

        try:
            with temporary_path.open(
                "xb"
            ) as destination:
                while True:
                    chunk = source.read(
                        CHUNK_SIZE
                    )

                    if not chunk:
                        break

                    size_bytes += len(
                        chunk
                    )

                    if (
                        size_bytes
                        > self.max_bytes
                    ):
                        raise DemoTooLargeError(
                            "Demo file is too large"
                        )

                    digest.update(
                        chunk
                    )

                    destination.write(
                        chunk
                    )

            if size_bytes == 0:
                raise InvalidDemoFileError(
                    "Demo file is empty"
                )

            temporary_path.replace(
                final_path
            )

            return StoredDemo(
                original_filename=filename,
                storage_key=storage_key,
                file_sha256=(
                    digest.hexdigest()
                ),
                size_bytes=size_bytes,
            )

        except Exception:
            temporary_path.unlink(
                missing_ok=True
            )

            final_path.unlink(
                missing_ok=True
            )

            raise

    def delete(
        self,
        storage_key: str,
    ) -> None:
        if (
            "/" in storage_key
            or "\\" in storage_key
            or Path(storage_key).name
            != storage_key
        ):
            raise ValueError(
                "Invalid storage key"
            )

        path = (
            self.root / storage_key
        )

        path.unlink(
            missing_ok=True
        )
