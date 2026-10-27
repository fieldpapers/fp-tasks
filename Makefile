CONTAINER ?= podman
IMAGE ?= fp-tasks

image:
	$(CONTAINER) build -t $(IMAGE) .

run: image
	$(CONTAINER) run --rm -it -p 8080:8080 $(if $(wildcard .env),--env-file .env) $(IMAGE)

# Runs the working copy's code (mounted over the image's), so the image only
# needs rebuilding when the Dockerfile changes. Pass pytest options with
# PYTEST_ARGS, e.g. PYTEST_ARGS="-k round_trip --update-expected".
test:
	$(CONTAINER) build --target test -t $(IMAGE)-test .
	$(CONTAINER) run --rm \
	  -v $$(pwd)/decoder:/app/decoder:Z \
	  -v $$(pwd)/service:/app/service:Z \
	  -v $$(pwd)/tests:/app/tests:Z \
	  $(IMAGE)-test python3 -m pytest $(PYTEST_ARGS)

.PHONY: image run test
