import click

from geopy import geocoders
from geopy.extra.rate_limiter import RateLimiter
from sqlite_utils import Database

from .utils import (
    geocode_list,
    select_ungeocoded,
    format_bbox,
    GEOMETRY_COLUMN,
    GEOCODER_COLUMN,
)
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
            click.option(
                "--geojson",
                type=click.BOOL,
                is_flag=True,
                default=False,
                help="""Store results as GeoJSON. 
Using this will add a geometry column instead of latitude and longitude columns.""",
            ),
            click.option(
                "--spatialite",
                is_flag=True,
                default=False,
                help="""Store results as a SpatiaLite geometry.
Using this will add a geometry column instead of latitude and longitude columns.""",
            ),
            click.pass_context,
        ]
    ):
        f = decorator(f)

    return f


def fill_context(
    ctx,
    database,
    table,
    location,
    delay,
    latitude,
    longitude,
    geojson,
    spatialite,
    **kwargs,
):
    "Add common options to context"
    ctx.obj.update(
        database=database,
        table=table,
        location=location,
        delay=delay,
        latitude=latitude,
        longitude=longitude,
        geojson=geojson,
        spatialite=spatialite,
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
        ctx.obj["geojson"],
        ctx.obj["spatialite"],
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
    if value is None or len(value) < 4:
        return None
    return format_bbox(*value)


@click.group()
@click.version_option()
@click.pass_context
def cli(ctx):
    "Geocode rows from a SQLite table"
    ctx.ensure_object(dict)


# name changed in click 8.0
result_callback = getattr(cli, "result_callback", None) or getattr(cli, "resultcallback")


@result_callback()
@click.pass_context
def geocode(ctx, geocoder):
    "Do the actual geocoding"
    (
        database,
        table,
        location,
        delay,
        latitude,
        longitude,
        geojson,
        spatialite,
        kwargs,
    ) = extract_context(ctx)

    database = Database(database)
    table = database[table]
    columns = table.columns_dict
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    click.echo(f"Geocoding table: {table.name}")

    if spatialite:
        database.init_spatialite()

    if latitude != "latitude":
        click.echo(f"Using custom latitude field: {latitude}")

    if longitude != "longitude":
        click.echo(f"Using custom longitude field: {longitude}")

    if not (geojson or spatialite) and latitude not in columns:
        click.echo(f"Adding column: {latitude}")
        table.add_column(latitude, float)

    if not (geojson or spatialite) and longitude not in columns:
        click.echo(f"Adding column: {longitude}")
        table.add_column(longitude, float)

    if geojson and GEOMETRY_COLUMN not in columns:
        click.echo("Adding geometry column")
        table.add_column(GEOMETRY_COLUMN, str)

    if spatialite and GEOMETRY_COLUMN not in columns:
        click.echo("Adding geometry column")
        table.add_geometry_column(GEOMETRY_COLUMN, "POINT")

    if GEOCODER_COLUMN not in table.columns_dict:
        click.echo("Adding geocoder column")
        table.add_column(GEOCODER_COLUMN, str)

    # always use a rate limiter, even if delay is zero
    geocode = RateLimiter(geocoder.geocode, min_delay_seconds=delay)

    rows, count = select_ungeocoded(
        database,
        table,
        latitude_column=latitude,
        longitude_column=longitude,
        geojson=(geojson or spatialite),
    )

    done = 0
    errors = []

    gen = geocode_list(
        rows,
        geocode,
        location,
        latitude_column=latitude,
        longitude_column=longitude,
        geojson=geojson,
        spatialite=spatialite,
        **kwargs,
    )

    if spatialite:
        conversions = {GEOMETRY_COLUMN: "GeomFromText(?, 4326)"}
    else:
        conversions = {}

    with click.progressbar(gen, length=count, label=f"{count} rows") as bar:
        for pk, row, success in bar:
            if success:
                table.update(pk, row, conversions=conversions)
                done += 1
            else:
                errors.append(pk)

    click.echo("Geocoded {} rows".format(done))
    if errors:
        click.echo("The following rows failed to geocode:")
        for pk in errors:
            row = table.get(pk)
            click.echo(f"{pk}: {location.format(row)}")


@cli.command("test", hidden=True)
@common_options
@click.option("-p", "--db-path", type=click.Path(exists=True))
def use_tester(
    ctx,
    database,
    table,
    location,
    delay,
    latitude,
    longitude,
    geojson,
    spatialite,
    db_path,
):
    "Only use this for testing"
    click.echo(f"Using test geocoder with database {db_path}")
    fill_context(
        ctx, database, table, location, delay, latitude, longitude, geojson, spatialite
    )
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
def bing(
    ctx,
    database,
    table,
    location,
    delay,
    latitude,
    longitude,
    geojson,
    spatialite,
    api_key,
):
    "Bing"
    click.echo("Using Bing geocoder")
    fill_context(
        ctx, database, table, location, delay, latitude, longitude, geojson, spatialite
    )
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
    ctx,
    database,
    table,
    location,
    delay,
    latitude,
    longitude,
    geojson,
    spatialite,
    api_key,
    domain,
    bbox,
):
    "Google V3"
    click.echo(f"Using GoogleV3 geocoder at domain {domain}")
    fill_context(
        ctx,
        database,
        table,
        location,
        delay,
        latitude,
        longitude,
        geojson,
        spatialite,
        bounds=bbox,
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
def mapquest(
    ctx,
    database,
    table,
    location,
    delay,
    latitude,
    longitude,
    geojson,
    spatialite,
    api_key,
    bbox,
):
    "Mapquest"
    click.echo("Using MapQuest geocoder")
    fill_context(
        ctx,
        database,
        table,
        location,
        delay,
        latitude,
        longitude,
        geojson,
        spatialite,
        bounds=bbox,
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
    ctx,
    database,
    table,
    location,
    delay,
    latitude,
    longitude,
    geojson,
    spatialite,
    user_agent,
    domain,
):
    "Nominatim (OSM)"
    click.echo(f"Using Nominatim geocoder at {domain}")
    fill_context(
        ctx, database, table, location, delay, latitude, longitude, geojson, spatialite
    )
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
def open_mapquest(
    ctx,
    database,
    table,
    location,
    delay,
    latitude,
    longitude,
    geojson,
    spatialite,
    api_key,
):
    "Open Mapquest"
    click.echo("Using MapQuest geocoder")
    fill_context(
        ctx, database, table, location, delay, latitude, longitude, geojson, spatialite
    )
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
    ctx,
    database,
    table,
    location,
    delay,
    latitude,
    longitude,
    geojson,
    spatialite,
    api_key,
    bbox,
    proximity,
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
        geojson,
        spatialite,
        bbox=bbox,
        proximity=proximity,
    )
    return geocoders.MapBox(api_key=api_key)


@cli.command("opencage")
@click.option(
    "-k",
    "--api-key",
    type=click.STRING,
    required=True,
    envvar="OPENCAGE_API_KEY",
    help="OpenCage geocoding API key",
)
@common_options
def opencage(
    ctx,
    database,
    table,
    location,
    delay,
    latitude,
    longitude,
    geojson,
    spatialite,
    api_key,
):
    "OpenCage"
    click.echo("Using OpenCage geocoder")
    fill_context(
        ctx,
        database,
        table,
        location,
        delay,
        latitude,
        longitude,
        geojson,
        spatialite,
    )
    return geocoders.OpenCage(api_key=api_key)
