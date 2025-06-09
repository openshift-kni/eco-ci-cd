FROM registry.access.redhat.com/ubi9/ubi

WORKDIR /eco-ci-cd

# Install required packages
RUN dnf -y install --setopt=install_weak_deps=False --setopt=tsdocs=False \
    git \
    sshpass \
    python3 \
    python3-pip \
    && dnf clean all

# Install ansible and ansible-lint
RUN pip3 install --no-cache-dir \
    ansible \
    ansible-lint \
    netaddr \
    jmespath \
    paramiko \
    ncclient \
    requests \
    jira \
    junitparser

# Copy application files to eco-ci-cd folder
COPY . .
# Install requirements
RUN ansible-galaxy collection install -r requirements.yml

# Set entrypoint to bash
ENTRYPOINT ["/bin/bash"]
