import argparse
import io
import json
import os
import tarfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


REQUEST_TIMEOUT = 10
MIN_DEPTH = 1
HTTP_NOT_FOUND = 404
PACKAGE_JSON_PATH = "package/package.json"


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

    if args.max_depth < MIN_DEPTH:
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
        raise ValueError("Некорректный URL репозитория")


def build_package_url(repository, package):
    package_name = quote(package, safe="@")
    repository = repository.rstrip("/")
    return f"{repository}/{package_name}"


def fetch_package_data(repository, package):
    url = build_package_url(repository, package)
    request = Request(
        url,
        headers={"Accept": "application/json"},
    )

    try:
        with urlopen(
            request,
            timeout=REQUEST_TIMEOUT,
        ) as response:
            return json.load(response)

    except HTTPError as error:
        if error.code == HTTP_NOT_FOUND:
            raise ValueError(
                f"Пакет '{package}' не найден"
            ) from error

        raise ValueError(
            f"Ошибка HTTP: {error.code}"
        ) from error

    except URLError as error:
        raise ValueError(
            f"Ошибка подключения: {error.reason}"
        ) from error

    except TimeoutError as error:
        raise ValueError(
            "Превышено время ожидания ответа"
        ) from error

    except json.JSONDecodeError as error:
        raise ValueError(
            "Репозиторий вернул некорректный JSON"
        ) from error


def get_tarball_url(package_data):
    dist_tags = package_data.get("dist-tags", {})
    latest = dist_tags.get("latest")

    if latest is None:
        raise ValueError(
            "Не удалось определить latest-версию пакета"
        )

    versions = package_data.get("versions", {})
    version_data = versions.get(latest)

    if version_data is None:
        raise ValueError(
            "Данные latest-версии пакета отсутствуют"
        )

    dist = version_data.get("dist", {})
    tarball_url = dist.get("tarball")

    if tarball_url is None:
        raise ValueError(
            "Не удалось получить ссылку на архив пакета"
        )

    return latest, tarball_url


def download_package(tarball_url):
    request = Request(tarball_url)

    try:
        with urlopen(
            request,
            timeout=REQUEST_TIMEOUT,
        ) as response:
            return response.read()

    except HTTPError as error:
        raise ValueError(
            f"Ошибка загрузки пакета: HTTP {error.code}"
        ) from error

    except URLError as error:
        raise ValueError(
            f"Ошибка загрузки пакета: {error.reason}"
        ) from error

    except TimeoutError as error:
        raise ValueError(
            "Превышено время ожидания загрузки пакета"
        ) from error


def read_package_json(archive_data):
    archive_file = io.BytesIO(archive_data)

    try:
        with tarfile.open(
            fileobj=archive_file,
            mode="r:gz",
        ) as archive:
            try:
                package_file = archive.extractfile(
                    PACKAGE_JSON_PATH
                )
            except KeyError as error:
                raise ValueError(
                    "В архиве отсутствует package.json"
                ) from error

            if package_file is None:
                raise ValueError(
                    "В архиве отсутствует package.json"
                )

            return json.load(package_file)

    except tarfile.TarError as error:
        raise ValueError(
            "Некорректный архив пакета"
        ) from error

    except json.JSONDecodeError as error:
        raise ValueError(
            "Некорректный package.json"
        ) from error


def get_direct_dependencies(package_json):
    return package_json.get("dependencies", {})


def print_dependencies(package, version, dependencies):
    print(f"Прямые зависимости {package}@{version}:")

    if not dependencies:
        print("Прямых зависимостей нет")
        return

    for name, required_version in sorted(dependencies.items()):
        print(f"{name}: {required_version}")

def analyze_package(args):
    package_data = fetch_package_data(
        args.repository,
        args.package,
    )

    version, tarball_url = get_tarball_url(
        package_data
    )

    archive_data = download_package(
        tarball_url
    )

    package_json = read_package_json(
        archive_data
    )

    dependencies = get_direct_dependencies(
        package_json
    )

    print_dependencies(
        args.package,
        version,
        dependencies,
    )

def main():
    parser = create_parser()
    args = parser.parse_args()

    try:
        validate_args(args)

        if args.test_mode:
            print(
                "Работа с тестовым репозиторием "
                "будет реализована на Этапе 3"
            )
            return

        analyze_package(args)

    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()