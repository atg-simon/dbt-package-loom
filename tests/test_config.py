import pytest
from pydantic import ValidationError

from dbt_package_loom.clients.dbt_cloud import DbtCloudReferenceConfig
from dbt_package_loom.clients.paradime import ParadimeReferenceConfig
from dbt_package_loom.config import (
    FileReferenceConfig,
    ManifestReference,
    dbtLoomConfig,
)


class TestFileReferenceConfig:
    def test_bare_path_normalized_to_file_uri(self):
        cfg = FileReferenceConfig(path="./target/manifest.json")
        assert cfg.path == "file://./target/manifest.json"

    def test_absolute_path_normalized(self):
        cfg = FileReferenceConfig(path="/tmp/manifest.json")
        assert cfg.path == "file:///tmp/manifest.json"

    def test_file_uri_unchanged(self):
        cfg = FileReferenceConfig(path="file:///abs/manifest.json")
        assert cfg.path == "file:///abs/manifest.json"

    def test_http_url_unchanged(self):
        cfg = FileReferenceConfig(path="http://example.com/manifest.json")
        assert cfg.path == "http://example.com/manifest.json"

    def test_https_url_unchanged(self):
        cfg = FileReferenceConfig(path="https://example.com/manifest.json")
        assert cfg.path == "https://example.com/manifest.json"


class TestManifestReference:
    def test_file_type_resolves_config(self):
        ref = ManifestReference.model_validate(
            {
                "name": "jaffle_finance",
                "type": "file",
                "config": {"path": "./manifest.json"},
            }
        )
        assert isinstance(ref.config, FileReferenceConfig)
        assert ref.config.path == "file://./manifest.json"

    def test_dbt_cloud_type_resolves_config(self):
        ref = ManifestReference.model_validate(
            {
                "name": "jaffle_finance",
                "type": "dbt_cloud",
                "config": {"account_id": 123, "job_id": 456},
            }
        )
        assert isinstance(ref.config, DbtCloudReferenceConfig)
        assert ref.config.account_id == 123
        assert ref.config.job_id == 456

    def test_dbt_cloud_default_endpoint(self):
        ref = ManifestReference.model_validate(
            {
                "name": "proj",
                "type": "dbt_cloud",
                "config": {"account_id": 1, "job_id": 2},
            }
        )
        assert ref.config.api_endpoint == "https://cloud.getdbt.com/api/v2"

    def test_paradime_type_resolves_config(self):
        ref = ManifestReference.model_validate(
            {
                "name": "proj",
                "type": "paradime",
                "config": {"schedule_name": "daily_prod"},
            }
        )
        assert isinstance(ref.config, ParadimeReferenceConfig)
        assert ref.config.schedule_name == "daily_prod"

    def test_optional_defaults_to_false(self):
        ref = ManifestReference.model_validate(
            {"name": "x", "type": "file", "config": {"path": "./m.json"}}
        )
        assert ref.optional is False

    def test_optional_can_be_set(self):
        ref = ManifestReference.model_validate(
            {
                "name": "x",
                "type": "file",
                "config": {"path": "./m.json"},
                "optional": True,
            }
        )
        assert ref.optional is True

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            ManifestReference.model_validate(
                {"name": "x", "type": "not_a_type", "config": {}}
            )


class TestDbtLoomConfig:
    def test_parse_single_file_manifest(self):
        cfg = dbtLoomConfig.model_validate(
            {
                "manifests": [
                    {"name": "proj", "type": "file", "config": {"path": "./m.json"}}
                ]
            }
        )
        assert len(cfg.manifests) == 1
        assert cfg.manifests[0].name == "proj"

    def test_parse_multiple_manifests(self):
        cfg = dbtLoomConfig.model_validate(
            {
                "manifests": [
                    {"name": "a", "type": "file", "config": {"path": "./a.json"}},
                    {"name": "b", "type": "file", "config": {"path": "./b.json"}},
                ]
            }
        )
        assert len(cfg.manifests) == 2

    def test_enable_telemetry_optional(self):
        cfg = dbtLoomConfig.model_validate(
            {
                "manifests": [
                    {"name": "a", "type": "file", "config": {"path": "./a.json"}}
                ]
            }
        )
        assert cfg.enable_telemetry is None

    def test_enable_telemetry_parsed(self):
        cfg = dbtLoomConfig.model_validate(
            {
                "enable_telemetry": False,
                "manifests": [
                    {"name": "a", "type": "file", "config": {"path": "./a.json"}}
                ],
            }
        )
        assert cfg.enable_telemetry is False
