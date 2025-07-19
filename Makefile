.ONESHELL:

SCRIPT_DEBUG		?= 0
GIT_REMOTE_NAME		?= origin
GIT_URL				?= $(shell ./scripts/git_remote_normalize.sh $(GIT_REMOTE_NAME))
GIT_COMMIT			?= $(shell git rev-parse HEAD)
GIT_BRANCH			?= $(shell git rev-parse --abbrev-ref HEAD)
GIT_TAG				?= $(shell git tag --points-at=HEAD 2>/dev/null)
IMAGE_NAME			?= $(notdir $(GIT_URL))
IMAGE_REGISTRY 		?= quay.io/telcov10n-ci
PODMAN_PARAMS 		?= 
PODMAN_BUILD_PARAMS ?= --platform=linux/amd64
PODMAN_TAG_PARAMS 	?=
PODMAN_PUSH_PARAMS 	?=

ifeq ($(SCRIPT_DEBUG),1)
	PODMAN_PARAMS += --log-level debug
endif

image-build:
	@GIT_TAG=$${GIT_TAG:-latest}
	@podman \
		$(PODMAN_PARAMS) \
		build \
			$(PODMAN_BUILD_PARAMS) \
			--label "org.opencontainers.image.version=$${GIT_TAG}" \
			--label "org.opencontainers.image.source=$(GIT_URL)" \
			--label "org.opencontainers.image.source.commit=$(GIT_COMMIT)" \
			--label "org.opencontainers.image.source.branch=$(GIT_BRANCH)" \
			--label "org.opencontainers.image.source.tag=$${GIT_TAG}" \
			--tag $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(GIT_COMMIT) \
			-f Containerfile \
			.
	@echo "Image built: $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(GIT_COMMIT)"
	@echo -n "Tagging: $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(GIT_COMMIT) as $(IMAGE_REGISTRY)/$(IMAGE_NAME):$${GIT_TAG} ..."
	@podman \
		$(PODMAN_PARAMS) \
		tag \
			$(PODMAN_TAG_PARAMS) \
			$(IMAGE_REGISTRY)/$(IMAGE_NAME):$(GIT_COMMIT) \
			$(IMAGE_REGISTRY)/$(IMAGE_NAME):$${GIT_TAG}
	@echo "done"

image-push:
	@echo -n "Pushing: $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(GIT_COMMIT) ..."
	@podman \
		$(PODMAN_PARAMS) \
		push \
			$(PODMAN_PUSH_PARAMS) \
			$(IMAGE_REGISTRY)/$(IMAGE_NAME):$(GIT_COMMIT)
	@echo " done"
	@echo -n "Pushing: $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(GIT_TAG) ..."
	@podman push \
	@podman \
		$(PODMAN_PARAMS) \
		push \
			$(PODMAN_PUSH_PARAMS) \
			$(IMAGE_REGISTRY)/$(IMAGE_NAME):$(GIT_TAG)
	@echo " done"



cnf-reporting-%:
	# The recipe for the rule.
	# It runs the sub-make in a subshell to avoid changing the current directory.
	@echo "--- Forwarding target '$(*)' to playbooks/cnf/reporting ---"
	@(cd playbooks/cnf/reporting && $(MAKE) $(*) )

# reporting-:
# reporting-reset-collections-reqs:
# reporting-clean-caches:	$(CLEANUP_LIST)
# reporting-bootstrap:
# reporting-gendata:
# reporting-render:
# reporting-run-playbook:
# reporting-pylint: $(GENERATOR)
# reporting-ansible-lint: $(PLAYBOOK)
# reporting-shellcheck: $(WRAPPER)
# reporting-lint:	pylint	ansible-lint shellcheck
# reporting-pytest:
# reporting-test-verify:
# reporting-test:
# reporting-retest:
	