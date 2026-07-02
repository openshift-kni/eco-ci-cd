.PHONY: test test-check test-remove prepare converge verify clean help

# Get absolute path to eco-ci-cd root (5 levels up from role dir)
ECO_CI_CD_ROOT := $(shell cd ../../../.. && pwd)

# Default target
test: test-check test-remove

# Run check-status tests in container
test-check:
	@echo "=========================================="
	@echo "  Running Check Status Tests"
	@echo "=========================================="
	@podman run --rm --platform linux/amd64 \
		-v $(ECO_CI_CD_ROOT):/eco-ci-cd:Z \
		-w /eco-ci-cd/playbooks/telco-kpis/roles/spoke_hub_connectivity \
		-e ANSIBLE_ROLES_PATH=/eco-ci-cd/playbooks/telco-kpis/roles \
		--entrypoint /bin/sh \
		quay.io/ccardenosa/eco-ci-cd:latest \
		-c "ansible-playbook -i localhost, -c local molecule/check-status/default/test.yml"
	@echo ""
	@echo "✓ Check status tests passed!"

# Run remove tests in container
test-remove:
	@echo "=========================================="
	@echo "  Running Remove iptables Tests"
	@echo "=========================================="
	@podman run --rm --platform linux/amd64 \
		-v $(ECO_CI_CD_ROOT):/eco-ci-cd:Z \
		-w /eco-ci-cd/playbooks/telco-kpis/roles/spoke_hub_connectivity \
		-e ANSIBLE_ROLES_PATH=/eco-ci-cd/playbooks/telco-kpis/roles \
		--entrypoint /bin/sh \
		quay.io/ccardenosa/eco-ci-cd:latest \
		-c "ansible-playbook -i localhost, -c local molecule/remove/default/test.yml"
	@echo ""
	@echo "✓ Remove tests passed!"

# Run individual test phases (for debugging - requires local ansible)
prepare:
	@ansible-playbook -i localhost, -c local molecule/check-status/default/prepare.yml

converge:
	@ansible-playbook -i localhost, -c local molecule/check-status/default/converge.yml

verify:
	@ansible-playbook -i localhost, -c local molecule/check-status/default/verify.yml

# Clean up test artifacts
clean:
	@rm -rf /tmp/molecule-tests
	@rm -f /tmp/spoke-hub-connectivity-*
	@echo "✓ Test artifacts cleaned"

# Help target
help:
	@echo "Spoke Hub Connectivity Role Tests"
	@echo ""
	@echo "Usage:"
	@echo "  make test          Run all tests (check + remove)"
	@echo "  make test-check    Run check-status template tests"
	@echo "  make test-remove   Run remove iptables template tests"
	@echo "  make prepare       Run prepare phase only (requires ansible)"
	@echo "  make converge      Run converge phase only (requires ansible)"
	@echo "  make verify        Run verify phase only (requires ansible)"
	@echo "  make clean         Remove test artifacts"
	@echo ""
	@echo "Check Status Tests:"
	@echo "  1. prepare   - Creates mock spoke-hub configuration variables"
	@echo "  2. converge  - Generates check-status templates (BMC, cluster, registry)"
	@echo "  3. verify    - Validates template outputs (10 assertions)"
	@echo ""
	@echo "Remove Tests:"
	@echo "  1. prepare   - Creates mock variables with loop context"
	@echo "  2. converge  - Generates removal templates (BMC, cluster, registry)"
	@echo "  3. verify    - Validates removal commands and error handling (10 assertions)"
