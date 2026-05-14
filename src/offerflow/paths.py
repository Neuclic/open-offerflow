from __future__ import annotations

from pathlib import Path


def project_dir() -> Path:
    return Path.cwd()


def runtime_dir(base_dir: Path | None = None) -> Path:
    return (base_dir or project_dir()) / ".offerflow"


def logs_dir(base_dir: Path | None = None) -> Path:
    return runtime_dir(base_dir) / "logs"


def db_path(base_dir: Path | None = None) -> Path:
    return runtime_dir(base_dir) / "offerflow.sqlite"


def migrations_dir() -> Path:
    package_file = Path(__file__).resolve()
    for root in (Path.cwd(), package_file.parents[2], package_file.parents[1]):
        candidate = root / "migrations"
        if candidate.exists():
            return candidate
    return package_file.parents[2] / "migrations"
