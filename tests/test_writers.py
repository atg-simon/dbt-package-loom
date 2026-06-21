from dbt_package_loom.writers import write_package


class TestWritePackage:
    def test_writes_dbt_project_yml(self, tmp_path, dim_customer):
        write_package("jaffle_finance", [dim_customer], output_dir=str(tmp_path))
        project_yml = tmp_path / "jaffle_finance" / "dbt_project.yml"
        assert project_yml.exists()
        content = project_yml.read_text()
        assert "name: jaffle_finance" in content
        assert "+materialized: ephemeral" in content

    def test_writes_unversioned_model_files(self, tmp_path, dim_customer):
        write_package("jaffle_finance", [dim_customer], output_dir=str(tmp_path))
        models_dir = tmp_path / "jaffle_finance" / "models" / "conformed"
        assert (models_dir / "dim_customer.sql").exists()
        assert (models_dir / "sources.yml").exists()
        assert (models_dir / "schema.yml").exists()

    def test_writes_versioned_model_files(
        self, tmp_path, fct_booking_v1, fct_booking_v2
    ):
        write_package(
            "jaffle_finance",
            [fct_booking_v1, fct_booking_v2],
            output_dir=str(tmp_path),
        )
        models_dir = tmp_path / "jaffle_finance" / "models" / "integrated"
        assert (models_dir / "fct_booking_v1.sql").exists()
        assert (models_dir / "fct_booking_v2.sql").exists()
        assert (models_dir / "fct_booking.sql").exists()  # unversioned alias

    def test_versioned_alias_stub_content(
        self, tmp_path, fct_booking_v1, fct_booking_v2
    ):
        write_package(
            "jaffle_finance",
            [fct_booking_v1, fct_booking_v2],
            output_dir=str(tmp_path),
        )
        alias_sql = (
            tmp_path / "jaffle_finance" / "models" / "integrated" / "fct_booking.sql"
        )
        content = alias_sql.read_text()
        assert "source('jaffle_finance', 'fct_booking_v2')" in content
        assert "Alias for latest version (v2)" in content

    def test_overwrites_existing_package(self, tmp_path, dim_customer):
        pkg_dir = tmp_path / "jaffle_finance"
        pkg_dir.mkdir()
        (pkg_dir / "stale_file.txt").write_text("old")
        write_package("jaffle_finance", [dim_customer], output_dir=str(tmp_path))
        assert not (pkg_dir / "stale_file.txt").exists()

    def test_full_package_structure(
        self, tmp_path, dim_customer, fct_booking_v1, fct_booking_v2
    ):
        write_package(
            "jaffle_finance",
            [dim_customer, fct_booking_v1, fct_booking_v2],
            output_dir=str(tmp_path),
        )
        root = tmp_path / "jaffle_finance"
        assert (root / "dbt_project.yml").exists()
        assert (root / "models" / "conformed" / "dim_customer.sql").exists()
        assert (root / "models" / "conformed" / "sources.yml").exists()
        assert (root / "models" / "conformed" / "schema.yml").exists()
        assert (root / "models" / "integrated" / "fct_booking_v1.sql").exists()
        assert (root / "models" / "integrated" / "fct_booking_v2.sql").exists()
        assert (root / "models" / "integrated" / "fct_booking.sql").exists()
        assert (root / "models" / "integrated" / "sources.yml").exists()
        assert (root / "models" / "integrated" / "schema.yml").exists()

    def test_sql_stubs_reference_correct_source(self, tmp_path, dim_customer):
        write_package("jaffle_finance", [dim_customer], output_dir=str(tmp_path))
        sql = (
            tmp_path / "jaffle_finance" / "models" / "conformed" / "dim_customer.sql"
        ).read_text()
        assert "source('jaffle_finance', 'dim_customer')" in sql

    def test_sources_yml_content(self, tmp_path, dim_customer):
        write_package("jaffle_finance", [dim_customer], output_dir=str(tmp_path))
        yml = (
            tmp_path / "jaffle_finance" / "models" / "conformed" / "sources.yml"
        ).read_text()
        assert "name: jaffle_finance" in yml
        assert "database: jaffle_finance_prod" in yml
        assert "schema: conformed" in yml
        assert "name: dim_customer" in yml
