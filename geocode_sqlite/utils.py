"""
This is the Python interface
"""
import logging
from geopy import geocoders
from geopy.extra.rate_limiter import RateLimiter
from sqlite_utils import Database

log = logging.getLogger("geocode_sqlite")


def geocode_table(
    db,
    table_name,
    geocoder,
    query_template="{location}",
    *,
    delay=0,
    latitude_column="latitude",
    longitude_column="longitude",
    force=False,
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

    if latitude_column not in table.columns_dict:
        table.add_column(latitude_column, float)

    if longitude_column not in table.columns_dict:
        table.add_column(longitude_column, float)

    if force:
        rows = table.rows
    else:
        rows = table.rows_where(
            f"{latitude_column} IS NULL OR {longitude_column} IS NULL"
        )

    if delay:
        geocode = RateLimiter(geocoder.geocode, min_delay_seconds=delay)
    else:
        geocode = geocoder.geocode

    count = 0
    for row in rows:
        result = geocode_row(geocode, query_template, row)
        if result:
            pks = [row[pk] for pk in table.pks]
            table.update(
                pks,
                {latitude_column: result.latitude, longitude_column: result.longitude},
            )
            count += 1

        else:
            log.info("Failed to geocode row: %s", row)

    return count


def geocode_row(geocode, query_template, row):
    """
    Do the actual work of geocoding
    """
    query = query_template.format(**row)
    return geocode(query)
