from dbt_package_loom.generator import (
    VersionedGroup,
    build_alias_stub_sql,
    build_dbt_project_yml,
    build_schema_yml,
    build_sources_yml,
    build_stub_sql,
    group_nodes_by_folder,
)
from dbt_package_loom.manifests import ManifestNode


class TestGroupNodesByFolder:
    def test_single_unversioned_model(self, dim_customer):
        folders = group_nodes_by_folder([dim_customer])
        assert "conformed" in folders
        assert folders["conformed"].unversioned == [dim_customer]
        assert folders["conformed"].versioned_groups == {}

    def test_versioned_models_grouped(self, fct_booking_v1, fct_booking_v2):
        folders = group_nodes_by_folder([fct_booking_v1, fct_booking_v2])
        assert "integrated" in folders
        fc = folders["integrated"]
        assert fc.unversioned == []
        assert "fct_booking" in fc.versioned_groups
        vg = fc.versioned_groups["fct_booking"]
        assert len(vg.versions) == 2

    def test_versioned_versions_sorted_ascending(self, fct_booking_v2, fct_booking_v1):
        folders = group_nodes_by_folder([fct_booking_v2, fct_booking_v1])
        vg = folders["integrated"].versioned_groups["fct_booking"]
        assert vg.versions[0].version == 1
        assert vg.versions[1].version == 2

    def test_multiple_folders(self, dim_customer, fct_booking_v1, fct_booking_v2):
        folders = group_nodes_by_folder([dim_customer, fct_booking_v1, fct_booking_v2])
        assert set(folders.keys()) == {"conformed", "integrated"}

    def test_root_folder(self):
        node = ManifestNode.model_validate(
            {
                "name": "my_model",
                "package_name": "proj",
                "unique_id": "model.proj.my_model",
                "resource_type": "model",
                "schema": "main",
                "path": "my_model.sql",
                "access": "public",
            }
        )
        folders = group_nodes_by_folder([node])
        assert "" in folders


class TestVersionedGroupLatest:
    def test_latest_uses_latest_version_field(self, fct_booking_v1, fct_booking_v2):
        vg = VersionedGroup(
            base_name="fct_booking", versions=[fct_booking_v1, fct_booking_v2]
        )
        assert vg.latest.version == 2

    def test_latest_falls_back_to_max_version(self):
        v1 = ManifestNode.model_validate(
            {
                "name": "m",
                "package_name": "p",
                "unique_id": "model.p.m.v1",
                "resource_type": "model",
                "schema": "s",
                "alias": "m_v1",
                "version": 1,
            }
        )
        v3 = ManifestNode.model_validate(
            {
                "name": "m",
                "package_name": "p",
                "unique_id": "model.p.m.v3",
                "resource_type": "model",
                "schema": "s",
                "alias": "m_v3",
                "version": 3,
            }
        )
        vg = VersionedGroup(base_name="m", versions=[v1, v3])
        assert vg.latest.version == 3


class TestBuildDbtProjectYml:
    def test_contains_project_name(self):
        yml = build_dbt_project_yml("jaffle_finance")
        assert "name: jaffle_finance" in yml

    def test_materialized_ephemeral(self):
        yml = build_dbt_project_yml("jaffle_finance")
        assert "+materialized: ephemeral" in yml

    def test_has_package_mesh_stub_tag(self):
        yml = build_dbt_project_yml("jaffle_finance")
        assert "package-mesh-stub" in yml

    def test_config_version_2(self):
        yml = build_dbt_project_yml("jaffle_finance")
        assert "config-version: 2" in yml

    def test_schema_namespaced_to_project(self):
        yml = build_dbt_project_yml("atg_source")
        assert "+schema: atg_source" in yml


class TestBuildSourcesYml:
    def test_output_is_valid_yaml(self, dim_customer):
        from dbt_package_loom.generator import FolderContent
        import yaml as _yaml

        fc = FolderContent(folder="conformed", unversioned=[dim_customer])
        parsed = _yaml.safe_load(build_sources_yml("proj", fc))
        assert parsed["sources"][0]["tables"][0]["name"] == "dim_customer"

    def test_descriptions_not_copied(self):
        from dbt_package_loom.generator import FolderContent

        node = ManifestNode.model_validate({
            "name": "dim_customer",
            "package_name": "proj",
            "unique_id": "model.proj.dim_customer",
            "resource_type": "model",
            "schema": "conformed",
            "path": "conformed/dim_customer.sql",
            "access": "public",
            "description": "Some upstream description",
        })
        fc = FolderContent(folder="conformed", unversioned=[node])
        assert "description" not in build_sources_yml("proj", fc)
        assert "description" not in build_schema_yml(fc)

    def test_unversioned_source_table(self, dim_customer):
        from dbt_package_loom.generator import FolderContent

        fc = FolderContent(folder="conformed", unversioned=[dim_customer])
        yml = build_sources_yml("jaffle_finance", fc)
        assert "name: jaffle_finance" in yml
        assert "name: dim_customer" in yml
        assert "identifier: dim_customer" in yml
        assert "schema: conformed" in yml
        assert "database: jaffle_finance_prod" in yml

    def test_unversioned_source_uses_model_name_with_custom_alias(self):
        from dbt_package_loom.generator import FolderContent

        node = ManifestNode.model_validate({
            "name": "dim_customer",
            "package_name": "proj",
            "unique_id": "model.proj.dim_customer",
            "resource_type": "model",
            "schema": "conformed",
            "alias": "customer_dim",
            "path": "conformed/dim_customer.sql",
        })
        fc = FolderContent(folder="conformed", unversioned=[node])
        yml = build_sources_yml("proj", fc)
        assert "name: dim_customer" in yml
        assert "identifier: customer_dim" in yml

    def test_versioned_source_tables(self, fct_booking_v1, fct_booking_v2):
        from dbt_package_loom.generator import FolderContent, VersionedGroup

        vg = VersionedGroup(
            base_name="fct_booking", versions=[fct_booking_v1, fct_booking_v2]
        )
        fc = FolderContent(folder="integrated", versioned_groups={"fct_booking": vg})
        yml = build_sources_yml("jaffle_finance", fc)
        assert "name: fct_booking_v1" in yml
        assert "name: fct_booking_v2" in yml
        assert "fct_booking\n" not in yml  # base name not added as a source table

    def test_no_database_line_when_absent(self):
        from dbt_package_loom.generator import FolderContent

        node = ManifestNode.model_validate(
            {
                "name": "m",
                "package_name": "p",
                "unique_id": "model.p.m",
                "resource_type": "model",
                "schema": "s",
                "path": "s/m.sql",
            }
        )
        fc = FolderContent(folder="s", unversioned=[node])
        yml = build_sources_yml("p", fc)
        assert "database:" not in yml


class TestBuildSchemaYml:
    def test_unversioned_model_entry(self, dim_customer):
        from dbt_package_loom.generator import FolderContent

        fc = FolderContent(folder="conformed", unversioned=[dim_customer])
        yml = build_schema_yml(fc)
        assert "name: dim_customer" in yml
        assert "versions:" not in yml
        assert "latest_version:" not in yml

    def test_versioned_model_entry(self, fct_booking_v1, fct_booking_v2):
        from dbt_package_loom.generator import FolderContent, VersionedGroup

        vg = VersionedGroup(
            base_name="fct_booking", versions=[fct_booking_v1, fct_booking_v2]
        )
        fc = FolderContent(folder="integrated", versioned_groups={"fct_booking": vg})
        yml = build_schema_yml(fc)
        assert "name: fct_booking\n" in yml
        assert "latest_version: 2" in yml
        assert "versions:" in yml
        assert "v: 1" in yml
        assert "v: 2" in yml
        # defined_in uses path stem, not alias
        assert "defined_in: fct_booking_v1" in yml
        assert "defined_in: fct_booking_v2" in yml

    def test_defined_in_uses_path_stem_not_alias(self):
        """Two models with same alias but different path stems must not clash."""
        from dbt_package_loom.generator import FolderContent, VersionedGroup

        node_av = ManifestNode.model_validate({
            "name": "ent_order_item", "package_name": "atg_source",
            "unique_id": "model.atg_source.ent_order_item.v3",
            "resource_type": "model", "schema": "s", "version": 3,
            "alias": "ent_order_item_v3",
            "path": "entity/av_uk/dynamic_tables/ent_order_item_v3.sql",
        })
        node_das = ManifestNode.model_validate({
            "name": "ent_das__order_item", "package_name": "atg_source",
            "unique_id": "model.atg_source.ent_das__order_item.v3",
            "resource_type": "model", "schema": "s", "version": 3,
            "alias": "ent_order_item_v3",
            "path": "entity/das/dynamic_tables/ent_das__order_item_v3.sql",
        })
        assert node_av.file_stem == "ent_order_item_v3"
        assert node_das.file_stem == "ent_das__order_item_v3"

        vg_av = VersionedGroup(base_name="ent_order_item", versions=[node_av])
        vg_das = VersionedGroup(base_name="ent_das__order_item", versions=[node_das])
        yml_av = build_schema_yml(FolderContent(folder="entity/av_uk/dynamic_tables", versioned_groups={"ent_order_item": vg_av}))
        yml_das = build_schema_yml(FolderContent(folder="entity/das/dynamic_tables", versioned_groups={"ent_das__order_item": vg_das}))
        assert "defined_in: ent_order_item_v3" in yml_av
        assert "defined_in: ent_das__order_item_v3" in yml_das


class TestBuildStubSql:
    def test_unversioned_stub_uses_model_name(self, dim_customer):
        sql = build_stub_sql("jaffle_finance", dim_customer)
        assert "source('jaffle_finance', 'dim_customer')" in sql
        assert "Generated by dbt-package-loom" in sql

    def test_unversioned_stub_uses_model_name_not_alias(self):
        node = ManifestNode.model_validate({
            "name": "dim_customer",
            "package_name": "proj",
            "unique_id": "model.proj.dim_customer",
            "resource_type": "model",
            "schema": "conformed",
            "alias": "customer_dim",
        })
        sql = build_stub_sql("proj", node)
        assert "source('proj', 'dim_customer')" in sql
        assert "customer_dim" not in sql

    def test_versioned_stub_uses_alias(self, fct_booking_v1):
        sql = build_stub_sql("jaffle_finance", fct_booking_v1)
        assert "source('jaffle_finance', 'fct_booking_v1')" in sql

    def test_alias_stub_points_to_latest(self, fct_booking_v1, fct_booking_v2):
        from dbt_package_loom.generator import VersionedGroup

        vg = VersionedGroup(
            base_name="fct_booking", versions=[fct_booking_v1, fct_booking_v2]
        )
        sql = build_alias_stub_sql("jaffle_finance", vg)
        assert "source('jaffle_finance', 'fct_booking_v2')" in sql
        assert "Alias for latest version (v2)" in sql
