import unittest
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from src.ingestion.storage import (
    DemoTooLargeError,
    InvalidDemoFileError,
    LocalDemoStorage,
)


class LocalDemoStorageTest(
    unittest.TestCase
):
    def setUp(self):
        self.temp_dir = (
            TemporaryDirectory()
        )

        self.root = Path(
            self.temp_dir.name
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_store_demo_streams_file_and_hashes_it(
        self,
    ):
        payload = (
            b"fake-cs2-demo-content"
        )

        storage = LocalDemoStorage(
            self.root
        )

        stored = storage.store(
            original_filename=(
                r"C:\replays\match.dem"
            ),
            source=BytesIO(payload),
        )

        self.assertEqual(
            stored.original_filename,
            "match.dem",
        )

        self.assertEqual(
            stored.file_sha256,
            sha256(
                payload
            ).hexdigest(),
        )

        self.assertEqual(
            stored.size_bytes,
            len(payload),
        )

        saved_path = (
            self.root
            / stored.storage_key
        )

        self.assertTrue(
            saved_path.exists()
        )

        self.assertEqual(
            saved_path.read_bytes(),
            payload,
        )

        self.assertEqual(
            list(
                self.root.glob(
                    "*.part"
                )
            ),
            [],
        )

    def test_rejects_non_demo_file(
        self,
    ):
        storage = LocalDemoStorage(
            self.root
        )

        with self.assertRaises(
            InvalidDemoFileError
        ):
            storage.store(
                original_filename=(
                    "match.zip"
                ),
                source=BytesIO(
                    b"content"
                ),
            )

    def test_rejects_empty_demo(
        self,
    ):
        storage = LocalDemoStorage(
            self.root
        )

        with self.assertRaises(
            InvalidDemoFileError
        ):
            storage.store(
                original_filename=(
                    "match.dem"
                ),
                source=BytesIO(b""),
            )

        self.assertEqual(
            list(
                self.root.iterdir()
            ),
            [],
        )

    def test_rejects_demo_above_limit_and_cleans_up(
        self,
    ):
        storage = LocalDemoStorage(
            self.root,
            max_bytes=5,
        )

        with self.assertRaises(
            DemoTooLargeError
        ):
            storage.store(
                original_filename=(
                    "match.dem"
                ),
                source=BytesIO(
                    b"123456"
                ),
            )

        self.assertEqual(
            list(
                self.root.iterdir()
            ),
            [],
        )

    def test_delete_removes_stored_demo(
        self,
    ):
        storage = LocalDemoStorage(
            self.root
        )

        stored = storage.store(
            original_filename=(
                "match.dem"
            ),
            source=BytesIO(
                b"content"
            ),
        )

        storage.delete(
            stored.storage_key
        )

        self.assertFalse(
            (
                self.root
                / stored.storage_key
            ).exists()
        )


if __name__ == "__main__":
    unittest.main()
