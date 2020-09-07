import click

from geopy import geocoders
from sqlite_utils import Database

from .utils import geocode_table


@click.group()
@click.version_option()
@click.argument(
    "database",
    type=click.Path(exists=False, file_okay=True, dir_okay=False, allow_dash=False),
    required=True,
)
@click.argument("table", type=click.STRING)
@click.option("-l", "--location", type=click.STRING, default="{location}")
@click.pass_context
def cli(ctx, database, table, location):
    "Geocode rows from a SQLite table"
    ctx.ensure_object(dict)

    ctx.obj["database"] = database
    ctx.obj["table"] = table
    ctx.obj["location"] = location


@cli.resultcallback()
def geocode(geocoder, database, table, location):
    "Do the actual geocoding"
    click.echo(f"Geocoding table {table}")
    count = geocode_table(database, table, geocoder, location)
    click.echo("Geocoded {} rows".format(count))


@cli.command("test")
@click.option("-p", "--db-path", type=click.Path(exists=True))
@click.pass_context
def use_tester(ctx, db_path):
    "Use the dummy geocoder for testing"
    click.echo(f"Using test geocoder with database {db_path}")
    from .testing import DummyGeocoder

    return DummyGeocoder(Database(db_path))

