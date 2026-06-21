"""Shared fixtures for dbt-package-loom tests."""
import json
from pathlib import Path

import pytest

from dbt_package_loom.manifests import ManifestNode


def _node(
    name: str,
    *,
    package_name: str = "jaffle_finance",
    schema: str = "integrated",
    database: str = "jaffle_finance_prod",
    alias: str | None = None,
    relation_name: str | None = None,
    path: str | None = None,
    version: int | None = None,
    latest_version: int | None = None,
    description: str = "",
    access: str = "public",
    resource_type: str = "model",
) -> ManifestNode:
    alias = alias or name
    relation_name = relation_name or f'"{database}"."{schema}"."{alias}"'
    path = path or f"{schema}/{alias}.sql"
    return ManifestNode.model_validate(
        {
            "name": name,
            "package_name": package_name,
            "unique_id": f"model.{package_name}.{name}",
            "resource_type": resource_type,
            "schema": schema,
            "database": database,
            "alias": alias,
            "relation_name": relation_name,
            "version": version,
            "latest_version": latest_version,
            "description": description,
            "access": access,
            "path": path,
        }
    )


@pytest.fixture
def dim_customer() -> ManifestNode:
    return _node("dim_customer", schema="conformed", path="conformed/dim_customer.sql")


@pytest.fixture
def fct_booking_v1() -> ManifestNode:
    return _node(
        "fct_booking",
        alias="fct_booking_v1",
        path="integrated/fct_booking_v1.sql",
        version=1,
        latest_version=2,
    )


@pytest.fixture
def fct_booking_v2() -> ManifestNode:
    return _node(
        "fct_booking",
        alias="fct_booking_v2",
        path="integrated/fct_booking_v2.sql",
        version=2,
        latest_version=2,
    )


@pytest.fixture
def manifest_json(tmp_path: Path, dim_customer, fct_booking_v1, fct_booking_v2) -> Path:
    manifest = {
        "nodes": {
            "model.jaffle_finance.dim_customer": dim_customer.model_dump(by_alias=True),
            "model.jaffle_finance.fct_booking.v1": fct_booking_v1.model_dump(by_alias=True),
            "model.jaffle_finance.fct_booking.v2": fct_booking_v2.model_dump(by_alias=True),
        }
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


@pytest.fixture
def loom_config_file(tmp_path: Path, manifest_json: Path) -> Path:
    config = tmp_path / "dbt_loom.config.yml"
    config.write_text(
        f"manifests:\n"
        f"  - name: jaffle_finance\n"
        f"    type: file\n"
        f"    config:\n"
        f"      path: {manifest_json}\n",
        encoding="utf-8",
    )
    return config
