from __future__ import annotations

from typing import Any


def validate_strict_json_schema(*, schema_name: str, schema: dict[str, Any]) -> None:
    _validate_schema_node(schema_name=schema_name, node=schema, path="$")


def _validate_schema_node(*, schema_name: str, node: Any, path: str) -> None:
    if not isinstance(node, dict):
        return

    node_type = node.get("type")
    if node_type == "object":
        _validate_object_schema(schema_name=schema_name, node=node, path=path)

    properties = node.get("properties")
    if isinstance(properties, dict):
        for key, child in properties.items():
            _validate_schema_node(schema_name=schema_name, node=child, path=f"{path}.properties.{key}")

    items = node.get("items")
    if items is not None:
        _validate_schema_node(schema_name=schema_name, node=items, path=f"{path}.items")

    for branch_key in ("anyOf", "allOf", "oneOf"):
        branches = node.get(branch_key)
        if isinstance(branches, list):
            for index, branch in enumerate(branches):
                _validate_schema_node(
                    schema_name=schema_name,
                    node=branch,
                    path=f"{path}.{branch_key}[{index}]",
                )


def _validate_object_schema(*, schema_name: str, node: dict[str, Any], path: str) -> None:
    properties = node.get("properties")
    required = node.get("required")
    if properties is None and required is None and "additionalProperties" in node:
        return
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise RuntimeError(
            f"Structured-output schema '{schema_name}' is invalid at {path}: "
            "object nodes must define properties and required keys"
        )
    property_keys = set(properties.keys())
    required_keys = {key for key in required if isinstance(key, str)}
    if property_keys != required_keys:
        missing = sorted(property_keys - required_keys)
        extra = sorted(required_keys - property_keys)
        issues: list[str] = []
        if missing:
            issues.append(f"missing from required: {', '.join(missing)}")
        if extra:
            issues.append(f"not present in properties: {', '.join(extra)}")
        detail = "; ".join(issues) if issues else "properties/required mismatch"
        raise RuntimeError(f"Structured-output schema '{schema_name}' is invalid at {path} ({detail})")
