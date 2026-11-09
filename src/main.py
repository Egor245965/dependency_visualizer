import argparse
import io
import json
import os
import subprocess
import tarfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


REQUEST_TIMEOUT = 30
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


def is_valid_test_package(package):
    return (
        isinstance(package, str)
        and package.isascii()
        and package.isalpha()
        and package.isupper()
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

        if not is_valid_test_package(args.package):
            raise ValueError(
                "В тестовом режиме имя пакета должно "
                "состоять из заглавных латинских букв"
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


def get_real_dependencies(
    package,
    repository,
    cache,
    versions=None,
):
    if package in cache:
        return cache[package]

    package_data = fetch_package_data(
        repository,
        package,
    )

    version, tarball_url = get_tarball_url(
        package_data
    )

    if versions is not None:
        versions[package] = version

    archive_data = download_package(
        tarball_url
    )

    package_json = read_package_json(
        archive_data
    )

    dependencies = set(
        get_direct_dependencies(package_json)
    )

    cache[package] = dependencies
    return dependencies


def get_real_version(package, repository):
    package_data = fetch_package_data(
        repository,
        package,
    )
    version, _ = get_tarball_url(
        package_data
    )
    return version


def fill_missing_versions(graph, repository, versions):
    for package in sorted(graph):
        if package not in versions:
            versions[package] = get_real_version(
                package,
                repository,
            )


def validate_test_repository(repository):
    for package, dependencies in repository.items():
        if not is_valid_test_package(package):
            raise ValueError(
                "Имена тестовых пакетов должны состоять "
                "из заглавных латинских букв"
            )

        if not isinstance(dependencies, list):
            raise ValueError(
                "Зависимости тестового пакета должны быть списком"
            )

        if not all(
            is_valid_test_package(item)
            for item in dependencies
        ):
            raise ValueError(
                "Имена зависимостей должны состоять "
                "из заглавных латинских букв"
            )

        if not all(
            item in repository
            for item in dependencies
        ):
            raise ValueError(
                "Все зависимости должны быть описаны "
                "в тестовом репозитории"
            )


def load_test_repository(path):
    try:
        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:
            repository = json.load(file)

    except json.JSONDecodeError as error:
        raise ValueError(
            "Некорректный файл тестового репозитория"
        ) from error

    if not isinstance(repository, dict):
        raise ValueError(
            "Тестовый репозиторий должен быть объектом JSON"
        )

    validate_test_repository(repository)
    return repository


def get_test_dependencies(package, repository):
    if package not in repository:
        raise ValueError(
            f"Пакет '{package}' отсутствует "
            "в тестовом репозитории"
        )

    return set(repository[package])


def should_skip_package(package, depth, visited_depths):
    previous_depth = visited_depths.get(package)

    return (
        previous_depth is not None
        and previous_depth <= depth
    )


def dfs(
    package,
    depth,
    max_depth,
    graph,
    visited_depths,
    get_dependencies,
):
    if should_skip_package(
        package,
        depth,
        visited_depths,
    ):
        return

    visited_depths[package] = depth
    graph.setdefault(package, set())

    if depth >= max_depth:
        return

    dependencies = set(get_dependencies(package))
    graph[package].update(dependencies)

    for dependency in sorted(dependencies):
        graph.setdefault(
            dependency,
            set(),
        )

        dfs(
            dependency,
            depth + 1,
            max_depth,
            graph,
            visited_depths,
            get_dependencies,
        )


def build_graph(package, max_depth, get_dependencies):
    graph = {}
    visited_depths = {}

    dfs(
        package,
        0,
        max_depth,
        graph,
        visited_depths,
        get_dependencies,
    )

    return graph


def build_real_graph(
    package,
    repository,
    max_depth,
    versions=None,
):
    cache = {}
    version_map = versions if versions is not None else {}

    def get_dependencies(current_package):
        return get_real_dependencies(
            current_package,
            repository,
            cache,
            version_map,
        )

    graph = build_graph(
        package,
        max_depth,
        get_dependencies,
    )

    if versions is not None:
        fill_missing_versions(
            graph,
            repository,
            version_map,
        )

    return graph


def build_test_graph(package, repository, max_depth):
    if package not in repository:
        raise ValueError(
            f"Пакет '{package}' отсутствует "
            "в тестовом репозитории"
        )

    def get_dependencies(current_package):
        return get_test_dependencies(
            current_package,
            repository,
        )

    return build_graph(
        package,
        max_depth,
        get_dependencies,
    )


def print_graph(graph):
    print("Граф зависимостей:")

    for package in sorted(graph):
        dependencies = sorted(
            graph[package]
        )

        if dependencies:
            print(
                f"{package}: "
                f"{', '.join(dependencies)}"
            )
        else:
            print(
                f"{package}: нет зависимостей"
            )


def load_order_dfs(package, graph, visited, order):
    if package in visited:
        return

    visited.add(package)

    for dependency in sorted(graph.get(package, set())):
        load_order_dfs(
            dependency,
            graph,
            visited,
            order,
        )

    order.append(package)


def build_load_order(graph, package):
    order = []
    visited = set()

    load_order_dfs(
        package,
        graph,
        visited,
        order,
    )

    return order


def print_load_order(order):
    print("Порядок загрузки (зависимости -> пакет):")
    print(" -> ".join(order))


def escape_dot(value):
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
    )


def build_graphviz(graph, versions=None):
    lines = [
        "digraph dependencies {",
        "    rankdir=LR;",
    ]
    version_map = versions or {}

    for package in sorted(graph):
        name = escape_dot(package)
        version = version_map.get(package)

        if version is None:
            lines.append(f'    "{name}";')
        else:
            safe_version = escape_dot(version)
            label = f"{name}\\n{safe_version}"
            lines.append(
                f'    "{name}" [label="{label}"];'
            )

    for package in sorted(graph):
        source = escape_dot(package)

        for dependency in sorted(graph[package]):
            target = escape_dot(dependency)
            lines.append(
                f'    "{source}" -> "{target}";'
            )

    lines.append("}")
    return "\n".join(lines)


def save_graph_png(graphviz_text, output):
    if not output.lower().endswith(".png"):
        raise ValueError(
            "Файл изображения должен иметь расширение .png"
        )

    try:
        subprocess.run(
            ["dot", "-Tpng", "-o", output],
            input=graphviz_text,
            text=True,
            capture_output=True,
            check=True,
        )

    except FileNotFoundError as error:
        raise ValueError(
            "Graphviz не найден. Команда dot недоступна"
        ) from error

    except subprocess.CalledProcessError as error:
        message = error.stderr.strip()

        raise ValueError(
            f"Ошибка Graphviz: {message}"
        ) from error


def ascii_tree_dfs(
    package,
    graph,
    prefix,
    is_last,
    visited,
    lines,
):
    connector = "`-- " if is_last else "|-- "
    lines.append(prefix + connector + package)

    if package in visited:
        lines[-1] += " [повтор]"
        return

    visited.add(package)
    dependencies = sorted(
        graph.get(package, set())
    )

    child_prefix = (
        prefix + ("    " if is_last else "|   ")
    )

    for index, dependency in enumerate(dependencies):
        ascii_tree_dfs(
            dependency,
            graph,
            child_prefix,
            index == len(dependencies) - 1,
            visited,
            lines,
        )


def build_ascii_tree(graph, package):
    lines = [package]
    visited = {package}

    dependencies = sorted(
        graph.get(package, set())
    )

    for index, dependency in enumerate(dependencies):
        ascii_tree_dfs(
            dependency,
            graph,
            "",
            index == len(dependencies) - 1,
            visited,
            lines,
        )

    return "\n".join(lines)


def print_graphviz(graphviz_text):
    print("Graphviz-представление:")
    print(graphviz_text)


def print_ascii_tree(tree):
    print("ASCII-дерево:")
    print(tree)


def analyze(args, versions=None):
    if args.test_mode:
        repository = load_test_repository(
            args.repository
        )

        return build_test_graph(
            args.package,
            repository,
            args.max_depth,
        )

    return build_real_graph(
        args.package,
        args.repository,
        args.max_depth,
        versions,
    )


def main():
    parser = create_parser()
    args = parser.parse_args()

    try:
        validate_args(args)
        versions = {}
        graph = analyze(args, versions)
        graphviz_text = build_graphviz(
            graph,
            versions,
        )

        print_graphviz(graphviz_text)

        save_graph_png(
            graphviz_text,
            args.output,
        )

        print(
            f"Изображение сохранено: {args.output}"
        )

        if args.ascii_tree:
            tree = build_ascii_tree(
                graph,
                args.package,
            )
            print_ascii_tree(tree)

    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()