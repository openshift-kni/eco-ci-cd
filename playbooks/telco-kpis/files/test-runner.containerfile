# Containerfile for telco-kpis test runner
# Used by --podman mode in run-local-test-*.sh scripts
#
# Build:  podman build -t quay.io/telcov10n-ci/telco-kpis-test-runner:latest -f test-runner.containerfile .
# Manual: podman run -it --rm -v /path/kubeconfig:/tmp/kubeconfig:ro quay.io/telcov10n-ci/telco-kpis-test-runner:latest bash

FROM registry.access.redhat.com/ubi9-minimal:latest

ARG GO_VERSION=1.22.10
# We need to have a versioned OCP release or this will break whenever the "stable" version is changed.
ARG OCP_VERSION=4.22.5

RUN microdnf install -y \
      bash git tar gzip wget make \
      findutils procps-ng which diffutils binutils \
      jq python3 python3-pip skopeo \
      openssl ca-certificates rsync \
      nmap-ncat iputils \
    && microdnf clean all

# ipmitool and python3.11 (needed for reboot test and report generation) from CentOS Stream 9 AppStream
RUN printf '[centos9-appstream]\nname=CentOS Stream 9 - AppStream\nbaseurl=https://mirror.stream.centos.org/9-stream/AppStream/$basearch/os/\ngpgcheck=1\ngpgkey=https://www.centos.org/keys/RPM-GPG-KEY-CentOS-Official-SHA256\nenabled=1\n' \
      > /etc/yum.repos.d/centos9-appstream.repo \
    && microdnf install -y ipmitool \
    && rm -f /etc/yum.repos.d/centos9-appstream.repo \
    && microdnf clean all


RUN pip3 install --no-cache-dir jinja2-tools stcrestclient

RUN ARCH=$(uname -m) && \
    case "$ARCH" in \
      x86_64)   GOARCH=amd64; OCARCH="" ;; \
      aarch64)  GOARCH=arm64; OCARCH="-arm64" ;; \
      *) echo "Unsupported architecture: $ARCH" && exit 1 ;; \
    esac && \
    GO_SHA256=$(curl -fsSL "https://dl.google.com/go/go${GO_VERSION}.linux-${GOARCH}.tar.gz.sha256") && \
    [ -n "${GO_SHA256}" ] || { echo "ERROR: could not fetch Go SHA256 for go${GO_VERSION} ${GOARCH}"; exit 1; } && \
    curl -fsSL -o /tmp/go.tgz "https://go.dev/dl/go${GO_VERSION}.linux-${GOARCH}.tar.gz" && \
    echo "${GO_SHA256}  /tmp/go.tgz" | sha256sum -c - && \
    tar -C /usr/local -xzf /tmp/go.tgz && rm -f /tmp/go.tgz && \
    curl -fsSL -o /tmp/oc.tgz "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/${OCP_VERSION}/openshift-client-linux${OCARCH}.tar.gz" && \
    OC_SHA256=$(curl -fsSL "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/${OCP_VERSION}/sha256sum.txt" 2>/dev/null \
      | tr -d '\r' \
      | grep " openshift-client-linux${OCARCH}\.tar\.gz$" \
      | awk '{print $1}' | head -1) && \
    if [ -n "${OC_SHA256}" ]; then \
      echo "${OC_SHA256}  /tmp/oc.tgz" | sha256sum -c - || { echo "ERROR: OC checksum mismatch for OCP ${OCP_VERSION}"; exit 1; }; \
    else \
      echo "WARNING: sha256sum.txt not available for OCP ${OCP_VERSION} — skipping verification, computed hash:"; \
      sha256sum /tmp/oc.tgz; \
    fi && \
    tar -C /usr/local/bin -xzf /tmp/oc.tgz oc kubectl && rm -f /tmp/oc.tgz

# Preinstall kube-compare plugin binary from official release artifacts.
# This avoids runtime/compile dependency on newer Go toolchains.
ARG KUBE_COMPARE_VERSION=v0.12.0
RUN ARCH=$(uname -m) && \
    case "$ARCH" in \
      x86_64)   KC_ARCH=amd64 ;; \
      aarch64)  KC_ARCH=arm64 ;; \
      *) echo "Unsupported architecture for kube-compare: $ARCH" && exit 1 ;; \
    esac && \
    KC_VERSION_NUM="${KUBE_COMPARE_VERSION#v}" && \
    curl -fsSL -o /tmp/kc.tgz "https://github.com/openshift/kube-compare/releases/download/${KUBE_COMPARE_VERSION}/kube-compare_linux_${KC_ARCH}.tar.gz" && \
    KC_SHA256=$(curl -fsSL "https://github.com/openshift/kube-compare/releases/download/${KUBE_COMPARE_VERSION}/kube-compare_${KC_VERSION_NUM}_checksums.txt" 2>/dev/null \
      | tr -d '\r' | grep " kube-compare_linux_${KC_ARCH}.tar.gz$" | awk '{print $1}') && \
    if [ -n "${KC_SHA256}" ]; then \
      echo "${KC_SHA256}  /tmp/kc.tgz" | sha256sum -c - || { echo "ERROR: kube-compare checksum mismatch for ${KUBE_COMPARE_VERSION}"; exit 1; }; \
    else \
      echo "WARNING: checksums not available for kube-compare ${KUBE_COMPARE_VERSION} — skipping verification, computed hash:"; \
      sha256sum /tmp/kc.tgz; \
    fi && \
    tar -C /usr/local/bin -xzf /tmp/kc.tgz kubectl-cluster_compare && rm -f /tmp/kc.tgz && \
    chmod 0755 /usr/local/bin/kubectl-cluster_compare


ENV PATH="/usr/local/go/bin:/root/go/bin:/root/bin:/root/.local/bin:${PATH}" \
    GOPATH="/root/go"

WORKDIR /workspace
