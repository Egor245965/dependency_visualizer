import argparse
import os
from urllib.parse import urlparse


def create_parser():
    parser = argparse.ArgumentParser(
        description="Визуализатор графа зависимостей"
    )
    parser.add_argument(
        "--package",
        required=True,
        help="Имя анализируемого пакета",
    )
    parser.add_argument(
        "--repository",
        required=True,
        help="URL репозитория или путь к тестовому файлу",
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Использовать тестовый репозиторий",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Имя файла с изображением графа",
    )
    parser.add_argument(
        "--ascii-tree",
        action="store_true",
        help="Выводить зависимости в виде ASCII-дерева",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        required=True,
        help="Максимальная глубина анализа",
    )
    return parser


def validate_url(repository):
    parsed = urlparse(repository)

    return (
        parsed.scheme in ("http", "https")
        and bool(parsed.netloc)
    )


def validate_args(args):
    if not args.package.strip():
        raise ValueError("Имя пакета не может быть пустым")

    if args.max_depth <= 0:
        raise ValueError(
            "Максимальная глубина должна быть больше нуля"
        )

    if not args.output.strip():
        raise ValueError(
            "Имя выходного файла не может быть пустым"
        )

    if args.test_mode:
        if not os.path.isfile(args.repository):
            raise ValueError(
                "Файл тестового репозитория не найден"
            )
    elif not validate_url(args.repository):
        raise ValueError(
            "Некорректный URL репозитория"
        )


def print_config(args):
    print("Параметры:")
    print(f"package: {args.package}")
    print(f"repository: {args.repository}")
    print(f"test_mode: {args.test_mode}")
    print(f"output: {args.output}")
    print(f"ascii_tree: {args.ascii_tree}")
    print(f"max_depth: {args.max_depth}")


def main():
    parser = create_parser()
    args = parser.parse_args()

    try:
        validate_args(args)
    except ValueError as error:
        parser.error(str(error))

    print_config(args)


if __name__ == "__main__":
    main()