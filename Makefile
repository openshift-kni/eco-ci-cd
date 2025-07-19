ONESHELL:

IMAGE_NAME			?= eco-ci-cd
IMAGE_TAG			?= $(shell git rev-parse --short HEAD)
GIT_TAG				?= $(shell git describe --tags --abbrev=0 HEAD 2>/dev/null || echo "latest")
IMAGE_REGISTRY 		?= quay.io/telcov10n-ci
PODMAN_BUILD_PARAMS ?= --platform=linux/amd64

image-build:

	GIT_URL=$$(git config --get remote.origin.url)
	GIT_COMMIT=$$(git rev-parse HEAD)
	GIT_BRANCH=$$(git rev-parse --abbrev-ref HEAD)
	APP_VERSION=$${GIT_TAG}
	echo "Dynamically got git information:"
	echo "GIT_URL: $(GIT_URL)"
	echo "GIT_COMMIT: $(GIT_COMMIT)"
	echo "GIT_BRANCH: $(GIT_BRANCH)"
	echo "GIT_TAG: $(GIT_TAG)"
	podman build \
		$(PODMAN_BUILD_PARAMS) \
		--label org.opencontainers.image.source=$${GIT_URL} \
		--label org.opencontainers.image.source.commit=$${GIT_COMMIT} \
		--label org.opencontainers.image.source.branch=$${GIT_BRANCH} \
		--label org.opencontainers.image.source.tag=$${GIT_TAG} \
		--tag $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG) \
		-f Containerfile \
		.
	echo "Image built: $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)"
	podman tag $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG) $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(GIT_TAG)
	echo "Image tagged: $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(GIT_TAG)"
	if [[ "${GIT_TAG}" != "latest" ]]; then
		podman tag $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG) $(IMAGE_REGISTRY)/$(IMAGE_NAME):latest
		echo "Image tagged: $(IMAGE_REGISTRY)/$(IMAGE_NAME):latest"
	fi

image-push:
	podman push $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)
	echo "Image pushed: $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)"
	podman push $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(GIT_TAG)
	echo "Image pushed: $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(GIT_TAG)"
	if [[ "${GIT_TAG}" != "latest" ]]; then
		podman push $(IMAGE_REGISTRY)/$(IMAGE_NAME):latest
		echo "Image pushed: $(IMAGE_REGISTRY)/$(IMAGE_NAME):latest"
	fi
