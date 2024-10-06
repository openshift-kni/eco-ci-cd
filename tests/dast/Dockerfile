FROM golang:1.21

# Copy the repository files
COPY . /tmp/telco-dast-qe

WORKDIR /tmp

# Set the Go path and Go cache environment variables
ENV GOPATH=/tmp/go
ENV GOBIN=/tmp/go/bin
ENV GOCACHE=/tmp/.cache/go-build
ENV PATH=$PATH:$GOBIN

# Create the /tmp/go/bin and build cache directories, and grant read and write permissions to all users
RUN mkdir -p /tmp/go/bin $GOCACHE \
    && chmod -R 777 /tmp/go/bin $GOPATH $GOCACHE

# Install dependencies required by test cases and debugging
RUN apt-get update && apt-get install -y jq vim libreadline-dev podman

# Install Chainsaw e2e testing tool
RUN go install github.com/kyverno/chainsaw@v0.2.0

# Install kubectl and oc
RUN curl -LO https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/latest/openshift-client-linux.tar.gz \
    && tar -xzf openshift-client-linux.tar.gz \
    && chmod +x oc kubectl \
    && mv oc kubectl /usr/local/bin/

# Set the working directory
WORKDIR /tmp/telco-dast-qe

#Set podman permissions and create .local folder
RUN mkdir -p /.local \
    && useradd podman \
    && chown podman:podman -R /.local \
    && chmod 777 /.local
USER podman