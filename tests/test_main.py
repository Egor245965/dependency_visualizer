import argparse
import os
import tempfile
import unittest

from src.main import validate_args, validate_url


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
        args = argparse.Namespace(
            package=" ",
            repository="https://registry.npmjs.org",
            test_mode=False,
            output="graph.png",
            ascii_tree=False,
            max_depth=3,
        )

        with self.assertRaises(ValueError):
            validate_args(args)

    def test_invalid_depth(self):
        args = argparse.Namespace(
            package="react",
            repository="https://registry.npmjs.org",
            test_mode=False,
            output="graph.png",
            ascii_tree=False,
            max_depth=0,
        )

        with self.assertRaises(ValueError):
            validate_args(args)

    def test_empty_output(self):
        args = argparse.Namespace(
            package="react",
            repository="https://registry.npmjs.org",
            test_mode=False,
            output=" ",
            ascii_tree=False,
            max_depth=3,
        )

        with self.assertRaises(ValueError):
            validate_args(args)

    def test_invalid_repository(self):
        args = argparse.Namespace(
            package="react",
            repository="hello",
            test_mode=False,
            output="graph.png",
            ascii_tree=False,
            max_depth=3,
        )

        with self.assertRaises(ValueError):
            validate_args(args)

    def test_missing_test_file(self):
        args = argparse.Namespace(
            package="react",
            repository="missing.txt",
            test_mode=True,
            output="graph.png",
            ascii_tree=False,
            max_depth=3,
        )

        with self.assertRaises(ValueError):
            validate_args(args)

    def test_existing_test_file(self):
        with tempfile.NamedTemporaryFile(
            delete=False
        ) as file:
            path = file.name

        try:
            args = argparse.Namespace(
                package="react",
                repository=path,
                test_mode=True,
                output="graph.png",
                ascii_tree=False,
                max_depth=3,
            )

            validate_args(args)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()