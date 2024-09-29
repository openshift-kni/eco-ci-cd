#!/bin/bash

nrop_token=$(oc create token privileged-sa -n rapidast-nrop)

# Define the content for the ConfigMap
configmap_content=$(cat <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: rapidast-configmap
  namespace: rapidast-nrop
data:
  rapidastconfig.yaml: |
    config:
      configVersion: 4

    application:
      shortName: "nrop"
      url: "https://kubernetes.default.svc"

    general:
      authentication:
        type: "http_header"
        parameters:
          name: "Authorization"
          value: "Bearer ${nrop_token}"
      container:
        type: "none"

    scanners:
      zap:
        apiScan:
          apis:
            apiUrl: "https://kubernetes.default.svc/openapi/v3/apis/nrop.openshift.io/v1alpha1"
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
echo "$configmap_content" | oc -n rapidast-nrop create -f -

