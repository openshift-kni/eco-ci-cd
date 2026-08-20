# Containerfile for telco-kpis test runner
# Used by --podman mode in run-local-test-*.sh scripts
#
# Build:  podman build -t telco-kpis-test-runner:latest -f test-runner.containerfile .
# Manual: podman run -it --rm -v /path/kubeconfig:/tmp/kubeconfig:ro telco-kpis-test-runner:latest bash

FROM registry.access.redhat.com/ubi9-minimal:latest

ARG GO_VERSION=1.22.10
# We need to have a versioned OCP release or this will break whenever the "stable" version is changed.
ARG OCP_VERSION=4.22.5
# sha256 of https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz — bump together with GO_VERSION
ARG GO_SHA256_amd64=736ce492a19d756a92719a6121226087ccd91b652ed5caec40ad6dbfb2252092
ARG GO_SHA256_arm64=5213c5e32fde3bd7da65516467b7ffbfe40d2bb5a5f58105e387eef450583eec
ARG OC_SHA256_amd64=6bf95f88311026b2f0582eb180a053aa71ebd76e426b689f3da56535f0578392
ARG OC_SHA256_arm64=9743d4728a75d784070ad6501d2346126e412e39862ae1c916b754d835df724f

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

RUN echo | openssl s_client -showcerts -connect prometheus.ran-metrics.telco5g.corp.redhat.com:443 2>/dev/null \
      | awk '/BEGIN CERT/,/END CERT/' > /etc/pki/ca-trust/source/anchors/ran-metrics.pem \
    && update-ca-trust
# NOTE: do NOT set `curl --insecure` globally — the ran-metrics CA above is the only intercepting endpoint.

RUN pip3 install --no-cache-dir jinja2-tools stcrestclient

RUN ARCH=$(uname -m) && \
    case "$ARCH" in \
      x86_64)   GOARCH=amd64; OCARCH="" ;; \
      aarch64)  GOARCH=arm64; OCARCH="-arm64" ;; \
      *) echo "Unsupported architecture: $ARCH" && exit 1 ;; \
    esac && \
    eval GO_SHA256=\$GO_SHA256_${GOARCH} && eval OC_SHA256=\$OC_SHA256_${GOARCH} && \
    curl -fsSL -o /tmp/go.tgz "https://go.dev/dl/go${GO_VERSION}.linux-${GOARCH}.tar.gz" && \
    echo "${GO_SHA256}  /tmp/go.tgz" | sha256sum -c - && \
    tar -C /usr/local -xzf /tmp/go.tgz && rm -f /tmp/go.tgz && \
    curl -fsSL -o /tmp/oc.tgz "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/${OCP_VERSION}/openshift-client-linux${OCARCH}.tar.gz" && \
    echo "${OC_SHA256}  /tmp/oc.tgz" | sha256sum -c - && \
    tar -C /usr/local/bin -xzf /tmp/oc.tgz oc kubectl && rm -f /tmp/oc.tgz

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
