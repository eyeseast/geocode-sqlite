import click

from geopy import geocoders
from sqlite_utils import Database

from .utils import geocode_table
from .testing import DummyGeocoder


def common_options(f):
    f = click.pass_context(f)

    # arguments have to be added in reverse order
    f = click.argument("table", type=click.STRING, required=True)(f)
    f = click.argument(
        "database",
        type=click.Path(exists=True, file_okay=True, dir_okay=False, allow_dash=False),
        required=True,
    )(f)

    # options
    f = click.option("-l", "--location", type=click.STRING, default="{location}")(f)
    f = click.option("-d", "--delay", type=click.FLOAT, default=1.0)(f)
    f = click.option("--latitude", type=click.STRING, default="latitude")(f)
    f = click.option("--longitude", type=click.STRING, default="longitude")(f)

    return f


def fill_context(ctx, database, table, location, delay, latitude, longitude):
    "Add common options to context"
    ctx.obj.update(
        database=database,
        table=table,
        location=location,
        delay=delay,
        latitude=latitude,
        longitude=longitude,
    )


def extract_context(ctx):
    "The opposite of fill_context. Return all common args in order."
    return (
        ctx.obj["database"],
        ctx.obj["table"],
        ctx.obj["location"],
        ctx.obj["delay"],
        ctx.obj["latitude"],
        ctx.obj["longitude"],
    )


@click.group()
@click.version_option()
@click.pass_context
def cli(ctx):
    "Geocode rows from a SQLite table"
    ctx.ensure_object(dict)


@cli.resultcallback()
@click.pass_context
def geocode(ctx, geocoder):
    "Do the actual geocoding"
    database, table, location, delay, latitude, longitude = extract_context(ctx)
    click.echo(f"Geocoding table: {table}")

    if latitude != "latitude":
        click.echo(f"Using custom latitude field: {latitude}")

    if longitude != "longitude":
        click.echo(f"Using custom longitude field: {longitude}")

    count = geocode_table(
        database,
        table,
        geocoder,
        query_template=location,
        delay=delay,
        latitude_column=latitude,
        longitude_column=longitude,
    )
    click.echo("Geocoded {} rows".format(count))


@cli.command("test", hidden=True)
@common_options
@click.option("-p", "--db-path", type=click.Path(exists=True))
def use_tester(ctx, database, table, location, delay, latitude, longitude, db_path):
    "Only use this for testing"
    click.echo(f"Using test geocoder with database {db_path}")
    fill_context(ctx, database, table, location, delay, latitude, longitude)
    return DummyGeocoder(Database(db_path))


@cli.command("bing")
@common_options
@click.option(
    "-k", "--api-key", type=click.STRING, required=True, envvar="BING_API_KEY"
)
def bing(ctx, database, table, location, delay, latitude, longitude, api_key):
    "Bing"
    click.echo("Using Bing geocoder")
    fill_context(ctx, database, table, location, delay, latitude, longitude)
    return geocoders.Bing(api_key=api_key)


@cli.command("googlev3")
@common_options
@click.option(
    "-k", "--api-key", type=click.STRING, required=True, envvar="GOOGLE_API_KEY"
)
@click.option("--domain", type=click.STRING, default="maps.googleapis.com")
def google(ctx, database, table, location, delay, latitude, longitude, api_key, domain):
    "Google V3"
    click.echo(f"Using GoogleV3 geocoder at domain {domain}")
    fill_context(ctx, database, table, location, delay, latitude, longitude)
    return geocoders.GoogleV3(api_key=api_key, domain=domain)


@cli.command("mapquest")
@common_options
@click.option(
    "-k", "--api-key", type=click.STRING, required=True, envvar="MAPQUEST_API_KEY"
)
def mapquest(ctx, database, table, location, delay, latitude, longitude, api_key):
    "Mapquest"
    click.echo("Using MapQuest geocoder")
    fill_context(ctx, database, table, location, delay, latitude, longitude)
    return geocoders.MapQuest(api_key=api_key)


@cli.command()
@common_options
@click.option("--user-agent", type=click.STRING)
@click.option("--domain", type=click.STRING, default="nominatim.openstreetmap.org")
def nominatum(
    ctx, database, table, location, delay, latitude, longitude, user_agent, domain
):
    "Nominatum (OSM)"
    click.echo(f"Using Nominatum geocoder at {domain}")
    fill_context(ctx, database, table, location, delay, latitude, longitude)
    return geocoders.Nominatim(user_agent=user_agent, domain=domain)


@cli.command("open-mapquest")
@common_options
@click.option(
    "-k", "--api-key", type=click.STRING, required=True, envvar="MAPQUEST_API_KEY"
)
def open_mapquest(ctx, database, table, location, delay, latitude, longitude, api_key):
    "Open Mapquest"
    click.echo("Using MapQuest geocoder")
    fill_context(ctx, database, table, location, delay, latitude, longitude)
    return geocoders.MapQuest(api_key=api_key)
