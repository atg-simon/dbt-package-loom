# Copyright 2023 Nicholas Yager and Contributors. Adapted under Apache 2.0.
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, field_validator, model_validator


class ManifestReferenceType(str, Enum):
    file = "file"
    dbt_cloud = "dbt_cloud"
    paradime = "paradime"
    s3 = "s3"
    gcs = "gcs"
    azure = "azure"
    snowflake = "snowflake"
    databricks = "databricks"


class FileReferenceConfig(BaseModel):
    path: str

    @field_validator("path")
    @classmethod
    def normalize_path(cls, v: str) -> str:
        if not v.startswith(("file://", "http://", "https://")):
            return f"file://{v}"
        return v


def _build_type_to_config() -> dict:
    from dbt_package_loom.clients.dbt_cloud import DbtCloudReferenceConfig
    from dbt_package_loom.clients.paradime import ParadimeReferenceConfig

    return {
        ManifestReferenceType.file: FileReferenceConfig,
        ManifestReferenceType.dbt_cloud: DbtCloudReferenceConfig,
        ManifestReferenceType.paradime: ParadimeReferenceConfig,
    }


class ManifestReference(BaseModel):
    name: str
    type: ManifestReferenceType
    config: Any = None
    excluded_packages: Optional[List[str]] = None
    included_packages: Optional[List[str]] = None
    optional: bool = False

    @model_validator(mode="after")
    def resolve_config_type(self) -> "ManifestReference":
        type_to_config = _build_type_to_config()
        config_class = type_to_config.get(self.type)
        if config_class is not None and self.config is not None:
            if not isinstance(self.config, config_class):
                self.config = config_class(**self.config)
        return self


class dbtLoomConfig(BaseModel):
    manifests: List[ManifestReference]
    enable_telemetry: Optional[bool] = None
