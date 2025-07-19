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
.PHONY: check-requirements

check-requirements:
	@APPS=($(APPS))
	@if [[ "$${DEV_MODE}" -gt 0 ]]; then
		@APPS=($(APPS_DEV))
	@fi
	@$(WRAPPER) "$@" "$${APPS[@]}"

reset-collections-reqs:
	$(MAKE) check-requirements
	@if echo "$(COLLECTION_REQ_FILES_TXT)" | grep -q ","; then
		@echo "DEL_COLLECTIONS: $(DEL_COLLECTIONS)"
		$(WRAPPER) "$@" $(SRC_REQS) $(DEL_COLLECTIONS) $(DST_REQS)
	@fi

clean-caches:	$(CLEANUP_LIST)
	@rm -fr "$^"

bootstrap:
	@if [[ "$(RECREATE)" -gt 0 ]]; then
		@$(MAKE) clean-caches
	@fi
	@export COLLECTION_REQ_FILES_TXT="$(COLLECTION_REQ_FILES_TXT)"
	@$(WRAPPER) $@

gendata:
	@$(WRAPPER) $@ || ""

render:
	@$(WRAPPER) $@ EXTRA_VARS=$(EXTRA_VARS)

run-playbook:
	@$(WRAPPER) $@

pylint: $(GENERATOR)
	@pylint $(GENERATOR)

ansible-lint: $(PLAYBOOK)
	@ansible-lint $(PLAYBOOK)

shellcheck: $(WRAPPER)
	@shellcheck -o all $(WRAPPER)

infra-lint:	pylint	ansible-lint shellcheck

pytest:
	@pytest -v ./tools

infra-test:	pytest

test-verify:
	@echo "DEBUG: running $@ with: RAW_ACTUAL_EVENT=$(RAW_ACTUAL_EVENT), ACTUAL_EVENT=$(ACTUAL_EVENT), EXPECTED_EVENT=$(EXPECTED_EVENT)"
	@cat $(RAW_ACTUAL_EVENT) | jq > $(ACTUAL_EVENT)
	@if ! diff --color --unified $(EXPECTED_EVENT) $(ACTUAL_EVENT); then
		@rc=$$?
		@echo "test for ci=$(CI_TYPE) failed with rc=$${rc}"
		@echo "ACTION ITEMS: review the formatted event $(ACTUAL_EVENT) and compare it to $(EXPECTED_EVENT)"
		@exit "$${rc}"
	@fi
	@echo "test for $(CI_TYPE) have passed."
	@if [[ "$(KEEP_ARTIFACTS)" -gt 0 ]]; then
		@echo "Keeping artifacts. [REASON: KEEP_ARTIFACTS=$(KEEP_ARTIFACTS)]"
		@exit 0
	@fi
	@rm $(RAW_ACTUAL_EVENT) $(ACTUAL_EVENT)
	@echo "Deleted $(RAW_ACTUAL_EVENT) and $(ACTUAL_EVENT). [REASON: KEEP_ARTIFACTS=$(KEEP_ARTIFACTS)]"

test:
	@echo "ANSIBLE_COLLECTIONS_PATH='$(ANSIBLE_COLLECTIONS_PATH)'"
	@$(WRAPPER) $@
	$(eval EXPECTED_EVENT = $(PWD)/fixtures/$(CI_TYPE)/event.json)
	$(eval ACTUAL_EVENT = $(PWD)/curr.event.json)
	$(eval RAW_ACTUAL_EVENT = $(PWD)/event.json)
	$(MAKE) test-verify EXPECTED_EVENT=$(EXPECTED_EVENT) ACTUAL_EVENT=$(ACTUAL_EVENT) RAW_ACTUAL_EVENT=$(RAW_ACTUAL_EVENT)

retest:
	$(MAKE) bootstrap RECREATE=1
	$(MAKE) test
