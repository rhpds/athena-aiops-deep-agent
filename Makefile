IMAGE_REGISTRY ?= quay.io
IMAGE_NAMESPACE ?= tonykay
IMAGE_NAME ?= athena-aiops
IMAGE_TAG ?= latest
IMAGE := $(IMAGE_REGISTRY)/$(IMAGE_NAMESPACE)/$(IMAGE_NAME):$(IMAGE_TAG)

PLATFORMS := linux/amd64,linux/arm64

.PHONY: build push run test lint clean

## Build multi-arch image and push to registry
push:
	docker buildx build \
		--platform $(PLATFORMS) \
		--tag $(IMAGE) \
		--push .

## Build for local architecture only (no push)
build:
	docker build --tag $(IMAGE) .

## Run locally (requires env vars)
run:
	uv run python -m athena

## Run test suite
test:
	uv run pytest -v

## Lint and format check
lint:
	uv run ruff check . && uv run ruff format --check .

## Auto-fix lint and formatting
fix:
	uv run ruff check --fix . && uv run ruff format .

## Deploy to OpenShift via Helm (set values via environment or --set)
deploy:
	helm upgrade --install athena deploy/helm/athena/ \
		--set aap2.url=$(AAP2_URL) \
		--set aap2.username=$(AAP2_USERNAME) \
		--set aap2.password=$(AAP2_PASSWORD) \
		--set aap2.organization=$(AAP2_ORGANIZATION) \
		--set kira.url=$(KIRA_URL) \
		--set kira.apiKey=$(KIRA_API_KEY) \
		--set rocketchat.url=$(ROCKETCHAT_URL) \
		--set rocketchat.apiAuthToken=$(ROCKETCHAT_API_AUTH_TOKEN) \
		--set rocketchat.apiUserId=$(ROCKETCHAT_API_USER_ID) \
		--set maas.apiBaseUrl=$(LITELLM_API_BASE_URL) \
		--set maas.virtualKey=$(LITELLM_VIRTUAL_KEY) \
		--set image.repository=$(IMAGE_REGISTRY)/$(IMAGE_NAMESPACE)/$(IMAGE_NAME) \
		--set image.tag=$(IMAGE_TAG)

## Remove Helm release
undeploy:
	helm uninstall athena

clean:
	rm -rf .venv dist *.egg-info .pytest_cache .ruff_cache __pycache__
