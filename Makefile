# make a test database, and run tests

tests/%.db: tests/innout.geojson tests/innout.csv
	geojson-to-sqlite $@ innout_geo tests/innout.geojson
	sqlite-utils insert $@ innout_test tests/innout.csv --csv --pk id

.PHONY: test
test: tests/test.db
	# geocode-sqlite -l "{id}" -d 0 $^ innout_test test -p $^
	geocode-sqlite test tests/test.db innout_test -p tests/test.db -l "{id}" -d 0

.PHONY: nominatum
nominatum: tests/nominatum.db
	geocode-sqlite -l "{full}, {city}, {state} {postcode}" \
	 --delay 1 \
	 $^ \
	 innout_test \
	 nominatum \
	 --user-agent "geocode-sqlite"

.PHONY: mapquest
mapquest: tests/mapquest.db
	geocode-sqlite -l "{full}, {city}, {state} {postcode}" \
	$^ innout_test \
	open-mapquest \
	--api-key "$(MAPQUEST_API_KEY)"

.PHONY: google
google: tests/google.db
	geocode-sqlite -l "{full}, {city}, {state} {postcode}" \
	$^ innout_test \
	googlev3 \
	--api-key "$(GOOGLE_API_KEY)"


.PHONY: bing
bing: tests/bing.db
	geocode-sqlite -l "{full}, {city}, {state} {postcode}" -d 1 \
	$^ innout_test \
	bing \
	--api-key "$(BING_API_KEY)"


.PHONY: clean
clean:
	rm tests/test.db
