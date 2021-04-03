# make a test database, and run tests

tests/%.db: tests/innout.geojson tests/innout.csv
	geojson-to-sqlite $@ innout_geo tests/innout.geojson
	sqlite-utils insert $@ innout_test tests/innout.csv --csv --pk id

.PHONY: test
test: tests/test.db
	geocode-sqlite test tests/test.db innout_test -p tests/test.db -l "{id}" -d 0

.PHONY: nominatum
nominatum: tests/nominatum.db
	geocode-sqlite nominatum $^ innout_test \
		--location "{full}, {city}, {state} {postcode}" \
		--delay 1 \
		--user-agent "geocode-sqlite"

.PHONY: mapquest
mapquest: tests/mapquest.db
	geocode-sqlite open-mapquest $^ innout_test \
		--location "{full}, {city}, {state} {postcode}" \
		--api-key "$(MAPQUEST_API_KEY)"

.PHONY: google
google: tests/google.db
	geocode-sqlite googlev3 $^ innout_test \
		--location "{full}, {city}, {state} {postcode}" \
		--api-key "$(GOOGLE_API_KEY)"

.PHONY: bing
bing: tests/bing.db
	geocode-sqlite bing $^ innout_test \
		--location "{full}, {city}, {state} {postcode}" \
		--delay 1 \
		--api-key "$(BING_API_KEY)"


.PHONY: clean
clean:
	rm tests/test.db
