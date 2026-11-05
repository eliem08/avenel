.PHONY: lint test typecheck openapi-lint rls-check audit-verify migrate migrate-down \
        web-install web-gen-api web-typecheck web-test web-build css-check guards e2e e2e-up e2e-down ci

# Python from the project venv when present (see the reproduce section of the phase report).
ifeq ($(OS),Windows_NT)
VENV_PY := .venv/Scripts/python.exe
else
VENV_PY := .venv/bin/python
endif
PYTHON ?= $(if $(wildcard $(VENV_PY)),$(VENV_PY),python)
COMPOSE ?= docker compose

# ---------------------------------------------------------------- backend (unchanged)
lint:
	$(PYTHON) -m ruff check avenel apps scripts
	$(PYTHON) scripts/check_no_tax_literals.py
	$(PYTHON) scripts/check_migration_hashes.py
	$(PYTHON) scripts/check_test_count.py
	$(PYTHON) scripts/generate_expert_sign_off.py --check

test:
	$(PYTHON) -m pytest -v tests

typecheck:
	$(PYTHON) -m mypy avenel apps/api scripts

openapi-lint:
	npx @stoplight/spectral-cli lint contracts/openapi.yaml --ruleset .spectral.yaml

rls-check:
	$(PYTHON) scripts/rls_check.py

audit-verify:
	$(PYTHON) scripts/verify_audit_chain.py --seed

migrate:
	$(PYTHON) avenel/infrastructure/migrations.py up

migrate-down:
	$(PYTHON) avenel/infrastructure/migrations.py down

# ---------------------------------------------------------------- web console
web-install:
	npm ci --no-audit --no-fund

# Fails if contracts/openapi.yaml and the generated client disagree.
web-gen-api:
	npx openapi-typescript contracts/openapi.yaml -o src/api/schema.d.ts
	git diff --exit-code -- src/api/schema.d.ts

web-typecheck:
	npx tsc -b --noEmit

web-build:
	npm run build

web-test: web-build
	npx vitest run --reporter=default --reporter=json --outputFile=.vitest-results.json
	node scripts/guards/check_web_test_count.mjs

css-check: web-build
	node scripts/guards/check_css_palette.mjs

# Part K 25–27 (25 and 27 also scan the built bundle).
guards: web-build
	node scripts/guards/no_test_code_in_prod.mjs
	node scripts/guards/no_e2e_interception.mjs
	node scripts/guards/no_legacy_terms.mjs

# ---------------------------------------------------------------- e2e (Part K 28)
e2e-up:
	$(COMPOSE) up -d --build postgres keycloak clamav freshclam ocr migrate seed api worker web
	node scripts/guards/wait_for_stack.mjs

e2e-down:
	$(COMPOSE) logs --no-color --timestamps api > docs/reports/phase-5c-1/e2e-api-container.log 2>&1 || true
	$(COMPOSE) down -v

e2e: e2e-up
	npx playwright install chromium
	rm -rf docs/reports/phase-5c-1/e2e-browser-api-requests.log .e2e-state
	npx playwright test --grep-invert @api-down
	$(COMPOSE) stop api
	npx playwright test --grep @api-down
	$(COMPOSE) start api
	$(MAKE) e2e-down

ci: lint typecheck openapi-lint rls-check audit-verify test web-gen-api web-typecheck web-test css-check guards e2e
