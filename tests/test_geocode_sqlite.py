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
from sqlite_utils.utils import find_spatialite

from geocode_sqlite.cli import cli, use_tester
from geocode_sqlite.testing import DummyGeocoder
from geocode_sqlite.utils import geocode_row, geocode_table, geocode_list

tests = pathlib.Path(__file__).parent
# DB_PATH = tests / "test.db"
TABLE_NAME = "innout_test"
GEO_TABLE = "innout_geo"

GEOJSON_DATA = tests / "innout.geojson"
CSV_DATA = tests / "innout.csv"


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def db(request, db_path):
    db = Database(db_path)
    table = db[TABLE_NAME]

    pk = getattr(request, "param", "id")

    # load csv data, which will be geocoded
    table.insert_all(csv.DictReader(open(CSV_DATA)), alter=True, pk=pk)

    # load our geojson data, for our fake geocoder
    fc = json.load(open(GEOJSON_DATA))
    import_features(db_path, GEO_TABLE, fc["features"], alter=True)

    # yield, instead of return, so we can cleanup
    yield db

    # start fresh every test
    print("Deleting test database")
    db_path.unlink()


@pytest.fixture
def geocoder(db):
    return DummyGeocoder(db)


def test_version():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["--version"])
        assert 0 == result.exit_code
        assert result.output.startswith("cli, version ")


@pytest.mark.parametrize("db", ["id", None], indirect=True)
def test_cli_geocode_table(db, db_path, geocoder):
    runner = CliRunner()
    table = db[TABLE_NAME]
    geo_table = db[GEO_TABLE]

    # run the cli with our test geocoder
    result = runner.invoke(
        cli,
        [
            "test",  # geocoder subcommand
            str(db_path),  # db
            str(TABLE_NAME),  # table
            "--db-path",  # path, for test geocoder
            str(db_path),
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


def test_custom_fieldnames(db, db_path, geocoder):
    runner = CliRunner()
    table = db[TABLE_NAME]
    geo_table = db[GEO_TABLE]

    result = runner.invoke(
        cli,
        [
            "test",
            str(db_path),
            str(TABLE_NAME),
            "-p",
            str(db_path),
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


def test_rate_limiting(db, db_path, geocoder):
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
            str(db_path),
            str(TABLE_NAME),
            "-p",
            str(db_path),
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


def test_pass_kwargs(db, db_path, geocoder):

    # geocode it once
    geocode_table(db, TABLE_NAME, geocoder, "{id}")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "mapbox",
            str(db_path),
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


def test_geocode_row(db, db_path, geocoder):
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

    utah = list(table.pks_and_rows_where('"state" = "UT"'))
    assert len(utah) == 10

    gen = geocode_list(utah, geocoder.geocode, "{id}")

    assert inspect.isgenerator(gen)

    done = list(gen)

    # geocode the whole table, to cheeck results
    geocode_table(db, TABLE_NAME, geocoder, "{id}")

    for pk, row, success in done:
        assert success
        assert row == table.get(pk)


def test_label_results(db, geocoder):
    table = db[TABLE_NAME]

    # geocode it once
    geocode_table(db, TABLE_NAME, geocoder, "{id}")

    for row in table.rows:
        assert "geocoder" in row
        assert row["geocoder"] == geocoder.__class__.__name__


def test_geojson_format(db, db_path, geocoder):
    runner = CliRunner()
    table = db[TABLE_NAME]
    geo_table = db[GEO_TABLE]

    # run the cli with our test geocoder
    result = runner.invoke(
        cli,
        [
            "test",  # geocoder subcommand
            str(db_path),  # db
            str(TABLE_NAME),  # table
            "--db-path",  # path, for test geocoder
            str(db_path),
            "--location",  # location
            "{id}",
            "--delay",  # delay
            "0",
            "--geojson",
        ],
    )

    print(result.stdout)
    assert 0 == result.exit_code

    for pk, row in table.pks_and_rows_where():
        assert "latitude" not in row
        assert "longitude" not in row

        assert type(row.get("geometry")) == str

        expected = geo_table.get(pk)
        geometry = json.loads(row["geometry"])

        assert json.loads(expected["geometry"]) == geometry


@pytest.mark.skipif(find_spatialite() is None, reason="SpatiaLite extension not found")
def test_spatialite(db, db_path, geocoder):
    db.init_spatialite()

    table = db[TABLE_NAME]
    geo_table = db[GEO_TABLE]

    # run the cli with our test geocoder
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "test",  # geocoder subcommand
            str(db_path),  # db
            str(TABLE_NAME),  # table
            "--db-path",  # path, for test geocoder
            str(db_path),
            "--location",  # location
            "{id}",
            "--delay",  # delay
            "0",
            "--spatialite",  # implies geojson
        ],
    )

    print(result.stdout)
    assert 0 == result.exit_code

    for pk, row in table.pks_and_rows_where():
        assert "latitude" not in row
        assert "longitude" not in row

        assert type(row.get("geometry")) == bytes

        expected = json.loads(geo_table.get(pk)["geometry"])
        geometry = json.loads(
            db.execute("select AsGeoJSON(?)", [row["geometry"]]).fetchone()[0]
        )

        assert geometry["type"] == expected["type"]
        assert expected["coordinates"] == pytest.approx(geometry["coordinates"])


@pytest.mark.skipif(find_spatialite() is None, reason="SpatiaLite extension not found")
def test_spatialite_geocode_table(db, geocoder):
    db.init_spatialite()

    table = db[TABLE_NAME]
    geo_table = db[GEO_TABLE]

    geocode_table(db, TABLE_NAME, geocoder, "{id}", spatialite=True)

    for pk, row in table.pks_and_rows_where():
        assert "latitude" not in row
        assert "longitude" not in row

        assert type(row.get("geometry")) == bytes

        expected = json.loads(geo_table.get(pk)["geometry"])
        geometry = json.loads(
            db.execute("select AsGeoJSON(?)", [row["geometry"]]).fetchone()[0]
        )

        assert geometry["type"] == expected["type"]
        assert expected["coordinates"] == pytest.approx(geometry["coordinates"])
