from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


class ContractValidationError(ValueError):
    pass


@lru_cache(maxsize=1)
def contract_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "contracts"
        if (candidate / "evidence_bundle.schema.json").exists():
            return candidate
    raise RuntimeError("repository-root contracts/ directory was not found")


@lru_cache(maxsize=1)
def _schemas() -> dict[str, dict]:
    result: dict[str, dict] = {}
    for path in contract_dir().glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        result[path.name] = schema
    return result


@lru_cache(maxsize=1)
def _registry() -> Registry:
    resources = []
    for name, schema in _schemas().items():
        resource = Resource.from_contents(schema)
        resources.append((name, resource))
        if schema.get("$id"):
            resources.append((schema["$id"], resource))
    return Registry().with_resources(resources)


def validate_contract(name: str, obj: object) -> None:
    filename = name if name.endswith(".schema.json") else f"{name}.schema.json"
    try:
        schema = _schemas()[filename]
    except KeyError as exc:
        raise ContractValidationError(f"unknown contract: {filename}") from exc
    validator = Draft202012Validator(
        schema,
        registry=_registry(),
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(obj), key=lambda error: list(error.absolute_path))
    if errors:
        message = "; ".join(
            f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ContractValidationError(message)
