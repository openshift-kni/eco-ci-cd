.PHONY: test test-hub test-hub-parse test-hub-capture test-spoke test-hub-local test-spoke-local prepare converge verify clean help

# Get absolute path to eco-ci-cd root (5 levels up from role dir)
ECO_CI_CD_ROOT := $(shell cd ../../../.. && pwd)

# Default target
test: test-hub-parse test-hub-capture

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

# Run spoke tests in container (when implemented)
test-spoke:
	@echo "=========================================="
	@echo "  Running Lockdowns Role Spoke Tests"
	@echo "=========================================="
	@echo "TODO: Spoke tests not yet implemented"

# Run individual hub test phases (for debugging - requires local ansible)
prepare-hub:
	@ansible-playbook -i localhost, -c local molecule/hub/default/prepare.yml

converge-hub:
	@ansible-playbook -i localhost, -c local molecule/hub/default/converge.yml

verify-hub:
	@ansible-playbook -i localhost, -c local molecule/hub/default/verify.yml

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
	@echo "  make test              Run all hub tests (parse + capture)"
	@echo "  make test-hub          Run all hub tests (parse + capture)"
	@echo "  make test-hub-parse    Run hub parse tests only"
	@echo "  make test-hub-capture  Run hub capture tests only"
	@echo "  make test-spoke        Run spoke tests (TODO)"
	@echo "  make prepare-hub       Run hub prepare phase only (requires ansible)"
	@echo "  make converge-hub      Run hub converge phase only (requires ansible)"
	@echo "  make verify-hub        Run hub verify phase only (requires ansible)"
	@echo "  make clean             Remove test artifacts"
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
