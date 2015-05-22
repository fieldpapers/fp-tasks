VERSION ?= latest

default:
	docker run --rm \
	  -p 8080:8080 \
	  -v $$(pwd):/app \
	  --env-file .env \
	  fieldpapers/tasks

image:
	docker build -t fieldpapers/tasks:$(VERSION) .
