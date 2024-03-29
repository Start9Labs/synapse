# Dockerfile to build the matrixdotorg/synapse docker images.
#
# To build the image, run `docker build` command from the root of the
# synapse repository:
#
#    docker build -f docker/Dockerfile .
#
# There is an optional PYTHON_VERSION build argument which sets the
# version of python to build against: for example:
#
#    docker build -f docker/Dockerfile --build-arg PYTHON_VERSION=3.6 .
#

ARG PYTHON_VERSION=3.8

###
### Stage: prebuilder
###
### New versions of cryptography require rust to be installed, but due to
### https://bugs.launchpad.net/qemu/+bug/1805913 downloading cargo registries
### and dependencies doesn't work on multiarch builds. We fix this by
### prebuilding `cryptography` first in the native arch, and then copying over
### the registry and running cargo in offline mode.
###
FROM --platform=$BUILDPLATFORM docker.io/python:${PYTHON_VERSION}-slim as prebuilder

RUN apt-get update && apt-get install -y \
        build-essential \
        libffi-dev \
        libssl-dev \
        rustc \
        zlib1g-dev \
        && rm -rf /var/lib/apt/lists/*

RUN mkdir /root/.cargo
ENV CARGO_HOME=/root/.cargo

RUN pip download --no-binary :all: --no-deps cryptography

RUN tar -xf cryptography*.tar.gz --wildcards cryptography*/src/rust/

RUN cd cryptography*/src/rust && cargo fetch

###
### Stage: builder
###
FROM docker.io/python:${PYTHON_VERSION}-slim as builder

LABEL org.opencontainers.image.url='https://matrix.org/docs/projects/server/synapse'
LABEL org.opencontainers.image.documentation='https://github.com/matrix-org/synapse/blob/master/docker/README.md'
LABEL org.opencontainers.image.source='https://github.com/matrix-org/synapse.git'
LABEL org.opencontainers.image.licenses='Apache-2.0'

# install the OS build deps
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libjpeg-dev \
    libpq-dev \
    libssl-dev \
    libwebp-dev \
    libxml++2.6-dev \
    libxslt1-dev \
    openssl \
    rustc \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=prebuilder /root/.cargo /root/.cargo

ENV CARGO_NET_OFFLINE=true
ENV CARGO_HOME=/root/.cargo

RUN pip install --prefix="/install" --no-warn-script-location \
        cryptography

# Copy just what we need to pip install
COPY scripts /synapse/scripts/
COPY MANIFEST.in README.rst setup.py synctl /synapse/
COPY synapse/__init__.py /synapse/synapse/__init__.py
COPY synapse/python_dependencies.py /synapse/synapse/python_dependencies.py

# To speed up rebuilds, install all of the dependencies before we copy over
# the whole synapse project so that we this layer in the Docker cache can be
# used while you develop on the source
#
# This is aiming at installing the `install_requires` and `extras_require` from `setup.py`
RUN pip install --prefix="/install" --no-warn-script-location \
    /synapse[all]

# Copy over the rest of the project
COPY synapse /synapse/synapse/

# Install the synapse package itself and all of its children packages.
#
# This is aiming at installing only the `packages=find_packages(...)` from `setup.py
RUN pip install --prefix="/install" --no-deps --no-warn-script-location /synapse

###
### Stage: runtime
###

FROM docker.io/python:${PYTHON_VERSION}-slim

LABEL org.opencontainers.image.url='https://matrix.org/docs/projects/server/synapse'
LABEL org.opencontainers.image.documentation='https://github.com/matrix-org/synapse/blob/master/docker/README.md'
LABEL org.opencontainers.image.source='https://github.com/matrix-org/synapse.git'
LABEL org.opencontainers.image.licenses='Apache-2.0'

RUN apt-get update && apt-get install -y \
    curl \
    gosu \
    libjpeg62-turbo \
    libpq5 \
    libwebp6 \
    xmlsec1 \
    libjemalloc2 \
    libssl-dev \
    openssl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY ./docker/start.py /start.py
COPY ./docker/conf /conf

VOLUME ["/data"]

EXPOSE 8008/tcp 8009/tcp 8448/tcp

ENTRYPOINT ["/start.py"]

HEALTHCHECK --start-period=5s --interval=15s --timeout=5s \
    CMD curl -fSs http://localhost:8008/health || exit 1
