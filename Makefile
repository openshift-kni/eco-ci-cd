ONESHELL:

IMAGE_NAME			?= eco-ci-cd
IMAGE_TAG			?= $(shell git rev-parse --short HEAD)
GIT_TAG				?= $(shell git describe --tags --abbrev=0 HEAD 2>/dev/null || echo "latest")
IMAGE_REGISTRY 		?= quay.io/telcov10n-ci
PODMAN_BUILD_PARAMS ?= --platform=linux/amd64

image-build:
	podman build \
		$(PODMAN_BUILD_PARAMS) \
		--tag $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG) \
		-f Containerfile \
		.
	echo "Image built: $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)"
	podman tag $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG) $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(GIT_TAG)
	echo "Image tagged: $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(GIT_TAG)"

image-push:
	podman push $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)
	podman push $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(GIT_TAG)
