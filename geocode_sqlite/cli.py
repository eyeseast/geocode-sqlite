import click

from geopy import geocoders
from geopy.extra.rate_limiter import RateLimiter
from sqlite_utils import Database

from .utils import geocode_list, select_ungeocoded, format_bbox
from .testing import DummyGeocoder


def common_options(f):
    for decorator in reversed(
        [
            # arguments
            click.argument(
                "database",
                type=click.Path(
                    exists=True, file_okay=True, dir_okay=False, allow_dash=False
                ),
                required=True,
            ),
            click.argument("table", type=click.STRING, required=True),
            # options
            click.option(
                "-l",
                "--location",
                type=click.STRING,
                default="{location}",
                help="Location query format. See docs for examples.",
            ),
            click.option(
                "-d",
                "--delay",
                type=click.FLOAT,
                default=1.0,
                help="Delay between geocoding calls, in seconds.",
            ),
            click.option(
                "--latitude",
                type=click.STRING,
                default="latitude",
                help="Field name for latitude",
            ),
            click.option(
                "--longitude",
                type=click.STRING,
                default="longitude",
                help="Field name for longitude",
            ),
            click.pass_context,
        ]
    ):
        f = decorator(f)

    return f


def fill_context(ctx, database, table, location, delay, latitude, longitude, **kwargs):
    "Add common options to context"
    ctx.obj.update(
        database=database,
        table=table,
        location=location,
        delay=delay,
        latitude=latitude,
        longitude=longitude,
        kwargs=kwargs,
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
        ctx.obj.get("kwargs", {}),
    )


def bbox_option(f):
    option = click.option(
        "--bbox",
        type=click.FLOAT,
        nargs=4,
        callback=validate_bbox,
        help="Bias results within a bounding box. Must be four numbers. Example: 33.0 -119.7 34.6 -115.8",
    )
    return option(f)


def validate_bbox(ctx, param, value):
    if len(value) < 4:
        return None
    return format_bbox(*value)


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
    database, table, location, delay, latitude, longitude, kwargs = extract_context(ctx)

    database = Database(database)
    table = database[table]
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    click.echo(f"Geocoding table: {table.name}")

    if latitude != "latitude":
        click.echo(f"Using custom latitude field: {latitude}")

    if longitude != "longitude":
        click.echo(f"Using custom longitude field: {longitude}")

    if latitude not in table.columns_dict:
        click.echo(f"Adding column: {latitude}")
        table.add_column(latitude, float)

    if longitude not in table.columns_dict:
        click.echo(f"Adding column: {longitude}")
        table.add_column(longitude, float)

    if "geocoder" not in table.columns_dict:
        click.echo("Adding geocoder column")
        table.add_column("geocoder", str)

    # always use a rate limiter, even if delay is zero
    geocode = RateLimiter(geocoder.geocode, min_delay_seconds=delay)

    rows, count = select_ungeocoded(
        database,
        table,
        latitude_column=latitude,
        longitude_column=longitude,
    )

    done = 0
    errors = []

    gen = geocode_list(
        rows,
        geocode,
        location,
        latitude_column=latitude,
        longitude_column=longitude,
        **kwargs,
    )

    with click.progressbar(gen, length=count, label=f"{count} rows") as bar:
        for row, success in bar:
            pks = [row[pk] for pk in table.pks]
            if success:
                table.update(pks, row)
                done += 1
            else:
                errors.append(pks)

    click.echo("Geocoded {} rows".format(done))
    if errors:
        click.echo("The following rows failed to geocode:")
        for pk in errors:
            row = table.get(pk)
            click.echo(f"{pk}: {location.format(row)}")


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
    "-k",
    "--api-key",
    type=click.STRING,
    required=True,
    envvar="BING_API_KEY",
    help="Bing Maps API key",
)
def bing(ctx, database, table, location, delay, latitude, longitude, api_key):
    "Bing"
    click.echo("Using Bing geocoder")
    fill_context(ctx, database, table, location, delay, latitude, longitude)
    return geocoders.Bing(api_key=api_key)


@cli.command("googlev3")
@click.option(
    "-k",
    "--api-key",
    type=click.STRING,
    required=True,
    envvar="GOOGLE_API_KEY",
    help="Google Maps API key",
)
@click.option(
    "--domain", type=click.STRING, default="maps.googleapis.com", show_default=True
)
@bbox_option
@common_options
def google(
    ctx, database, table, location, delay, latitude, longitude, api_key, domain, bbox
):
    "Google V3"
    click.echo(f"Using GoogleV3 geocoder at domain {domain}")
    fill_context(
        ctx, database, table, location, delay, latitude, longitude, bounds=bbox
    )
    return geocoders.GoogleV3(api_key=api_key, domain=domain)


@cli.command("mapquest")
@click.option(
    "-k",
    "--api-key",
    type=click.STRING,
    required=True,
    envvar="MAPQUEST_API_KEY",
    help="MapQuest API key",
)
@bbox_option
@common_options
def mapquest(ctx, database, table, location, delay, latitude, longitude, api_key, bbox):
    "Mapquest"
    click.echo("Using MapQuest geocoder")
    fill_context(
        ctx, database, table, location, delay, latitude, longitude, bounds=bbox
    )
    return geocoders.MapQuest(api_key=api_key)


@cli.command()
@click.option(
    "--user-agent",
    type=click.STRING,
    help="Unique user-agent string to identify requests",
)
@click.option(
    "--domain",
    type=click.STRING,
    default="nominatim.openstreetmap.org",
    show_default=True,
)
@common_options
def nominatim(
    ctx, database, table, location, delay, latitude, longitude, user_agent, domain
):
    "Nominatim (OSM)"
    click.echo(f"Using Nominatim geocoder at {domain}")
    fill_context(ctx, database, table, location, delay, latitude, longitude)
    return geocoders.Nominatim(user_agent=user_agent, domain=domain)


@cli.command("open-mapquest")
@click.option(
    "-k",
    "--api-key",
    type=click.STRING,
    required=True,
    envvar="MAPQUEST_API_KEY",
    help="MapQuest API key",
)
@common_options
def open_mapquest(ctx, database, table, location, delay, latitude, longitude, api_key):
    "Open Mapquest"
    click.echo("Using MapQuest geocoder")
    fill_context(ctx, database, table, location, delay, latitude, longitude)
    return geocoders.MapQuest(api_key=api_key)


@cli.command("mapbox")
@click.option(
    "-k",
    "--api-key",
    type=click.STRING,
    required=True,
    envvar="MAPBOX_API_KEY",
    help="MapBox access token",
)
@bbox_option
@click.option(
    "--proximity",
    type=click.FLOAT,
    nargs=2,
    help="Favor results closer to a provided location. Example: 33.8 -117.8",
)
@common_options
def mapbox(
    ctx, database, table, location, delay, latitude, longitude, api_key, bbox, proximity
):
    "Mapbox"
    click.echo("Using Mapbox geocoder")
    fill_context(
        ctx,
        database,
        table,
        location,
        delay,
        latitude,
        longitude,
        bbox=bbox,
        proximity=proximity,
    )
    return geocoders.MapBox(api_key=api_key)
