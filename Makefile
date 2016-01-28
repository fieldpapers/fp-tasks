NAME = fieldpapers/tasks
VERSION ?= latest

default:
	docker run -it --rm \
	  -p 8080:8080 \
	  -v $$(pwd):/app \
	  --env-file .env \
	  $(NAME):$(VERSION)

image:
	docker build --rm -t $(NAME):$(VERSION) .

publish-image:
	docker push $(NAME):$(VERSION)
