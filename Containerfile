FROM registry.access.redhat.com/ubi9/ubi

WORKDIR /eco-ci-cd

# Install required packages
RUN dnf -y install --setopt=install_weak_deps=False --setopt=tsdocs=False \
    git \
    sshpass \
    python3 \
    python3-pip \
    && dnf clean all

# Copy python requirements file to eco-ci-cd folder
COPY pip.txt .

# Install python dependencies
RUN pip3 install --no-cache-dir -r pip.txt

# Copy galaxy requirements file to eco-ci-cd folder
COPY requirements.yml .

# Install ansible collections
# Install galaxy requirements
RUN ansible-galaxy collection install -r requirements.yml

COPY . .

# Set entrypoint to bash
ENTRYPOINT ["/bin/bash"]
