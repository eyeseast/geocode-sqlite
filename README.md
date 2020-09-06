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

Now, geocode it using OpenStreetMap's Nominatum geocoder.

```sh
geocode-sqlite nominatum data.db data \
 --location="{address}, {city}, {state} {zip}" \
 --user-agent="this-is-me"
```

In the command above, you're using Nominatum, which is free and only asks for a unique user agent.

This will connect to a database (`data.db`) and read all rows from the table `data` (skipping any that already
have both a `latitude` and `longitude` column filled).

You're also telling the geocoder how to extract a location query from a row of data, using Python's
built-in string formatting.

For each row where geocoding succeeds, `latitude` and `longitude` will be populated. If you hit an error, or a rate limit,
run the same query and pick up where you left off.

## Development

To contribute to this tool, first checkout the code. Then create a new virtual environment:

    cd geocode-sqlite
    python -m venv venv
    source venv/bin/activate

Or if you are using `pipenv`:

    pipenv shell

Now install the dependencies and tests:

    pip install -e '.[test]'

To run the tests:

    pytest

```

```
