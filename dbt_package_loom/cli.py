import logging
import sys

import click
import yaml

from dbt_package_loom.config import dbtLoomConfig
from dbt_package_loom.manifests import ManifestLoader
from dbt_package_loom.writers import write_package

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.option(
    "--config",
    "config_path",
    default="dbt_loom.config.yml",
    show_default=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to dbt-loom config file.",
)
def inject(config_path: str) -> None:
    """Inject ephemeral stub packages for each upstream project in the dbt-loom config."""
    with open(config_path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    loom_config = dbtLoomConfig.model_validate(raw)

    errors: list[str] = []
    for ref in loom_config.manifests:
        click.echo(f"  → {ref.name} ({ref.type.value})")
        try:
            loader = ManifestLoader(ref)
            manifest = loader.load()
            nodes = loader.get_public_models(manifest)
            click.echo(f"    {len(nodes)} public model(s) found")
            write_package(ref.name, nodes)
            click.echo(f"    Written to dbt_packages/{ref.name}/")
        except Exception as exc:  # noqa: BLE001
            if ref.optional:
                click.echo(f"    WARNING: {exc} (optional — skipping)", err=True)
            else:
                click.echo(f"    ERROR: {exc}", err=True)
                errors.append(ref.name)

    if errors:
        click.echo(f"\nFailed for: {', '.join(errors)}", err=True)
        sys.exit(1)
