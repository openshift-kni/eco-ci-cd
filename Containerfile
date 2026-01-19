FROM registry.access.redhat.com/ubi9/ubi

WORKDIR /eco-ci-cd

# https://docs.ansible.com/projects/ansible/latest/reference_appendices/config.html#envvar-ANSIBLE_ALLOW_BROKEN_CONDITIONALS
ENV ANSIBLE_ALLOW_BROKEN_CONDITIONALS=True

# Install required packages
RUN dnf -y install --setopt=install_weak_deps=False --setopt=tsdocs=False \
    git \
    sshpass \
    python3 \
    python3-pip \
    python3-devel \
    python3-wheel \
    && dnf clean all

# Copy python requirements file to /eco-ci-cd
COPY pip.txt .
# Install python dependencies
RUN python3 -m pip install --no-cache-dir -r pip.txt && \
    python3 -m pip cache purge

# Copy files affecting ansible-galaxy to /eco-ci-cd
COPY requirements.yml ansible.cfg /eco-ci-cd/
# Install galaxy requirements
RUN ansible-galaxy collection install --no-cache --pre -r requirements.yml

# Copy application files to eco-ci-cd folder
COPY . .

# Set entrypoint to bash
ENTRYPOINT ["/bin/bash"]
