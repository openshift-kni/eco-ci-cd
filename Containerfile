FROM registry.access.redhat.com/ubi9/ubi:latest

LABEL org.opencontainers.image.authors="Telcov10n CI/CD Team"
LABEL org.opencontainers.image.description="ECO CI/CD"
LABEL org.opencontainers.image.documentation="https://github.com/telcov10n/eco-ci-cd/tree/main"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/telcov10n/eco-ci-cd"
LABEL org.opencontainers.image.title="ECO CI/CD"
LABEL org.opencontainers.image.url="https://github.com/telcov10n/eco-ci-cd/tree/main"
LABEL org.opencontainers.image.vendor="Telcov10n CI/CD Team"

WORKDIR /eco-ci-cd

# Install required packages
RUN dnf -y install --setopt=install_weak_deps=False --setopt=tsdocs=False \
    git \
    sshpass \
    python3.11 \
    python3.11-pip \
    python3.11-wheel \
    python3.11-setuptools \
    && dnf clean all

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 2

# Copy application files to eco-ci-cd folder
COPY . .


# Update pip, wheel, etc.
RUN python3.11 -m pip \
        install \
            --no-cache-dir \
            --upgrade \
                pip \
                wheel \
                setuptools

# Install ansible and ansible-lint
RUN python3.11 -m pip \
        install \
            --no-cache-dir \
                ansible \
                ansible-lint \
                jira \
                jmespath \
                junitparser \
                lxml \
                ncclient \
                netaddr \
                paramiko \
                requests

# Install requirements
RUN ansible-galaxy collection install --force -r requirements.yml

# Set entrypoint to bash
ENTRYPOINT ["/bin/bash"]
