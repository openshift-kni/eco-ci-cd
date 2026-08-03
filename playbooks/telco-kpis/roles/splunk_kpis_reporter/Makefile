.PHONY: test prepare converge verify clean help

# Get absolute path to eco-ci-cd root (5 levels up from role dir)
ECO_CI_CD_ROOT := $(shell cd ../../../.. && pwd)

# Default target
test: test-splunk-reporter

# Run splunk reporter tests in container
test-splunk-reporter:
	@echo "=========================================="
	@echo "  Running Splunk KPIs Reporter Tests"
	@echo "=========================================="
	@podman run --rm --platform linux/amd64 \
		-v $(ECO_CI_CD_ROOT):/eco-ci-cd:Z \
		-w /eco-ci-cd/playbooks/telco-kpis/roles/splunk_kpis_reporter \
		-e ANSIBLE_ROLES_PATH=/eco-ci-cd/playbooks/telco-kpis/roles \
		--entrypoint /bin/sh \
		quay.io/telcov10n-ci/eco-ci-cd:latest \
		-c "ansible-playbook -i localhost, -c local molecule/default/test.yml"
	@echo ""
	@echo "Splunk KPIs reporter tests passed!"

# Run individual test phases (for debugging - requires local ansible)
prepare:
	@ansible-playbook -i localhost, -c local molecule/default/prepare.yml

converge:
	@ansible-playbook -i localhost, -c local molecule/default/converge.yml

verify:
	@ansible-playbook -i localhost, -c local molecule/default/verify.yml

# Clean up test artifacts
clean:
	@rm -rf /tmp/molecule-splunk-reporter
	@echo "Test artifacts cleaned"

# Help target
help:
	@echo "Splunk KPIs Reporter Role Tests"
	@echo ""
	@echo "Usage:"
	@echo "  make test       Run all tests (in container)"
	@echo "  make prepare    Run prepare phase only (requires ansible)"
	@echo "  make converge   Run converge phase only (requires ansible)"
	@echo "  make verify     Run verify phase only (requires ansible)"
	@echo "  make clean      Remove test artifacts"
	@echo ""
	@echo "Test Phases:"
	@echo "  1. prepare   - Creates mock report_data with 7 test types (8 events)"
	@echo "  2. converge  - Runs splunk_kpis_reporter in dry-run mode"
	@echo "  3. verify    - Validates event JSON schema compliance and type safety"
	@echo ""
	@echo "Note: Individual phases require local Ansible installation."
	@echo "      Use 'make test' to run in eco-ci-cd container (recommended)."
