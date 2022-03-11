"""
This is the Python interface
"""
import logging
from geopy.extra.rate_limiter import RateLimiter
from sqlite_utils import Database

log = logging.getLogger("geocode_sqlite")

GEOMETRY_COLUMN = "geometry"
GEOCODER_COLUMN = "geocoder"


def geocode_table(
    db,
    table_name,
    geocoder,
    query_template="{location}",
    *,
    delay=0,
    latitude_column="latitude",
    longitude_column="longitude",
    geojson=False,
    spatialite=False,
    force=False,
    **kwargs,
):
    """
    Geocode rows in a given table.

    You **must** specify a geocoder instance to use.

    By default, select all rows where `latitude` or `longitude` is null.
    Those fields can be configured (for example, to use `lat` and `long`).
    Pass `force=True` to ignore existing data.

    Since location data is often split across multiple rows, you can build
    a single query using a template string passed as `query_template`. By default,
    this looks for a column called `location`.
    """
    if not isinstance(db, Database):
        db = Database(db)

    table = db[table_name]
    columns = table.columns_dict

    if spatialite:
        db.init_spatialite()

    if not (geojson or spatialite) and latitude_column not in columns:
        log.info(f"Adding latitude column: {latitude_column}")
        table.add_column(latitude_column, float)

    if not (geojson or spatialite) and longitude_column not in columns:
        log.info(f"Adding longitude column: {longitude_column}")
        table.add_column(longitude_column, float)

    if geojson and GEOMETRY_COLUMN not in columns:
        log.info("Adding geometry column")
        table.add_column(GEOMETRY_COLUMN, str)

    if spatialite and GEOMETRY_COLUMN not in columns:
        log.info("Adding geometry column")
        table.add_geometry_column(GEOMETRY_COLUMN, "POINT")

    if GEOCODER_COLUMN not in columns:
        log.info("Adding geocoder column")
        table.add_column(GEOCODER_COLUMN, str)

    rows, todo = select_ungeocoded(
        db,
        table,
        latitude_column=latitude_column,
        longitude_column=longitude_column,
        geojson=(geojson or spatialite),
        force=force,
    )

    # always use a rate limiter, even with no delay
    geocode = RateLimiter(geocoder.geocode, min_delay_seconds=delay)

    count = 0
    log.info(f"Geocoding {todo} rows from {table.name}")
    for pk, row in rows:
        result = geocode_row(geocode, query_template, row, **kwargs)
        if result:
            update = {
                GEOCODER_COLUMN: geocoder.__class__.__name__,
            }

            conversions = {}

            if geojson:
                update[GEOMETRY_COLUMN] = {
                    "type": "Point",
                    "coordinates": [result.longitude, result.latitude],
                }

            elif spatialite:
                update[
                    GEOMETRY_COLUMN
                ] = f"POINT ({result.longitude} {result.latitude})"
                conversions[GEOMETRY_COLUMN] = "GeomFromText(?, 4326)"

            else:
                update[latitude_column] = result.latitude
                update[longitude_column] = result.longitude

            table.update(pk, update, conversions=conversions)
            count += 1

        else:
            log.info("Failed to geocode row: %s", row)

    return count


def geocode_list(
    rows,
    geocode,
    query_template="{location}",
    *,
    latitude_column="latitude",
    longitude_column="longitude",
    geojson=False,
    spatialite=False,
    **kwargs,
):
    """
    Geocode an arbitrary list of rows, returning a generator.
    This does not query or save geocoded results into a table.
    If geocoding succeeds, it will yield a three-tuple:
     - the primary key of the row (rowid or actual PK)
     - the row with latitude and longitude columns set
     - and True

    If geocoding fails, it will yield the original row and False.
    """
    for pk, row in rows:
        result = geocode_row(geocode, query_template, row, **kwargs)
        if result:
            row = update_row(
                row, result, latitude_column, longitude_column, geojson, spatialite
            )
            row[GEOCODER_COLUMN] = get_geocoder_class(geocode)

        yield pk, row, bool(result)


def geocode_row(geocode, query_template, row, **kwargs):
    """
    Do the actual work of geocoding
    """
    query = query_template.format(**row)
    return geocode(query, **kwargs)


def update_row(
    row,
    result,
    latitude_column="latitude",
    longitude_column="longitude",
    geojson=False,
    spatialite=False,
):
    """
    Update a row before saving, either setting latitude and longitude,
    or creating a geojson object for a geometry column.
    """
    if geojson:
        row[GEOMETRY_COLUMN] = {
            "type": "Point",
            "coordinates": [result.longitude, result.latitude],
        }

    elif spatialite:
        row[GEOMETRY_COLUMN] = f"POINT ({result.longitude} {result.latitude})"

    else:
        row[longitude_column] = result.longitude
        row[latitude_column] = result.latitude

    return row


def select_ungeocoded(
    db,
    table,
    *,
    latitude_column="latitude",
    longitude_column="longitude",
    geojson=False,
    force=False,
):
    if force:
        return table.rows, table.count

    if geojson:
        count = db.execute(
            f"SELECT count(*) FROM {table.name} WHERE {GEOMETRY_COLUMN} IS NULL"
        ).fetchone()
        rows = table.pks_and_rows_where(f"{GEOMETRY_COLUMN} IS NULL")

    else:
        count = db.execute(
            f"""SELECT count(*) 
            FROM {table.name} 
            WHERE {latitude_column} IS NULL 
            OR {longitude_column} IS NULL"""
        ).fetchone()

        rows = table.pks_and_rows_where(
            f"{latitude_column} IS NULL OR {longitude_column} IS NULL"
        )

    if count:
        count = count[0]

    return rows, count


def get_geocoder_class(geocode):
    "Walk back up to the original geocoder class"

    if isinstance(geocode, RateLimiter):
        return geocode.func.__self__.__class__.__name__

    # unwrapped function
    return geocode.__self__.__class__.__name__


def format_bbox(*coords):
    coords = coords[:4]  # get exactly four
    return (coords[0], coords[1]), (coords[2], coords[3])
