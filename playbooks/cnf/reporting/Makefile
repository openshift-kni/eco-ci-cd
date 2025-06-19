# include optional local variables overrides file:
-include vars.local.mk
# include variables definitions file
include vars.mk

# $(warning DEBUG: Inside Makefile - COLLECTION_REQ_FILES_TXT = "$(COLLECTION_REQ_FILES_TXT)")

# Destination for the modified requirements.yml
DST_REQS = requirements.yml
# Source requirements.yml, using git rev-parse for the repository root
SRC_REQS = $(shell git rev-parse --show-toplevel)/$(DST_REQS)

APPS = $(PY) ansible-playbook ansible-galaxy yq diff
APPS_DEV := $(APPS) pylint ansible-lint shellcheck
KEEP_ARTIFACTS ?= false

CLEANUP_LIST := $(ANSIBLE_COLLECTIONS_PATH) $(CACHE_PATHS)	$(HOME)/.ansible/collections

.ONESHELL:
.DEFAULT_TARGETS: bootstrap
.PHONY: make-requirements print_vars

check-requirements:
	@APPS=($(APPS))
	@if [[ "$${DEV_MODE}" -gt 0 ]]; then
		@APPS=($(APPS_DEV))
	@fi
	@$(WRAPPER) "$@" "$${APPS[@]}"


reset-collections-reqs:
	$(MAKE) check-requirements
	@echo "DEL_COLLECTIONS: $(DEL_COLLECTIONS)"
	$(WRAPPER) "$@" $(SRC_REQS) $(DEL_COLLECTIONS) $(DST_REQS)

clean-caches:	$(CLEANUP_LIST)
	@rm -fr "$^"

buildpkg:
	$(MAKE) reset-collections-reqs
	$(MAKE) clean-caches
	@export COLLECTION_ROOT=$(COLLECTION_ROOT)
	@$(WRAPPER) "${@}"

bootstrap:
	@if [[ "$(RECREATE)" -gt 0 ]]; then
		@SUB_TARGET="buildpkg"
		@echo "Launching target $${SUB_TARGET}"
		$(MAKE) $${SUB_TARGET}
		rc=$$?
		@echo "Finished  target: $${SUB_TARGET} with rc=$${rc}"
	@fi
	@export COLLECTION_REQ_FILES_TXT="$(COLLECTION_REQ_FILES_TXT)"
	@$(WRAPPER) $@

gendata:
	@$(WRAPPER) $@

render:
	@$(WRAPPER) $@

run-playbook:
	@$(WRAPPER) $@

pylint: $(GENERATOR)
	@pylint $(GENERATOR)

ansible-lint: $(PLAYBOOK)
	@ansible-lint $(PLAYBOOK)

shellcheck: $(WRAPPER)
	@shellcheck -o all $(WRAPPER)

lint:	pylint	ansible-lint shellcheck

pytest:
	@pytest -v ./tools

test:
	@echo "ANSIBLE_COLLECTIONS_PATH='$(ANSIBLE_COLLECTIONS_PATH)'"
	@$(WRAPPER) $@
	@EXPECTED_EVENT=$(PWD)/fixtures/$(TEST)/event.json
	@ACTUAL_EVENT=$(PWD)/curr.event.json
	@cat $(PWD)/event.json | jq > $${ACTUAL_EVENT}
	@if ! diff --color --unified $${EXPECTED_EVENT} $${ACTUAL_EVENT}; then
		rc=$$?
		echo "test for $(TEST) failed with rc=$${rc}"
		echo "ACTION ITEMS: review the formatted event $${ACTUAL_EVENT} and compare it to $${EXPECTED_EVENT}"
		exit "$${rc}"
	fi
	@echo "test for $(TEST) passed."
	if [[ "$${KEEP_ARTIFACTS}" -gt 0 ]]; then
		echo "Keeping artifacts. [REASON: KEEP_ARTIFACTS=$${KEEP_ARTIFACTS}]"
		exit 0
	fi
	@echo "Deleting artifacts. [REASON: KEEP_ARTIFACTS=$${KEEP_ARTIFACTS}]"
	rm $(PWD)/*event.json

retest:
	$(MAKE) rebuild
	$(MAKE) bootstrap RECREATE=1
	$(MAKE) test
