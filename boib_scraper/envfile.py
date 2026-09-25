"""Carga variables sencillas desde el fichero local .env."""

import os
from pathlib import Path


def load_env_file(path: Path) -> None:
    """Carga pares KEY=VALUE sin sustituir variables ya definidas en el entorno."""
    if not path.is_file():
        return

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key or not key.replace("_", "a").isalnum() or key[0].isdigit():
            raise ValueError(f"Línea {line_number} no válida en {path.name}; usa KEY=VALUE")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)
