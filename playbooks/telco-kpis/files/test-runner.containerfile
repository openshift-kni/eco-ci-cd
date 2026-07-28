# Containerfile for telco-kpis test runner
# Used by --podman mode in run-local-test-*.sh scripts
#
# Build:  podman build -t telco-kpis-test-runner:latest -f test-runner.containerfile .
# Manual: podman run -it --rm -v /path/kubeconfig:/tmp/kubeconfig:ro telco-kpis-test-runner:latest bash

FROM registry.access.redhat.com/ubi9-minimal:latest

ARG GO_VERSION=1.22.10

RUN microdnf install -y \
      bash git tar gzip wget make \
      findutils procps-ng which diffutils binutils \
      jq python3 python3-pip skopeo \
      openssl ca-certificates rsync \
      nmap-ncat iputils \
    && microdnf clean all

# ipmitool (needed for reboot test) from CentOS Stream 9 AppStream
RUN printf '[centos9-appstream]\nname=CentOS Stream 9 - AppStream\nbaseurl=https://mirror.stream.centos.org/9-stream/AppStream/$basearch/os/\ngpgcheck=0\nenabled=1\n' \
      > /etc/yum.repos.d/centos9-appstream.repo \
    && microdnf install -y ipmitool \
    && rm -f /etc/yum.repos.d/centos9-appstream.repo \
    && microdnf clean all

RUN echo | openssl s_client -showcerts -connect prometheus.ran-metrics.telco5g.corp.redhat.com:443 2>/dev/null \
      | awk '/BEGIN CERT/,/END CERT/' > /etc/pki/ca-trust/source/anchors/ran-metrics.pem \
    && update-ca-trust \
    && echo "--insecure" > /root/.curlrc

RUN pip3 install --no-cache-dir jinja2-tools stcrestclient

RUN ARCH=$(uname -m) && \
    case "$ARCH" in \
      x86_64)   GOARCH=amd64; OCARCH="" ;; \
      aarch64)  GOARCH=arm64; OCARCH="-arm64" ;; \
      *) echo "Unsupported architecture: $ARCH" && exit 1 ;; \
    esac && \
    curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-${GOARCH}.tar.gz" \
      | tar -C /usr/local -xzf - && \
    curl -fsSL "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux${OCARCH}.tar.gz" \
      | tar -C /usr/local/bin -xzf - oc kubectl

# Preinstall kube-compare plugin binary from official release artifacts.
# This avoids runtime/compile dependency on newer Go toolchains.
ARG KUBE_COMPARE_VERSION=v0.12.0
# sha256 of kube-compare_linux_{amd64,arm64}.tar.gz for KUBE_COMPARE_VERSION above — bump together
ARG KUBE_COMPARE_SHA256_amd64=32966e0d0b827f80b565df50caf57aca1e207ab1a877f5ec2339b215bc5fb2d0
ARG KUBE_COMPARE_SHA256_arm64=812f77226ea5a6bf66b144fd9072bbd601c5e756de9fef43a7ed1e5a33777cbe
RUN ARCH=$(uname -m) && \
    case "$ARCH" in \
      x86_64)   KC_ARCH=amd64 ;; \
      aarch64)  KC_ARCH=arm64 ;; \
      *) echo "Unsupported architecture for kube-compare: $ARCH" && exit 1 ;; \
    esac && \
    eval KC_SHA256=\$KUBE_COMPARE_SHA256_${KC_ARCH} && \
    curl -fsSL -o /tmp/kc.tgz "https://github.com/openshift/kube-compare/releases/download/${KUBE_COMPARE_VERSION}/kube-compare_linux_${KC_ARCH}.tar.gz" && \
    echo "${KC_SHA256}  /tmp/kc.tgz" | sha256sum -c - && \
    tar -C /usr/local/bin -xzf /tmp/kc.tgz kubectl-cluster_compare && rm -f /tmp/kc.tgz && \
    chmod 0755 /usr/local/bin/kubectl-cluster_compare

# Copy registry authentication and certificates into image
# These are generated during setup-test-runner.yml from vault credentials
COPY auth.json /run/containers/0/auth.json
COPY certs.d /etc/containers/certs.d
RUN chmod 0600 /run/containers/0/auth.json

ENV PATH="/usr/local/go/bin:/root/go/bin:/root/bin:/root/.local/bin:${PATH}" \
    GOPATH="/root/go"

WORKDIR /workspace
