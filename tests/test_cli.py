from pathlib import Path

from click.testing import CliRunner

from dbt_package_loom.cli import cli


class TestInjectCommand:
    def test_inject_creates_package(self, tmp_path, loom_config_file):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                cli,
                ["inject", "--config", str(loom_config_file)],
                catch_exceptions=False,
            )
        assert result.exit_code == 0, result.output

    def test_inject_shows_project_name(self, tmp_path, loom_config_file):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                cli,
                ["inject", "--config", str(loom_config_file)],
                catch_exceptions=False,
            )
        assert "jaffle_finance" in result.output

    def test_inject_missing_config_exits_nonzero(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["inject", "--config", str(tmp_path / "does_not_exist.yml")],
        )
        assert result.exit_code != 0

    def test_inject_default_config_name(self, tmp_path):
        """--config defaults to dbt_loom.config.yml"""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["inject"])
        assert result.exit_code != 0  # no default file present — expected failure

    def test_inject_writes_dbt_package(self, tmp_path, loom_config_file):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                cli,
                ["inject", "--config", str(loom_config_file)],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            pkg = Path("dbt_packages") / "jaffle_finance"
            assert (pkg / "dbt_project.yml").exists()

    def test_inject_reports_model_count(self, tmp_path, loom_config_file):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                cli,
                ["inject", "--config", str(loom_config_file)],
                catch_exceptions=False,
            )
        # 3 nodes in the fixture manifest (dim_customer + v1 + v2)
        assert "3 public model(s)" in result.output
