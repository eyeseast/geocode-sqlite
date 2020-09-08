# make a test database, and run tests

tests/test.db: tests/innout.geojson tests/innout.csv
	geojson-to-sqlite $@ innout_geo tests/innout.geojson
	sqlite-utils insert $@ innout_test tests/innout.csv --csv --pk id

.PHONY: test
test: tests/test.db
	geocode-sqlite -l "{id}" $^ innout_test test -p $^

.PHONY: nominatum
nominatum: tests/test.db
	geocode-sqlite -l "{full}, {city}, {state} {postcode}" \
	 --delay 1 \
	 tests/test.db \
	 innout_test \
	 nominatum \
	 --user-agent "geocode-sqlite"

.PHONY: clean
clean:
	rm tests/test.db
