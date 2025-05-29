PY ?= python3
VENV_DIR ?= .venv
RECREATE ?= 0
VARS_DIR ?= vars
DATA_FILE ?= data.yml
TPL_DIR ?= templates
PLAYBOOK ?= playbooks/infra/reporting/test_report_send.yml
GENERATOR ?= tools/gen_playbook_data.py

.DEFAULT_TARGETS: bootstrap

bootstrap:
	@printf -- "---- STARTED: $$(date -u) ----\n"
	@function venv_inst() { \
		local venv="$${1?cannot continue without venv}"; \
		local py="$${2:-"$(PY)"}"; \
		echo "installing new venv in $${venv}"; \
		$(PY) -m venv "$${venv}"; \
		source "$${venv}"/bin/activate; \
		python3 -m pip install --upgrade pip && echo "=> upgraded pip"; \
		pip3 install -r requirements.txt && echo "=> installed packages"; \
		printf "Installed: "; \
		python3 --version; \
	}; \
	if [ -d "$(VENV_DIR)" ]; then \
		echo "venv dir: '$(VENV_DIR)' exists"; \
		if [ $(RECREATE) -gt 0 ]; then \
			rm -fr $(VENV_DIR); \
			echo "deleted venv dir '$(VENV_DIR)'. [REASON: RECREATE=$(RECREATE)]"; \
			venv_inst "$(VENV_DIR)" "$(PY)"; \
		else \
			echo "nothing to do"; \
		fi; \
	else \
		venv_inst "$(VENV_DIR)" "$(PY)"; \
	fi
	@printf -- "---- FINISHED: $$(date -u) ----\n"

setup:
	TPL=$(TPL_DIR)/$(notdir $(PLAYBOOK)).j2; \
	EXTRA_VAR=$(VARS_DIR)/$(notdir $(PLAYBOOK)); \
	source "$(VENV_DIR)/bin/activate"; \
	if [ ! -r "$(DATA_FILE)" ]; then \
		echo "Running $(GENERATOR) script to generate $(DATA_FILE). [REASON: the file is missing]"; \
		python3 $(GENERATOR) --output=$(DATA_FILE); \
	fi; \
	echo "Generating extra variables file $${EXTRA_VAR} for playbook $(PLAYBOOK)"; \
	jinja --format=yaml --data=$(DATA_FILE) --output=$${EXTRA_VAR} $${TPL}
	echo "Now you can invoke the playbook via: make run PLAYBOOK=$(PLAYBOOK)"

run:
	source "$(VENV_DIR)/bin/activate"; \
	ansible-playbook -e @$(DATA_FILE) $(PLAYBOOK) -v
