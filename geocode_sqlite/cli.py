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
@click.option("--latitude", type=click.STRING, default="latitude")
@click.option("--longitude", type=click.STRING, default="longitude")
def cli(database, table, location, latitude, longitude):
    "Geocode rows from a SQLite table"


@cli.resultcallback()
def geocode(geocoder, database, table, location, latitude, longitude):
    "Do the actual geocoding"
    click.echo(f"Geocoding table {table} using {geocoder.__class__.__name__}")
    if latitude != "latitude":
        click.echo(f"Using custom latitude field: {latitude}")

    if longitude != "longitude":
        click.echo(f"Using custom longitude field: {longitude}")

    count = geocode_table(
        database,
        table,
        geocoder,
        query_template=location,
        latitude_column=latitude,
        longitude_column=longitude,
    )
    click.echo("Geocoded {} rows".format(count))


@cli.command("test")
@click.option("-p", "--db-path", type=click.Path(exists=True))
def use_tester(db_path):
    "Use the dummy geocoder for testing"
    click.echo(f"Using test geocoder with database {db_path}")
    from .testing import DummyGeocoder

    return DummyGeocoder(Database(db_path))

