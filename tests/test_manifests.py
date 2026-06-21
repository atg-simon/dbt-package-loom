import gzip
import json
from pathlib import Path

import pytest

from dbt_package_loom.config import ManifestReference
from dbt_package_loom.manifests import ManifestLoader, ManifestNode


class TestManifestNodeIdentifier:
    def test_strips_double_quotes(self):
        node = ManifestNode.model_validate(
            {
                "name": "fct_booking",
                "package_name": "proj",
                "unique_id": "model.proj.fct_booking",
                "resource_type": "model",
                "schema": "integrated",
                "relation_name": '"prod_db"."integrated"."fct_booking"',
            }
        )
        assert node.identifier == "fct_booking"

    def test_strips_backtick_quotes(self):
        node = ManifestNode.model_validate(
            {
                "name": "fct_booking",
                "package_name": "proj",
                "unique_id": "model.proj.fct_booking",
                "resource_type": "model",
                "schema": "integrated",
                "relation_name": "`prod_db`.`integrated`.`fct_booking`",
            }
        )
        assert node.identifier == "fct_booking"

    def test_strips_bracket_quotes(self):
        node = ManifestNode.model_validate(
            {
                "name": "fct_booking",
                "package_name": "proj",
                "unique_id": "model.proj.fct_booking",
                "resource_type": "model",
                "schema": "integrated",
                "relation_name": "[prod_db].[integrated].[fct_booking]",
            }
        )
        assert node.identifier == "fct_booking"

    def test_falls_back_to_name_when_no_relation_name(self):
        node = ManifestNode.model_validate(
            {
                "name": "fct_booking",
                "package_name": "proj",
                "unique_id": "model.proj.fct_booking",
                "resource_type": "model",
                "schema": "integrated",
            }
        )
        assert node.identifier == "fct_booking"

    def test_versioned_model_identifier(self):
        node = ManifestNode.model_validate(
            {
                "name": "fct_booking",
                "package_name": "proj",
                "unique_id": "model.proj.fct_booking.v1",
                "resource_type": "model",
                "schema": "integrated",
                "relation_name": '"prod_db"."integrated"."fct_booking_v1"',
                "version": 1,
            }
        )
        assert node.identifier == "fct_booking_v1"


class TestManifestNodeFolder:
    def test_folder_from_path(self):
        node = ManifestNode.model_validate(
            {
                "name": "fct_booking",
                "package_name": "proj",
                "unique_id": "model.proj.fct_booking",
                "resource_type": "model",
                "schema": "integrated",
                "path": "integrated/fct_booking.sql",
            }
        )
        assert node.folder == "integrated"

    def test_root_folder_when_no_subdirectory(self):
        node = ManifestNode.model_validate(
            {
                "name": "fct_booking",
                "package_name": "proj",
                "unique_id": "model.proj.fct_booking",
                "resource_type": "model",
                "schema": "integrated",
                "path": "fct_booking.sql",
            }
        )
        assert node.folder == ""

    def test_nested_folder(self):
        node = ManifestNode.model_validate(
            {
                "name": "dim_x",
                "package_name": "proj",
                "unique_id": "model.proj.dim_x",
                "resource_type": "model",
                "schema": "conformed",
                "path": "conformed/nested/dim_x.sql",
            }
        )
        assert node.folder == "conformed/nested"


class TestManifestLoaderGetPublicModels:
    def _make_ref(self) -> ManifestReference:
        return ManifestReference.model_validate(
            {"name": "jaffle_finance", "type": "file", "config": {"path": "./m.json"}}
        )

    def test_filters_to_public_models(self):
        loader = ManifestLoader(self._make_ref())
        manifest = {
            "nodes": {
                "model.jaffle_finance.pub": {
                    "name": "pub",
                    "package_name": "jaffle_finance",
                    "unique_id": "model.jaffle_finance.pub",
                    "resource_type": "model",
                    "schema": "integrated",
                    "access": "public",
                },
                "model.jaffle_finance.priv": {
                    "name": "priv",
                    "package_name": "jaffle_finance",
                    "unique_id": "model.jaffle_finance.priv",
                    "resource_type": "model",
                    "schema": "integrated",
                    "access": "protected",
                },
            }
        }
        result = loader.get_public_models(manifest)
        assert len(result) == 1
        assert result[0].name == "pub"

    def test_excludes_other_packages(self):
        loader = ManifestLoader(self._make_ref())
        manifest = {
            "nodes": {
                "model.other_project.pub": {
                    "name": "pub",
                    "package_name": "other_project",
                    "unique_id": "model.other_project.pub",
                    "resource_type": "model",
                    "schema": "integrated",
                    "access": "public",
                }
            }
        }
        result = loader.get_public_models(manifest)
        assert result == []

    def test_excludes_non_model_resources(self):
        loader = ManifestLoader(self._make_ref())
        manifest = {
            "nodes": {
                "seed.jaffle_finance.raw_orders": {
                    "name": "raw_orders",
                    "package_name": "jaffle_finance",
                    "unique_id": "seed.jaffle_finance.raw_orders",
                    "resource_type": "seed",
                    "schema": "raw",
                    "access": "public",
                }
            }
        }
        result = loader.get_public_models(manifest)
        assert result == []


class TestManifestLoaderLoadFile:
    def _make_file_ref(self, path: str) -> ManifestReference:
        return ManifestReference.model_validate(
            {"name": "jaffle_finance", "type": "file", "config": {"path": path}}
        )

    def test_load_plain_json(self, tmp_path: Path):
        manifest = {"nodes": {}, "metadata": {"dbt_version": "1.8.0"}}
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
        ref = self._make_file_ref(str(manifest_file))
        loader = ManifestLoader(ref)
        result = loader.load()
        assert result["metadata"]["dbt_version"] == "1.8.0"

    def test_load_gzipped_json(self, tmp_path: Path):
        manifest = {"nodes": {}, "metadata": {"dbt_version": "1.8.0"}}
        manifest_file = tmp_path / "manifest.json.gz"
        manifest_file.write_bytes(gzip.compress(json.dumps(manifest).encode()))
        ref = self._make_file_ref(str(manifest_file))
        loader = ManifestLoader(ref)
        result = loader.load()
        assert result["metadata"]["dbt_version"] == "1.8.0"

    def test_unsupported_source_type_raises(self):
        ref = ManifestReference.model_validate(
            {"name": "proj", "type": "s3", "config": None}
        )
        loader = ManifestLoader(ref)
        with pytest.raises(NotImplementedError, match="s3"):
            loader.load()
