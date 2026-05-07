build:
	docker compose build

shell:
	docker compose run --rm app bash

doctor:
	docker compose run --rm app dii doctor

seed:
	docker compose run --rm app python scripts/generate_sample_delta_tables.py

history:
	docker compose run --rm app dii history data/delta/customers

test:
	docker compose run --rm app pytest

lint:
	docker compose run --rm app ruff check .

format:
	docker compose run --rm app ruff format .

clean:
	docker compose down -v
	rm -rf data/delta data/tmp .pytest_cache .ruff_cache

diff-by-key:
	docker compose run --rm app dii diff-by-key data/delta/customers --from-version 2 --to-version 4 --key customer_id
