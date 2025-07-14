ONESHELL:

IMAGE_NAME 	:= eco-ci-cd
IMAGE_TAG 	?= $(shell git rev-parse --short HEAD)
GIT_TAG 	?= $(shell git describe --tags --abbrev=0 HEAD 2>/dev/null || echo "latest")
IMAGE_REGISTRY 	?= 
PODMAN_PARAMS 	?= --platform=linux/amd64

image-build:
	podman build \
		$(PODMAN_PARAMS) \
		--tag $(IMAGE_REGISTRY)$(IMAGE_NAME):$(IMAGE_TAG) \
		--tag $(IMAGE_REGISTRY)$(IMAGE_NAME):$(GIT_TAG) \
		-f Containerfile \
		.

image-push:
	podman push \
		$(IMAGE_REGISTRY)$(IMAGE_NAME):$(IMAGE_TAG) \
		$(IMAGE_REGISTRY)$(IMAGE_NAME):$(GIT_TAG)