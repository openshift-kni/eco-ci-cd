FROM registry.access.redhat.com/ubi9/python-312-minimal 

WORKDIR /eco-ci-cd

USER root
# Install required packages
RUN microdnf update && \
    microdnf -y install \
    git \
    sshpass \
    && microdnf clean all

# Copy python requirements file to /eco-ci-cd
COPY pip.txt .
# Install python dependencies
RUN python3 -m pip install --prefer-binary --no-cache-dir --no-compile --use-pep517 -r pip.txt

# Copy files affecting ansible-galaxy to /eco-ci-cd
COPY requirements.yml ansible.cfg /eco-ci-cd/
# Install galaxy requirements
RUN ansible-galaxy collection install --no-cache --pre -r requirements.yml

USER 1001
# Copy application files to eco-ci-cd folder
COPY . .

# Set entrypoint to bash
ENTRYPOINT ["/bin/bash"]
