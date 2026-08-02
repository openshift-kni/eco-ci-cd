.PHONY: test prepare converge verify clean help

ECO_CI_CD_ROOT := $(shell cd ../../../.. && pwd)

test:
	@echo "=========================================="
	@echo "  Running remote_flock Role Tests"
	@echo "=========================================="
	@podman run --rm --platform linux/amd64 \
		-v $(ECO_CI_CD_ROOT):/eco-ci-cd:Z \
		-w /eco-ci-cd/playbooks/telco-kpis/roles/remote_flock \
		-e ANSIBLE_ROLES_PATH=/eco-ci-cd/playbooks/telco-kpis/roles \
		--entrypoint /bin/sh \
		quay.io/telcov10n-ci/eco-ci-cd:latest \
		-c "ansible-playbook -i localhost, -c local molecule/default/test.yml"
	@echo ""
	@echo "remote_flock role tests passed!"

prepare:
	@ansible-playbook -i localhost, -c local molecule/default/prepare.yml

converge:
	@ansible-playbook -i localhost, -c local molecule/default/converge.yml

verify:
	@ansible-playbook -i localhost, -c local molecule/default/verify.yml

clean:
	@rm -rf /tmp/molecule-remote-flock
	@rm -f /tmp/remote_flock_molecule_test_acquire.sh
	@rm -f /tmp/remote_flock_molecule_test_release.sh
	@rm -rf /var/lock/remote_flock_molecule_test.lock*
	@echo "Test artifacts cleaned"

help:
	@echo "remote_flock Role Tests"
	@echo ""
	@echo "Usage:"
	@echo "  make test       Run all tests (in container)"
	@echo "  make prepare    Run prepare phase only (requires ansible)"
	@echo "  make converge   Run converge phase only (requires ansible)"
	@echo "  make verify     Run verify phase only (requires ansible)"
	@echo "  make clean      Remove test artifacts"
