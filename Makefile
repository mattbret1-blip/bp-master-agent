.PHONY: install test run web docker-up docker-down format-check lock

install:
	python -m pip install -r requirements-dev.txt

lock:
	python -m pip install -r requirements.txt && python -m pip freeze > requirements-lock.txt

test:
	python -m pytest

run:
	python main.py

web:
	uvicorn web.app:create_app --factory --host 0.0.0.0 --port 8000 --reload

docker-up:
	docker compose up --build

docker-down:
	docker compose down

format-check:
	python -m compileall agent adapters web main.py
