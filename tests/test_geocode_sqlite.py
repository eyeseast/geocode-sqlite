import csv
import datetime
import inspect
import json
import pathlib
import pytest

from click.testing import CliRunner
from geojson_to_sqlite.utils import import_features
from geopy.location import Location
from sqlite_utils import Database

from geocode_sqlite.cli import cli, use_tester
from geocode_sqlite.testing import DummyGeocoder
from geocode_sqlite.utils import geocode_row, geocode_table, geocode_list

tests = pathlib.Path(__file__).parent
DB_PATH = tests / "test.db"
TABLE_NAME = "innout_test"
GEO_TABLE = "innout_geo"

GEOJSON_DATA = tests / "innout.geojson"
CSV_DATA = tests / "innout.csv"


@pytest.fixture
def db():
    db = Database(DB_PATH)
    table = db[TABLE_NAME]

    # load csv data, which will be geocoded
    table.insert_all(csv.DictReader(open(CSV_DATA)), alter=True, pk="id")

    # load our geojson data, for our fake geocoder
    fc = json.load(open(GEOJSON_DATA))
    import_features(DB_PATH, GEO_TABLE, fc["features"], alter=True)

    # yield, instead of return, so we can cleanup
    yield db

    # start fresh every test
    print("Deleting test database")
    DB_PATH.unlink()


@pytest.fixture
def geocoder(db):
    return DummyGeocoder(db)


def test_version():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["--version"])
        assert 0 == result.exit_code
        assert result.output.startswith("cli, version ")


def test_cli_geocode_table(db, geocoder):
    runner = CliRunner()
    table = db[TABLE_NAME]
    geo_table = db[GEO_TABLE]

    # run the cli with our test geocoder
    result = runner.invoke(
        cli,
        [
            "test",  # geocoder subcommand
            str(DB_PATH),  # db
            str(TABLE_NAME),  # table
            "--db-path",  # path, for test geocoder
            str(DB_PATH),
            "--location",  # location
            "{id}",
            "--delay",  # delay
            "0",
        ],
    )

    print(result.stdout)
    assert 0 == result.exit_code

    for row in table.rows:
        assert type(row.get("latitude")) == float
        assert type(row.get("longitude")) == float

        expected = geo_table.get(row["id"])
        geometry = json.loads(expected["geometry"])
        lng, lat = geometry["coordinates"]

        assert (lng, lat) == (row["longitude"], row["latitude"])


def test_custom_fieldnames(db, geocoder):
    runner = CliRunner()
    table = db[TABLE_NAME]
    geo_table = db[GEO_TABLE]

    result = runner.invoke(
        cli,
        [
            "test",
            str(DB_PATH),
            str(TABLE_NAME),
            "-p",
            str(DB_PATH),
            "-l",
            "{id}",
            "-d",
            "0",
            "--latitude",
            "lat",
            "--longitude",
            "lng",
        ],
    )

    print(result.stdout)
    assert 0 == result.exit_code

    for row in table.rows:
        assert type(row.get("lat")) == float
        assert type(row.get("lng")) == float

        result = geo_table.get(row["id"])


def test_rate_limiting(db, geocoder):
    table = db[TABLE_NAME]
    runner = CliRunner()

    # geocode once
    geocode_table(db, TABLE_NAME, geocoder, "{id}")

    # un-geocode Utah, which has 10 locations
    utah = list(table.rows_where('"state" = "UT"'))
    assert len(utah) == 10
    for row in utah:
        table.update(row["id"], {"latitude": None, "longitude": None})

    # re-geocode those 10 rows, with a --delay argument
    # and time it
    start = datetime.datetime.now()
    result = runner.invoke(
        cli,
        [
            "test",
            str(DB_PATH),
            str(TABLE_NAME),
            "-p",
            str(DB_PATH),
            "--location",
            "{id}",
            "--delay",
            "1",
        ],
    )
    end = datetime.datetime.now()
    diff = end - start

    print(result.stdout)
    assert 0 == result.exit_code
    assert diff.total_seconds() >= len(utah) - 1  # delay is after, so one less


def test_pass_kwargs(db, geocoder):

    # geocode it once
    geocode_table(db, TABLE_NAME, geocoder, "{id}")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "mapbox",
            str(DB_PATH),
            TABLE_NAME,  # already geocoded, so no calls
            "--location",
            "{id}",
            "--bbox",
            "-71.553765",
            "42.163302",
            "-70.564995",
            "42.533755",
            "--proximity",
            "-71.0",
            "42.3",
        ],
    )
    assert 0 == result.exit_code


def test_geocode_row(db, geocoder):
    table = db[TABLE_NAME]
    geo_table = db[GEO_TABLE]

    row = next(table.rows)

    assert row.get("latitude") is None
    assert row.get("longitude") is None

    # since it's a fake geocoder, we can just look things up by id
    # all we're testing here is the interface that glues everything together
    result = geo_table.get(row["id"])
    location = geocode_row(geocoder.geocode, "{id}", row)

    assert isinstance(location, Location)
    assert location.address == result["addr:full"]
    assert result == location.raw


def test_geocode_table(db, geocoder):
    table = db[TABLE_NAME]
    geo_table = db[GEO_TABLE]

    assert "latitude" not in table.columns_dict
    assert "longitude" not in table.columns_dict

    count = geocode_table(db, TABLE_NAME, geocoder, "{id}")

    # did we get the whole table?
    assert count == table.count

    for row in table.rows:
        assert type(row.get("latitude")) == float
        assert type(row.get("longitude")) == float

        result = geo_table.get(row["id"])


def test_resume_table(db, geocoder):
    table = db[TABLE_NAME]

    # geocode it once
    geocode_table(db, TABLE_NAME, geocoder, "{id}")

    # undo it for some results, to pretend we're resuming
    texas = list(table.rows_where('"state" = "TX"'))
    for row in texas:
        table.update(row["id"], {"latitude": None, "longitude": None})

    count = geocode_table(db, TABLE_NAME, geocoder, "{id}")

    assert count == len(texas)


def test_geocode_list(db, geocoder):
    table = db[TABLE_NAME]

    utah = list(table.rows_where('"state" = "UT"'))
    assert len(utah) == 10

    gen = geocode_list(utah, geocoder.geocode, "{id}")

    assert inspect.isgenerator(gen)

    done = list(gen)

    # geocode the whole table, to cheeck results
    geocode_table(db, TABLE_NAME, geocoder, "{id}")

    for row, success in done:
        assert success
        assert row == table.get(row["id"])


def test_label_results(db, geocoder):
    table = db[TABLE_NAME]

    # geocode it once
    geocode_table(db, TABLE_NAME, geocoder, "{id}")

    for row in table.rows:
        assert "geocoder" in row
        assert row["geocoder"] == geocoder.__class__.__name__


def test_geojson_format(db, geocoder):
    runner = CliRunner()
    table = db[TABLE_NAME]
    geo_table = db[GEO_TABLE]

    # run the cli with our test geocoder
    result = runner.invoke(
        cli,
        [
            "test",  # geocoder subcommand
            str(DB_PATH),  # db
            str(TABLE_NAME),  # table
            "--db-path",  # path, for test geocoder
            str(DB_PATH),
            "--location",  # location
            "{id}",
            "--delay",  # delay
            "0",
            "--geojson",
        ],
    )

    print(result.stdout)
    assert 0 == result.exit_code

    for row in table.rows:
        assert type(row.get("geometry")) == str

        expected = json.loads(geo_table.get(row["id"])["geometry"])
        geometry = json.loads(row["geometry"])

        assert expected == geometry
