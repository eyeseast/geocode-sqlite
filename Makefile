# make a test database, and run tests

tests/%.db: tests/innout.geojson tests/innout.csv
	geojson-to-sqlite $@ innout_geo tests/innout.geojson
	sqlite-utils insert $@ innout_test tests/innout.csv --csv --pk id

.PHONY: test
test: tests/test.db
	geocode-sqlite test tests/test.db innout_test -p tests/test.db -l "{id}" -d .1 --spatialite

.PHONY: nominatim
nominatim: tests/nominatim.db
	geocode-sqlite nominatim $^ innout_test \
		--location "{full}, {city}, {state} {postcode}" \
		--delay 1 \
		--raw \
		--user-agent "geocode-sqlite"

.PHONY: mapquest
mapquest: tests/mapquest.db
	geocode-sqlite open-mapquest $^ innout_test \
		--location "{full}, {city}, {state} {postcode}" \
		--raw \
		--api-key "$(MAPQUEST_API_KEY)"

.PHONY: google
google: tests/google.db
	geocode-sqlite googlev3 $^ innout_test \
		--location "{full}, {city}, {state} {postcode}" \
		--raw \
		--api-key "$(GOOGLE_API_KEY)" \
		--bbox 33.030551 -119.787326 34.695341 -115.832248

.PHONY: bing
bing: tests/bing.db
	geocode-sqlite bing $^ innout_test \
		--location "{full}, {city}, {state} {postcode}" \
		--delay 1 \
		--raw \
		--api-key "$(BING_API_KEY)"

.PHONY: mapbox
mapbox: tests/mapbox.db
	geocode-sqlite mapbox $^ innout_test \
		--location "{full}, {city}, {state} {postcode}" \
		--delay 1 \
		--raw \
		--api-key "$(MAPBOX_API_KEY)"

.PHONY: opencage
opencage: tests/opencage.db
	geocode-sqlite opencage $^ innout_test \
		--location "{full}, {city}, {state} {postcode}" \
		--delay '0.1' \
		--raw \
		--api-key "$(OPENCAGE_API_KEY)"

.PHONY: run
run:
	datasette serve tests/*.db --load-extension spatialite

.PHONY: clean
clean:
	rm -f tests/test.db
