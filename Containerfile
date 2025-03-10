FROM registry.access.redhat.com/ubi9/ubi

# Install required packages
RUN dnf -y install \
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
    jmespath

# Copy application files to eco-ci-cd folder
COPY . ./eco-ci-cd

WORKDIR /eco-ci-cd

# Install requirements
RUN ansible-galaxy collection install -r requirements.yml

# Set entrypoint to bash
ENTRYPOINT ["/bin/bash"]
