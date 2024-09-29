#!/bin/bash

ptp_token=$(oc create token privileged-sa -n rapidast-ptp)

# Define the content for the ConfigMap
configmap_content=$(cat <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: rapidast-configmap
  namespace: rapidast-ptp
data:
  rapidastconfig.yaml: |
    config:
      configVersion: 4

    application:
      shortName: "ptp"
      url: "https://kubernetes.default.svc"

    general:
      authentication:
        type: "http_header"
        parameters:
          name: "Authorization"
          value: "Bearer ${ptp_token}"
      container:
        type: "none"

    scanners:
      zap:
        apiScan:
          apis:
            apiUrl: "https://kubernetes.default.svc/openapi/v3/apis/ptp.openshift.io/v1alpha1"
        passiveScan:
          disabledRules: "2,10015,10027,10096,10024,10054"
        activeScan:
          policy: "Operator-scan"
        miscOptions:
          enableUI: False
          updateAddons: False
EOF
)

# Create the ConfigMap
echo "$configmap_content" | oc -n rapidast-ptp create -f -

