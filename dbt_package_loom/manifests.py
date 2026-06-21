# Copyright 2023 Nicholas Yager and Contributors. Adapted under Apache 2.0.
import gzip
import json
import logging
import re
from pathlib import PurePosixPath
from typing import Dict, List, Optional, Union

import requests
from pydantic import BaseModel, Field

from dbt_package_loom.clients import is_gzipped
from dbt_package_loom.config import ManifestReference, ManifestReferenceType

logger = logging.getLogger(__name__)


class ManifestNode(BaseModel):
    name: str
    package_name: str
    unique_id: str
    resource_type: str
    schema_name: str = Field(alias="schema")
    database: Optional[str] = None
    relation_name: Optional[str] = None
    version: Optional[Union[int, str]] = None
    latest_version: Optional[Union[int, str]] = None
    access: Optional[str] = None
    path: str = ""
    alias: Optional[str] = None

    model_config = {"populate_by_name": True}

    @property
    def identifier(self) -> str:
        if self.relation_name:
            last_segment = self.relation_name.split(".")[-1]
            return re.sub(r'["`\[\]]', "", last_segment)
        return self.name

    @property
    def folder(self) -> str:
        return str(PurePosixPath(self.path).parent).replace("\\", "/").strip("/.")


class ManifestLoader:
    def __init__(self, reference: ManifestReference) -> None:
        self.reference = reference

    def load(self) -> Dict:
        ref_type = self.reference.type
        config = self.reference.config

        if ref_type == ManifestReferenceType.file:
            return self._load_file(config)
        if ref_type == ManifestReferenceType.dbt_cloud:
            from dbt_package_loom.clients.dbt_cloud import DbtCloud

            return DbtCloud(config).get_latest_manifest()
        if ref_type == ManifestReferenceType.paradime:
            from dbt_package_loom.clients.paradime import ParadimeClient

            return ParadimeClient(config).get_latest_manifest()
        raise NotImplementedError(
            f"Source type '{ref_type.value}' is not yet implemented. "
            "Supported: file, dbt_cloud, paradime."
        )

    def _load_file(self, config) -> Dict:
        path: str = config.path
        if path.startswith(("http://", "https://")):
            response = requests.get(path, timeout=30)
            response.raise_for_status()
            content = response.content
        else:
            local_path = path.removeprefix("file://")
            with open(local_path, "rb") as fh:
                content = fh.read()

        if is_gzipped(content):
            content = gzip.decompress(content)

        return json.loads(content)

    def get_public_models(self, manifest: Dict) -> List[ManifestNode]:
        project_name = self.reference.name
        result: List[ManifestNode] = []
        for node_data in manifest.get("nodes", {}).values():
            if (
                node_data.get("resource_type") == "model"
                and node_data.get("access") == "public"
                and node_data.get("package_name") == project_name
            ):
                result.append(ManifestNode.model_validate(node_data))
        return result
