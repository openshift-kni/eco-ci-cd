FROM registry.access.redhat.com/ubi9/ubi:latest

ARG GIT_URL
ARG GIT_BRANCH
ARG GIT_COMMIT
ARG GIT_TAG

LABEL org.opencontainers.image.authors="Telcov10n CI/CD Team"
LABEL org.opencontainers.image.description="ECO CI/CD"
LABEL org.opencontainers.image.documentation="${GIT_URL}/tree/main"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source.branch="${GIT_BRANCH}"
LABEL org.opencontainers.image.source.commit="${GIT_COMMIT}"
LABEL org.opencontainers.image.source.tag="${GIT_TAG}"
LABEL org.opencontainers.image.source="${GIT_URL}.git"
LABEL org.opencontainers.image.title="ECO CI/CD"
LABEL org.opencontainers.image.url="${GIT_URL}/tree/main"
LABEL org.opencontainers.image.vendor="Telcov10n CI/CD Team"
LABEL org.opencontainers.image.version="${GIT_TAG}"

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
            -r requirements-base.txt

# Install ansible and ansible-lint
RUN python3.11 -m pip \
        install \
            --no-cache-dir \
            -r requirements-container.txt \

# Install requirements
RUN ansible-galaxy collection install --force -r requirements.yml

# Set entrypoint to bash
ENTRYPOINT ["/bin/bash"]
