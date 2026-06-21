from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

from dbt_package_loom.manifests import ManifestNode


@dataclass
class VersionedGroup:
    base_name: str
    versions: List[ManifestNode] = field(default_factory=list)

    @property
    def latest(self) -> ManifestNode:
        declared = self.versions[0].latest_version
        if declared is not None:
            for n in self.versions:
                if n.version == declared:
                    return n
        return max(self.versions, key=lambda n: _version_key(n.version))

    @property
    def description(self) -> str:
        return self.versions[0].description or ""

    @property
    def latest_version_number(self) -> Union[int, str]:
        v = self.latest.version
        if v is None:
            raise ValueError(f"Versioned group '{self.base_name}' has a node with no version set")
        return v


@dataclass
class FolderContent:
    folder: str
    unversioned: List[ManifestNode] = field(default_factory=list)
    versioned_groups: Dict[str, VersionedGroup] = field(default_factory=dict)

    @property
    def database(self) -> Optional[str]:
        return self._first_node().database

    @property
    def schema_name(self) -> str:
        return self._first_node().schema_name

    def _first_node(self) -> ManifestNode:
        if self.unversioned:
            return self.unversioned[0]
        group = next(iter(self.versioned_groups.values()))
        return group.versions[0]


def _version_key(v: Optional[Union[int, str]]) -> Union[int, str]:
    if v is None:
        return 0
    try:
        return int(v)
    except (ValueError, TypeError):
        return str(v)


def group_nodes_by_folder(nodes: List[ManifestNode]) -> Dict[str, FolderContent]:
    folders: Dict[str, FolderContent] = {}

    for node in nodes:
        folder = node.folder
        if folder not in folders:
            folders[folder] = FolderContent(folder=folder)
        fc = folders[folder]

        if node.version is not None:
            if node.name not in fc.versioned_groups:
                fc.versioned_groups[node.name] = VersionedGroup(base_name=node.name)
            fc.versioned_groups[node.name].versions.append(node)
        else:
            fc.unversioned.append(node)

    for fc in folders.values():
        for vg in fc.versioned_groups.values():
            vg.versions.sort(key=lambda n: _version_key(n.version))

    return folders


def build_dbt_project_yml(project_name: str) -> str:
    return (
        f"name: {project_name}\n"
        "version: '1.0.0'\n"
        "config-version: 2\n"
        "\n"
        f"models:\n"
        f"  {project_name}:\n"
        "    +materialized: ephemeral\n"
        "    +tags:\n"
        "      - package-mesh-stub\n"
    )


def build_sources_yml(project_name: str, folder_content: FolderContent) -> str:
    tables: List[str] = []

    for node in folder_content.unversioned:
        alias = node.alias or node.name
        desc = node.description or ""
        tables.append(
            f"      - name: {alias}\n"
            f"        identifier: {alias}\n"
            f'        description: "{desc}"\n'
        )

    for vg in folder_content.versioned_groups.values():
        for node in vg.versions:
            alias = node.alias or node.name
            desc = node.description or ""
            tables.append(
                f"      - name: {alias}\n"
                f"        identifier: {alias}\n"
                f'        description: "{desc}"\n'
            )

    database_line = (
        f"    database: {folder_content.database}\n" if folder_content.database else ""
    )
    tables_block = "".join(tables)
    return (
        "version: 2\n"
        "\n"
        "sources:\n"
        f"  - name: {project_name}\n"
        f"{database_line}"
        f"    schema: {folder_content.schema_name}\n"
        "    tables:\n"
        f"{tables_block}"
    )


def build_schema_yml(folder_content: FolderContent) -> str:
    model_entries: List[str] = []

    for node in folder_content.unversioned:
        desc = node.description or ""
        model_entries.append(f'  - name: {node.name}\n    description: "{desc}"\n')

    for vg in folder_content.versioned_groups.values():
        desc = vg.description
        lv = vg.latest_version_number
        versions_block = "".join(
            f"      - v: {n.version}\n        defined_in: {n.alias or n.name}\n"
            for n in vg.versions
        )
        model_entries.append(
            f"  - name: {vg.base_name}\n"
            f'    description: "{desc}"\n'
            f"    latest_version: {lv}\n"
            f"    versions:\n"
            f"{versions_block}"
        )

    models_block = "".join(model_entries)
    return "version: 2\n\nmodels:\n" + models_block


def build_stub_sql(project_name: str, node: ManifestNode) -> str:
    alias = node.alias or node.name
    return (
        "-- Generated by dbt-package-loom. Do not edit.\n"
        f"select * from {{{{ source('{project_name}', '{alias}') }}}}\n"
    )


def build_alias_stub_sql(project_name: str, vg: VersionedGroup) -> str:
    latest_alias = vg.latest.alias or vg.latest.name
    lv = vg.latest_version_number
    return (
        "-- Generated by dbt-package-loom. Do not edit.\n"
        f"-- Alias for latest version (v{lv})\n"
        f"select * from {{{{ source('{project_name}', '{latest_alias}') }}}}\n"
    )
