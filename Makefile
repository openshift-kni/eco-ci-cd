.ONESHELL:

SCRIPT_DEBUG		?= 0
RESET_VENV			?= 0
VENV_DIR			?= .venv
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
BUILD_ARGS_FILE		?= current-build-args.txt
PY_REQS_BASE_FILE	?= requirements-base.local.txt
PY_REQS_PREFIX		?= requirements-container

ifeq ($(SCRIPT_DEBUG),1)
	PODMAN_PARAMS += --log-level debug
endif

ifeq ($(RESET_VENV),1)
	rm -rf $(VENV_DIR)
endif



image-build-args-file:
	@GIT_TAG=$${GIT_TAG:-latest}
	@echo "Generating build arguments file: $(BUILD_ARGS_FILE)"
	{ \
		echo "GIT_URL=$(GIT_URL)"; \
		echo "GIT_BRANCH=$(GIT_BRANCH)"; \
		echo "GIT_COMMIT=$(GIT_COMMIT)"; \
		echo "GIT_TAG=$${GIT_TAG}"; \
	} > $(BUILD_ARGS_FILE)

image-build:	image-build-args-file
	@podman \
		$(PODMAN_PARAMS) \
		build \
			$(PODMAN_BUILD_PARAMS) \
			--build-arg-file $(BUILD_ARGS_FILE) \
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

### Make targets for cnf-reporting
# cnf-reporting-reset-collections-reqs
# cnf-reporting-clean-caches
# cnf-reporting-bootstrap
# cnf-reporting-gendata
# cnf-reporting-render
# cnf-reporting-run-playbook
# cnf-reporting-pylint
# cnf-reporting-ansible-lint
# cnf-reporting-shellcheck
# cnf-reporting-lint
# cnf-reporting-pytest
# cnf-reporting-test-verify
# cnf-reporting-test
# cnf-reporting-retest
	

venv-ensure:
	@echo "Ensuring venv $(VENV_DIR) is installed"
	mkdir -p $(VENV_DIR)
	python3.11 -m venv $(VENV_DIR)
	source $(VENV_DIR)/bin/activate
	pip install -r $(PY_REQS_BASE_FILE)

pydeps-update:	venv-ensure
	source $(VENV_DIR)/bin/activate
	@echo "Updating pydeps"
	CMD=(pip-compile)
	if [ -f $(PY_REQS_PREFIX).txt ]; then \
		CMD+=(--upgrade)
	else \
		CMD+=(--annotate)
	fi
	CMD+=($(PY_REQS_PREFIX).in)
	CMD+=(-o $(PY_REQS_PREFIX).txt)
	echo "Running: $${CMD[*]}"
	$${CMD[@]}
