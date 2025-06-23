DEV_MODE   		?= 0
# do not recreate by default
RECREATE   		?= 0
# use the default python3.
PY         		?= python3
# where to install current venv directory
VENV_DIR   		?= $(PWD)/.venv
# ansible vars/ directory
VARS_DIR    	?= $(PWD)/vars
# jinja data file path
OUT_DIR    		?= $(PWD)/output
# jinja templates directory
TPL_DIR    		?= $(PWD)/templates
# jinja intermediate data file
DATA_FILE  		?= $(OUT_DIR)/data.yml
# ansible playbook
PLAYBOOK   		?= test_report_send.yml
# extra data generator script
GENERATOR  		?= tools/gen_playbook_extra_vars.py
# extra data file template
TPL_FILE    	= $(TPL_DIR)/$(notdir $(PLAYBOOK)).j2
# extra vars file for the ansible playbook
EXTRA_VARS  	= $(VARS_DIR)/$(notdir $(PLAYBOOK))
# additional ansible parameters
EXTRA_PARAMS 	?= -vv
ANSIBLE_COLLECTIONS_PATH ?= $(PWD)/collections
SHELL			= /bin/bash
CI_TYPE   		?= dci
WRAPPER			?= ./tools/make_wrapper.sh
SCRIPT_DBG	?= $(DEV_MODE)

CACHE_PATHS		?= $(PWD)/.ansible
COLLECTION_ROOT ?= $(HOME)/src/github.com/mvk/ocp
COLLECTIONS_REQS_LOCAL 		?= requirements.local.yml
COLLECTION_REQ_FILES_TXT 	?= requirements.yml
DEL_COLLECTIONS 			?= redhatci.ocp

# $(warning DEBUG: Inside vars.mk - COLLECTION_REQ_FILES_TXT = "$(COLLECTION_REQ_FILES_TXT)")
