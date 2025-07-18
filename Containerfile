FROM registry.access.redhat.com/ubi9/ubi:latest

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
