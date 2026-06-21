from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import List

from dbt_package_loom.generator import (
    FolderContent,
    build_alias_stub_sql,
    build_dbt_project_yml,
    build_schema_yml,
    build_sources_yml,
    build_stub_sql,
    group_nodes_by_folder,
)
from dbt_package_loom.manifests import ManifestNode

logger = logging.getLogger(__name__)


def write_package(
    project_name: str,
    nodes: List[ManifestNode],
    output_dir: str = "dbt_packages",
) -> None:
    package_root = Path(output_dir) / project_name

    if package_root.exists():
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True)

    _write_file(package_root / "dbt_project.yml", build_dbt_project_yml(project_name))

    folders = group_nodes_by_folder(nodes)
    for folder_content in folders.values():
        _write_folder(project_name, folder_content, package_root)

    logger.info(
        "Wrote %d public model(s) into %s", len(nodes), package_root
    )


def _write_folder(
    project_name: str,
    fc: FolderContent,
    package_root: Path,
) -> None:
    if fc.folder:
        models_dir = package_root / "models" / fc.folder
    else:
        models_dir = package_root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    _write_file(models_dir / "sources.yml", build_sources_yml(project_name, fc))
    _write_file(models_dir / "schema.yml", build_schema_yml(fc))

    for node in fc.unversioned:
        filename = f"{node.name}.sql"
        _write_file(models_dir / filename, build_stub_sql(project_name, node))

    for vg in fc.versioned_groups.values():
        for node in vg.versions:
            filename = f"{node.alias or node.name}.sql"
            _write_file(models_dir / filename, build_stub_sql(project_name, node))
        alias_filename = f"{vg.base_name}.sql"
        _write_file(models_dir / alias_filename, build_alias_stub_sql(project_name, vg))


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    logger.debug("Wrote %s", path)
