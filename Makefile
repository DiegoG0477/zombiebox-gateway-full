
.PHONY: format format-check
format:
	python3 scripts/format.py
format-check:
	python3 scripts/format.py --check

ZOMBIE_CORE_DIR ?= $(shell python3 scripts/dependencies.py path gateway-core)
ZOMBIE_RUNTIME_ROOT ?= $(CURDIR)
ZOMBIE_FULL_DIR := $(CURDIR)
export ZOMBIE_CORE_DIR ZOMBIE_RUNTIME_ROOT ZOMBIE_FULL_DIR
COMPOSE = docker compose --env-file $(ZOMBIE_RUNTIME_ROOT)/.local/gateway/compose.env -f compose.yaml
.PHONY: deps deps-check setup sources check build up down
deps:
	python3 scripts/dependencies.py fetch gateway-core
deps-check:
	python3 scripts/dependencies.py check gateway-core
setup:
	bash scripts/setup-runtime.sh
	python3 scripts/setup-youtube.py
	python3 scripts/setup-services.py
	python3 $(ZOMBIE_CORE_DIR)/scripts/generate-probes.py --output $(ZOMBIE_RUNTIME_ROOT)/.local/gateway/probes
sources: setup
	python3 scripts/setup-services.py --sources
check: setup
	$(COMPOSE) --profile youtube --profile youtube-receiver --profile spotify --profile airplay --profile threadfin --profile rebrowser config --quiet
build: setup
	$(COMPOSE) build gateway
up: deps
	$(MAKE) setup
	$(COMPOSE) build gateway
	$(COMPOSE) up -d
down:
	$(COMPOSE) down

.PHONY: tracks-smoke
tracks-smoke:
	python3 scripts/smoke-tracks.py

.PHONY: remote-smoke
remote-smoke:
	bash scripts/smoke-remote.sh
