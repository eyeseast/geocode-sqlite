from setuptools import setup
import os

VERSION = "0.2.0"

requirements = ["click", "sqlite_utils", "geopy"]


def get_long_description():
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md"),
        encoding="utf8",
    ) as fp:
        return fp.read()


setup(
    name="geocode-sqlite",
    description="Geocode rows from a SQLite table",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Chris Amico",
    url="https://github.com/eyeseast/geocode-sqlite",
    project_urls={
        "Issues": "https://github.com/eyeseast/geocode-sqlite/issues",
        "CI": "https://github.com/eyeseast/geocode-sqlite/actions",
        "Changelog": "https://github.com/eyeseast/geocode-sqlite/releases",
    },
    license="Apache License, Version 2.0",
    version=VERSION,
    packages=["geocode_sqlite"],
    entry_points="""
        [console_scripts]
        geocode-sqlite=geocode_sqlite.cli:cli
    """,
    install_requires=requirements,
    extras_require={"test": ["pytest", "geojson-to-sqlite"]},
    tests_require=["geocode-sqlite[test]"],
)
