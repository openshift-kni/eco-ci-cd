
#!/bin/usr/env bash

# Those value are set to align with both Prow and Jenkins Jobs
ARTIFACT_DIR=${ARTIFACT_DIR:-/artifacts}
SHARED_DIR=${SHARED_DIR:-/artifacts}

if [[ -f ${ARTIFACT_DIR}*.xml ]]; then
        echo "Found unittest files"
        script_url=https://raw.githubusercontent.com/openshift-kni/telco5gci/refs/heads/master/j2html.py
        requirements_url=https://raw.githubusercontent.com/openshift-kni/telco5gci/refs/heads/master/requirements.txt

        echo "Install dependencies"
        pip install -r ${requirements_url}

        echo "Download script"
        curl -o /tmp/j2html.py ${script_url}

        python3 /tmp/j2html.py --format xml ${SHARED_DIR}/*.xml --output ${ARTIFACT_DIR}/nto_test_report.html 2>/dev/null || echo "No JUnit files found to generate HTML report"

else
        echo "Did not find any unit test files, skipping..."
fi