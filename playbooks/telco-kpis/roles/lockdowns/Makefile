.PHONY: test test-hub test-hub-parse test-hub-capture test-spoke test-spoke-lockdown-uri test-spoke-retag-catalog test-resolve-release-image prepare-hub converge-hub verify-hub prepare-spoke converge-spoke verify-spoke clean help

# Get absolute path to eco-ci-cd root (5 levels up from role dir)
ECO_CI_CD_ROOT := $(shell cd ../../../.. && pwd)

# Default target
test: test-hub-parse test-hub-capture test-spoke test-spoke-lockdown-uri test-spoke-retag-catalog test-resolve-release-image

# Run hub parse tests in container
test-hub-parse:
	@echo "=========================================="
	@echo "  Running Hub PARSE Tests"
	@echo "=========================================="
	@podman run --rm --platform linux/amd64 \
		-v $(ECO_CI_CD_ROOT):/eco-ci-cd:Z \
		-w /eco-ci-cd/playbooks/telco-kpis/roles/lockdowns \
		-e ANSIBLE_ROLES_PATH=/eco-ci-cd/playbooks/telco-kpis/roles \
		--entrypoint /bin/sh \
		quay.io/ccardenosa/eco-ci-cd:latest \
		-c "ansible-playbook -i localhost, -c local molecule/hub/default/test.yml"
	@echo ""
	@echo "✓ Hub parse tests passed!"

# Run hub capture tests in container
test-hub-capture:
	@echo "=========================================="
	@echo "  Running Hub CAPTURE Tests"
	@echo "=========================================="
	@podman run --rm --platform linux/amd64 \
		-v $(ECO_CI_CD_ROOT):/eco-ci-cd:Z \
		-w /eco-ci-cd/playbooks/telco-kpis/roles/lockdowns \
		-e ANSIBLE_ROLES_PATH=/eco-ci-cd/playbooks/telco-kpis/roles \
		--entrypoint /bin/sh \
		quay.io/ccardenosa/eco-ci-cd:latest \
		-c "ansible-playbook -i localhost, -c local molecule/hub/default/test-capture.yml"
	@echo ""
	@echo "✓ Hub capture tests passed!"

# Run all hub tests (parse + capture)
test-hub: test-hub-parse test-hub-capture
	@echo ""
	@echo "✓ All hub tests passed!"

# Run spoke tests in container
test-spoke:
	@echo "=========================================="
	@echo "  Running Spoke Tests (Parse + Generate)"
	@echo "=========================================="
	@podman run --rm --platform linux/amd64 \
		-v $(ECO_CI_CD_ROOT):/eco-ci-cd:Z \
		-w /eco-ci-cd/playbooks/telco-kpis/roles/lockdowns \
		-e ANSIBLE_ROLES_PATH=/eco-ci-cd/playbooks/telco-kpis/roles \
		--entrypoint /bin/sh \
		quay.io/ccardenosa/eco-ci-cd:latest \
		-c "ansible-playbook -i localhost, -c local molecule/spoke/default/test.yml"
	@echo ""
	@echo "✓ Spoke tests passed!"

# Run spoke lockdown URI with digests test (reproduces empty metadata issue)
test-spoke-lockdown-uri:
	@echo "=========================================="
	@echo "  Running Spoke Lockdown URI with Digests Test"
	@echo "=========================================="
	@podman run --rm --platform linux/amd64 \
		-v $(ECO_CI_CD_ROOT):/eco-ci-cd:Z \
		-w /eco-ci-cd/playbooks/telco-kpis/roles/lockdowns \
		-e ANSIBLE_ROLES_PATH=/eco-ci-cd/playbooks/telco-kpis/roles \
		--entrypoint /bin/sh \
		quay.io/ccardenosa/eco-ci-cd:latest \
		-c "ansible-playbook -i localhost, -c local molecule/spoke-lockdown-uri-with-digests/default/test.yml"
	@echo ""
	@echo "✓ Spoke lockdown URI with digests test passed!"

# Run spoke retag catalog index tests
test-spoke-retag-catalog:
	@echo "=========================================="
	@echo "  Running Spoke Retag Catalog Index Tests"
	@echo "=========================================="
	@podman run --rm --platform linux/amd64 \
		-v $(ECO_CI_CD_ROOT):/eco-ci-cd:Z \
		-w /eco-ci-cd/playbooks/telco-kpis/roles/lockdowns \
		-e ANSIBLE_ROLES_PATH=/eco-ci-cd/playbooks/telco-kpis/roles \
		--entrypoint /bin/sh \
		quay.io/ccardenosa/eco-ci-cd:latest \
		-c "ansible-playbook -i localhost, -c local molecule/spoke-retag-catalog/default/test.yml"
	@echo ""
	@echo "✓ Spoke retag catalog index tests passed!"

# Run resolve-release-image tests
test-resolve-release-image:
	@echo "=========================================="
	@echo "  Running Resolve Release Image Tests"
	@echo "=========================================="
	@podman run --rm --platform linux/amd64 \
		-v $(ECO_CI_CD_ROOT):/eco-ci-cd:Z \
		-w /eco-ci-cd/playbooks/telco-kpis/roles/lockdowns \
		-e ANSIBLE_ROLES_PATH=/eco-ci-cd/playbooks/telco-kpis/roles \
		--entrypoint /bin/sh \
		quay.io/ccardenosa/eco-ci-cd:latest \
		-c "ansible-playbook -i localhost, -c local molecule/resolve-release-image/default/test.yml"
	@echo ""
	@echo "✓ Resolve release image tests passed!"

# Run individual hub test phases (for debugging - requires local ansible)
prepare-hub:
	@ansible-playbook -i localhost, -c local molecule/hub/default/prepare.yml

converge-hub:
	@ansible-playbook -i localhost, -c local molecule/hub/default/converge.yml

verify-hub:
	@ansible-playbook -i localhost, -c local molecule/hub/default/verify.yml

# Run individual spoke test phases (for debugging - requires local ansible)
prepare-spoke:
	@ansible-playbook -i localhost, -c local molecule/spoke/default/prepare.yml

converge-spoke:
	@ansible-playbook -i localhost, -c local molecule/spoke/default/converge.yml

verify-spoke:
	@ansible-playbook -i localhost, -c local molecule/spoke/default/verify.yml

# Clean up test artifacts
clean:
	@rm -rf /tmp/molecule-tests
	@rm -f /tmp/hub-lockdown.json /tmp/spoke-lockdown.json
	@echo "✓ Test artifacts cleaned"

# Help target
help:
	@echo "Lockdowns Role Tests"
	@echo ""
	@echo "Usage:"
	@echo "  make test                         Run all tests"
	@echo "  make test-hub                     Run all hub tests (parse + capture)"
	@echo "  make test-hub-parse               Run hub parse tests only"
	@echo "  make test-hub-capture             Run hub capture tests only"
	@echo "  make test-spoke                   Run spoke tests (parse + generate)"
	@echo "  make test-spoke-lockdown-uri      Run spoke lockdown URI with digests test"
	@echo "  make test-spoke-retag-catalog     Run spoke retag catalog index tests"
	@echo "  make test-resolve-release-image   Run resolve release image digest tests"
	@echo "  make prepare-hub               Run hub prepare phase only (requires ansible)"
	@echo "  make converge-hub              Run hub converge phase only (requires ansible)"
	@echo "  make verify-hub                Run hub verify phase only (requires ansible)"
	@echo "  make prepare-spoke             Run spoke prepare phase only (requires ansible)"
	@echo "  make converge-spoke            Run spoke converge phase only (requires ansible)"
	@echo "  make verify-spoke              Run spoke verify phase only (requires ansible)"
	@echo "  make clean                     Remove test artifacts"
	@echo ""
	@echo "Hub Parse Tests:"
	@echo "  1. prepare   - Creates mock hub lockdown JSON file"
	@echo "  2. converge  - Runs role parse action (read JSON)"
	@echo "  3. verify    - Validates parse results (10 assertions)"
	@echo ""
	@echo "Hub Capture Tests:"
	@echo "  1. prepare   - Sets up mock k8s_info responses"
	@echo "  2. converge  - Runs capture logic (generate JSON)"
	@echo "  3. verify    - Validates generated JSON (10 assertions)"
	@echo ""
	@echo "Spoke Tests:"
	@echo "  1. prepare   - Creates mock lockdown files (legacy + new) and metadata"
	@echo "  2. converge  - Runs parse (both formats) and generate logic"
	@echo "  3. verify    - Validates results (17 assertions)"
	@echo ""
	@echo "Spoke Lockdown URI with Digests Test:"
	@echo "  1. prepare   - Creates mock lockdown JSON with bundle/fbc digests"
	@echo "  2. converge  - Demonstrates empty lockdown_metadata_operators issue"
	@echo "  3. verify    - Confirms issue and validates workaround (3 assertions)"
	@echo ""
	@echo "Spoke Retag Catalog Index Tests:"
	@echo "  1. prepare   - Creates mock skopeo wrapper and authfile"
	@echo "  2. converge  - Runs retag task with mock skopeo (3 retags + 1 validation failure)"
	@echo "  3. verify    - Validates skopeo commands (10 assertions)"
	@echo ""
	@echo "Resolve Release Image Tests:"
	@echo "  1. prepare   - Creates mock skopeo (returns fake digest) and pull secret"
	@echo "  2. converge  - Tests digest passthrough, tag resolution, registry port handling"
	@echo "  3. verify    - Validates results and skopeo calls (6 assertions)"
