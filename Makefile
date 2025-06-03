# whether we shall not send data and set specific CI
DEV_MODE   ?= 0
# do not recreate by default
RECREATE   ?= 0
# use the default python3.
PY         ?= python3
# where to install current venv directory
VENV_DIR   ?= $(PWD)/.venv
# ansible vars/ directory
VAR_DIR    ?= $(PWD)/vars
# jinja data file path
OUT_DIR    ?= $(PWD)/output
# jinja templates directory
TPL_DIR    ?= $(PWD)/templates
# jinja intermediate data file
DATA_FILE  ?= $(OUT_DIR)/data.yml
# ansible playbook file
PLAYBOOK   ?= playbooks/infra/reporting/test_report_send.yml
# extra data generator script
GENERATOR  ?= tools/gen_playbook_data.py
# extra data file template
TPL_FILE    = $(TPL_DIR)/$(notdir $(PLAYBOOK)).j2
# extra vars for the playbook
EXTRA_VARS  = $(VAR_DIR)/$(notdir $(PLAYBOOK))
SHELL       = /bin/bash

.DEFAULT_TARGETS: bootstrap

bootstrap:
	@printf -- "---- STARTING $@: $(shell date -u) ----\n"
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
	@printf -- "---- FINISHED $@: $$(date -u) ----\n"

gendata:
	@printf -- "---- STARTING $@: $(shell date -u) ----\n"
	@function datagen() { \
		local generator data venv; \
		local -a cmd; \
		generator="$${1:-"$(GENERATOR)"}"; \
		data="$${2:-"$(DATA_FILE)"}"; \
		venv="$${3:-"$(VENV_DIR)"}"; \
		echo "Running $${generator} script to generate $${data}. [REASON: the file is missing]"; \
		cmd=("python3" "$${generator}" "--output=$${data}"); \
		if [[ "$(DEV_MODE)" -gt 0 ]]; then \
			cmd+=("--skip-ci-detect" "--skip-send"); \
		fi; \
		source "$${venv}"/bin/activate; \
		"$${cmd[@]}" || exit 1; \
	}; \
	source $(VENV_DIR)/bin/activate; \
	if [ "$(RECREATE)" -gt 0 ]; then \
		datagen $(GENERATOR) $(DATA_FILE) || exit $$?; \
	fi; \
	if ! [ -r "$(DATA_FILE)" ]; then \
		datagen "$(GENERATOR)" "$(DATA_FILE)" || exit $$?; \
	fi
	@printf -- "---- FINISHED $@: $$(date -u) ----\n"

render:	gendata
	@printf -- "---- STARTING $@: $$(date -u) ----\n"
	echo "Generating extra variables file $(EXTRA_VAR) for playbook $(PLAYBOOK)"; \
	source $(VENV_DIR)/bin/activate; \
	jinja \
		--format=yaml \
		--data="$(DATA_FILE)" \
		--output="$(EXTRA_VAR)" "$(TPL_FILE)" || exit $$?; \
	echo "Now you can invoke the playbook via: make run PLAYBOOK=$(PLAYBOOK)"
	@printf -- "---- FINISHED $@: $$(date -u) ----\n"

run:
	@printf -- "---- STARTING $@: $$(date -u) ----\n"
	source $(VENV_DIR)/bin/activate; \
	ansible-playbook -e @$(EXTRA_VAR) $(PLAYBOOK) -v
	@printf -- "---- FINISHED $@: $$(date -u) ----\n"
