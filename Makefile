.PHONY: help install test run catalog export docker-up docker-down k8s-apply metrics-smoke

help:
	@echo "Targets: install test run catalog export docker-up docker-down k8s-apply metrics-smoke"

install:
	python -m pip install -r requirements-dev.txt

test:
	pytest -q

run:
	FLASK_DEBUG=1 python app.py

catalog:
	python -m pip install -r scripts/requirements.txt
	python scripts/build_trailers.py
	python scripts/build_catalog.py
	python scripts/export_site.py --out docs

export:
	python scripts/export_site.py --out docs

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

k8s-apply:
	kubectl apply -f deploy/k8s/deployment.yaml

metrics-smoke:
	curl -fsS http://127.0.0.1:8080/healthz && curl -fsS http://127.0.0.1:8080/readyz && curl -fsS http://127.0.0.1:8080/metrics | head
