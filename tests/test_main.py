import argparse
import io
import json
import os
import tarfile
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.main import (
    build_package_url,
    download_package,
    fetch_package_data,
    get_direct_dependencies,
    get_tarball_url,
    read_package_json,
    validate_args,
    validate_url,
)


def make_args(**changes):
    values = {
        "package": "react",
        "repository": "https://registry.npmjs.org",
        "test_mode": False,
        "output": "graph.png",
        "ascii_tree": False,
        "max_depth": 3,
    }
    values.update(changes)
    return argparse.Namespace(**values)


def create_test_archive(package_json):
    archive_buffer = io.BytesIO()
    data = json.dumps(package_json).encode("utf-8")

    with tarfile.open(
        fileobj=archive_buffer,
        mode="w:gz",
    ) as archive:
        info = tarfile.TarInfo(
            name="package/package.json"
        )
        info.size = len(data)

        archive.addfile(
            info,
            io.BytesIO(data),
        )

    return archive_buffer.getvalue()


class TestMain(unittest.TestCase):
    def test_valid_url(self):
        self.assertTrue(
            validate_url("https://registry.npmjs.org")
        )

    def test_invalid_url(self):
        self.assertFalse(
            validate_url("hello")
        )

    def test_empty_package(self):
        args = make_args(package=" ")

        with self.assertRaises(ValueError):
            validate_args(args)

    def test_invalid_depth(self):
        args = make_args(max_depth=0)

        with self.assertRaises(ValueError):
            validate_args(args)

    def test_minimum_valid_depth(self):
        args = make_args(max_depth=1)

        validate_args(args)

    def test_empty_output(self):
        args = make_args(output=" ")

        with self.assertRaises(ValueError):
            validate_args(args)

    def test_invalid_repository(self):
        args = make_args(repository="hello")

        with self.assertRaises(ValueError):
            validate_args(args)

    def test_missing_test_file(self):
        args = make_args(
            repository="missing.txt",
            test_mode=True,
        )

        with self.assertRaises(ValueError):
            validate_args(args)

    def test_existing_test_file(self):
        with tempfile.NamedTemporaryFile(
            delete=False
        ) as file:
            path = file.name

        try:
            args = make_args(
                repository=path,
                test_mode=True,
            )

            validate_args(args)
        finally:
            os.remove(path)

    def test_build_package_url(self):
        url = build_package_url(
            "https://registry.npmjs.org",
            "express",
        )

        self.assertEqual(
            url,
            "https://registry.npmjs.org/express",
        )

    def test_get_tarball_url(self):
        package_data = {
            "dist-tags": {
                "latest": "1.0.0",
            },
            "versions": {
                "1.0.0": {
                    "dist": {
                        "tarball": "https://example.com/test.tgz",
                    }
                }
            },
        }

        version, url = get_tarball_url(package_data)

        self.assertEqual(version, "1.0.0")
        self.assertEqual(
            url,
            "https://example.com/test.tgz",
        )

    def test_missing_latest_version(self):
        package_data = {
            "dist-tags": {},
            "versions": {},
        }

        with self.assertRaises(ValueError):
            get_tarball_url(package_data)

    def test_missing_version_data(self):
        package_data = {
            "dist-tags": {
                "latest": "1.0.0",
            },
            "versions": {},
        }

        with self.assertRaises(ValueError):
            get_tarball_url(package_data)

    def test_missing_tarball_url(self):
        package_data = {
            "dist-tags": {
                "latest": "1.0.0",
            },
            "versions": {
                "1.0.0": {
                    "dist": {},
                }
            },
        }

        with self.assertRaises(ValueError):
            get_tarball_url(package_data)

    def test_get_direct_dependencies(self):
        package_json = {
            "name": "test-package",
            "dependencies": {
                "package-a": "^2.0.0",
                "package-b": "^3.0.0",
            },
        }

        dependencies = get_direct_dependencies(
            package_json
        )

        self.assertEqual(
            dependencies,
            {
                "package-a": "^2.0.0",
                "package-b": "^3.0.0",
            },
        )

    def test_package_without_dependencies(self):
        package_json = {
            "name": "test-package",
        }

        dependencies = get_direct_dependencies(
            package_json
        )

        self.assertEqual(dependencies, {})

    @patch("src.main.urlopen")
    def test_fetch_package_data(self, mock_urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.read.return_value = (
            b'{"name": "express"}'
        )

        mock_urlopen.return_value = response

        data = fetch_package_data(
            "https://registry.npmjs.org",
            "express",
        )

        self.assertEqual(
            data,
            {"name": "express"},
        )

    @patch("src.main.urlopen")
    def test_download_package(self, mock_urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.read.return_value = b"archive-data"

        mock_urlopen.return_value = response

        data = download_package(
            "https://example.com/package.tgz"
        )

        self.assertEqual(
            data,
            b"archive-data",
        )

    def test_read_package_json(self):
        package_json = {
            "name": "test-package",
            "dependencies": {
                "package-a": "^1.0.0",
            },
        }

        archive_data = create_test_archive(
            package_json
        )

        result = read_package_json(
            archive_data
        )

        self.assertEqual(
            result,
            package_json,
        )

    def test_invalid_archive(self):
        with self.assertRaises(ValueError):
            read_package_json(
                b"not-a-real-archive"
            )


if __name__ == "__main__":
    unittest.main()