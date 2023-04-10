FROM mambaorg/micromamba:1.3.1-bullseye-slim
LABEL MAINTAINER="Kyle Wilcox <kyle@axds.co>"

ENV DEBIAN_FRONTEND noninteractive
ENV LANG C.UTF-8

USER root

RUN apt-get update && apt-get install -y \
        git \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

USER $MAMBA_USER

#COPY --chown environment variables only work in recent versions of Docker (May 2019)
#https://github.com/moby/moby/issues/35018#issuecomment-486774627
COPY --chown=mambauser:mambauser reqs/base.yml /tmp/base.yml
COPY --chown=mambauser:mambauser reqs/dev.yml /tmp/dev.yml
RUN micromamba install --name base --yes --file /tmp/base.yml && \
    micromamba install --name base --yes --file /tmp/dev.yml && \
    micromamba clean --all --yes

ARG MAMBA_DOCKERFILE_ACTIVATE=1
ENV PATH "$MAMBA_ROOT_PREFIX/bin:$PATH"
ENV PROMETHEUS_MULTIPROC_DIR /tmp/metrics

# Copy packrat contents and install
ENV XPUB_HOME /xpd
WORKDIR $XPUB_HOME
COPY --chown=mambauser:mambauser . $XPUB_HOME/

ARG PSEUDO_VERSION=1
RUN SETUPTOOLS_SCM_PRETEND_VERSION=${PSEUDO_VERSION} pip install -e . && \
    mkdir -p ${PROMETHEUS_MULTIPROC_DIR}

ENV XPUB_CONFIG_FILE ${XPUB_HOME}/config.yaml
ENV XPUB_ENV_FILES ${XPUB_HOME}/.env

EXPOSE 9000

CMD ["gunicorn", "xpublish_host.app:app", "--config", "xpublish_host/gunicorn.conf.py"]
