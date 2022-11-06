# geocode-sqlite

[![PyPI](https://img.shields.io/pypi/v/geocode-sqlite.svg)](https://pypi.org/project/geocode-sqlite/)
[![Changelog](https://img.shields.io/github/v/release/eyeseast/geocode-sqlite?include_prereleases&label=changelog)](https://github.com/eyeseast/geocode-sqlite/releases)
[![Tests](https://github.com/eyeseast/geocode-sqlite/workflows/Test/badge.svg)](https://github.com/eyeseast/geocode-sqlite/actions?query=workflow%3ATest)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/eyeseast/geocode-sqlite/blob/master/LICENSE)

Geocode rows from a SQLite table

## Installation

Install this tool using `pip` or `pipx`:

```sh
# install inside a virtualenv
pip install geocode-sqlite

# install globally
pipx install geocode-sqlite
```

## Usage

Let's say you have a spreadsheet with addresses in it, and you'd like to map those locations.
First, create a SQLite database and insert rows from that spreadsheet using `sqlite-utils`.

```sh
sqlite-utils insert data.db data data.csv --csv
```

Now, geocode it using OpenStreetMap's Nominatim geocoder.

```sh
geocode-sqlite nominatim data.db data \
 --location="{address}, {city}, {state} {zip}" \
 --delay=1 \
 --user-agent="this-is-me"
```

In the command above, you're using Nominatim, which is free and only asks for a unique user agent (`--user-agent`).

This will connect to a database (`data.db`) and read all rows from the table `data` (skipping any that already
have both a `latitude` and `longitude` column filled).

You're also telling the geocoder how to extract a location query (`--location`) from a row of data, using Python's
built-in string formatting, and setting a rate limit (`--delay`) of one request per second.

For each row where geocoding succeeds, `latitude` and `longitude` will be populated. If you hit an error, or a rate limit,
run the same query and pick up where you left off.

The resulting table layout can be visualized with [datasette-cluster-map](https://datasette.io/plugins/datasette-cluster-map).

Under the hood, this package uses the excellent [geopy](https://geopy.readthedocs.io/en/latest/) library, which is stable and thoroughly road-tested. If you need help understanding a particular geocoder's options, consult [geopy's documentation](https://geopy.readthedocs.io/en/latest/#module-geopy.geocoders).

### Supported Geocoders

The CLI currently supports these geocoders:

- `bing`
- `googlev3`
- `mapquest` (and `open-mapquest`)
- `mapbox`
- `nominatim`
- `opencage`

#### Adding new geocoders

1. Open an issue with the name of the geocoding service as the ticket title ([example](https://github.com/eyeseast/geocode-sqlite/issues/35)). Put any noteworthy implementation details in the ticket body, like where to get an API key if one is required.
2. Fork the repo and add a geocoder.
3. Add an example to the `Makefile`. Add tests if there's new shared functionality.

### Common arguments and options

Each geocoder needs to know where to find the data it's working with. These are the first two arguments:

- `database`: a path to a SQLite file, which must already exist
- `table`: the name of a table, in that database, which exists and has data to geocode

From there, we have a set of options passed to every geocoder:

- `location`: a [string format](https://docs.python.org/3/library/stdtypes.html#str.format) that will be expanded with each row to build a full query, to be geocoded
- `delay`: a delay between each call (some services require this)
- `latitude`: latitude column name
- `longitude`: longitude column name
- `geojson`: store results as GeoJSON, instead of in latitude and longitude columns
- `spatialite`: store results in a SpatiaLite geometry column, instead of in latitude and longitude columns
- `raw`: store raw geocoding results in a JSON column

Each geocoder takes additional, specific arguments beyond these, such as API keys. Again, [geopy's documentation](https://geopy.readthedocs.io/en/latest/#module-geopy.geocoders) is an excellent resource.

## Using SpatiaLite

The `--spatialite` flag will store results in a [geometry column](https://www.gaia-gis.it/gaia-sins/spatialite-cookbook-5/cookbook_topics.adminstration.html#topic_TABLE_to_SpatialTable), instead of `latitude` and `longitude` columns. This is useful if you're doing other GIS operations, such as using a [spatial index](https://www.gaia-gis.it/fossil/libspatialite/wiki?name=SpatialIndex). See the [SpatiaLite cookbook](https://www.gaia-gis.it/gaia-sins/spatialite-cookbook-5/index.html) and [functions list](https://www.gaia-gis.it/gaia-sins/spatialite-sql-latest.html) for more of what's possible.

## Capturing additional geocoding data

Geocoding services typically return more data than just coordinates. This might include accuracy, normalized addresses or other context. This can be captured using the `--raw` flag. By default, this will add a `raw` column and store the full geocoding response as JSON. If you want to rename that column, pass a value, like `--raw custom_raw`.

The shape of this response object will vary between services. You can query specific values using [SQLite's built-in JSON functions](https://www.sqlite.org/json1.html). For example, this will work with Google's geocoder:

```sql
select
  json_extract(raw, '$.formatted_address') as address,
  json_extract(raw, '$.geometry.location_type') as location_type
from
  innout_test
```

Check each geocoding service's documentation for what's included in the response.

## Python API

The command line interface aims to support the most common options for each geocoder. For more fine-grained control, use the Python API.

As with the CLI, this assumes you already have a SQLite database and a table of location data.

```python
from geocode_sqlite import geocode_table
from geopy.geocoders import Nominatim

# create a geocoder instance, with some extra options
nominatim = Nominatim(user_agent="this-is-me", domain="nominatim.local.dev", scheme="http")

# assuming our database is in the same directory
count = geocode_table("data.db", "data", query_template="{address}, {city}, {state} {zip}")

# when it's done
print(f"Geocoded {count} rows")
```

Any [geopy geocoder](https://geopy.readthedocs.io/en/latest/#module-geopy.geocoders) can be used with the Python API.

## Development

To contribute to this tool, first checkout the code. Then create a new virtual environment:

```sh
cd geocode-sqlite
python -m venv .venv
source .venv/bin/activate
```

Or if you are using `pipenv`:

```sh
pipenv shell
```

Now install the dependencies and tests:

```sh
pip install -e '.[test]'
```

To run the tests:

```sh
pytest
```

Please remember that this library is mainly glue code between other well-tested projects, specifically: [click](https://click.palletsprojects.com/), [geopy](https://geopy.readthedocs.io/en/stable/) and [sqlite-utils](https://sqlite-utils.datasette.io/en/stable/). Tests should focus on making sure those parts fit together correctly. We can assume the parts themselves already work.

To that end, there is a test geocoder included: `geocode_sqlite.testing.DummyGeocoder`. That geocoder works with an included dataset of In-N-Out Burger locations provided by [AllThePlaces](https://www.alltheplaces.xyz/). It works like a normal GeoPy geocoder, except it will only return results for In-N-Out locations using the included database.
