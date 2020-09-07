"""
Test geocoder that uses a pre-built database of In-N-Out locations to geocode a CSV of the same locations.
Location data comes from alltheplaces.xyz, scraped from In-N-Out's store locator.
"""
import json
from geopy.geocoders.base import Geocoder
from geopy.point import Point
from geopy.location import Location
from sqlite_utils import Database
from sqlite_utils.db import NotFoundError

DB_PATH = "../tests/test.db"
TABLE_NAME = "innout_geo"


class DummyGeocoder(Geocoder):
    """
    This is a fake geocoder. Don't use it for anything besides tests.
    """

    def __init__(self, db=None, table_name=TABLE_NAME, **kwargs):
        if db is None:
            db = Database(DB_PATH)
        self.db = db
        self.table = self.db[table_name]

    def geocode(self, query, *, exactly_one=True):
        "Since this is a fake geocoder, we can just look things up by ID"
        try:
            row = self.table.get(query)
        except NotFoundError:
            return None

        geometry = json.loads(row["geometry"])
        lng, lat = geometry["coordinates"]
        point = Point(lat, lng)
        return Location(row["addr:full"], point, row)

    def reverse(self, query, *, exactly_one=True):
        pass
