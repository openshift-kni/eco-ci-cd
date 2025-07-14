FROM registry.access.redhat.com/ubi9/ubi

WORKDIR /eco-ci-cd

# Install required packages
RUN dnf -y install --setopt=install_weak_deps=False --setopt=tsdocs=False \
    git \
    sshpass \
    python3 \
    python3-pip \
    python3-wheel \
    python3-setuptools \
    && dnf clean all

# Copy application files to eco-ci-cd folder
COPY . .

# Update pip, wheel, etc.
RUN python3 -m pip \
        install \
            --no-cache-dir \
            --upgrade \
            pip \
            wheel \
            setuptools

# Install ansible and ansible-lint
RUN python3 -m pip \
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
RUN ansible-galaxy collection install -r requirements.yml

# Set entrypoint to bash
ENTRYPOINT ["/bin/bash"]
