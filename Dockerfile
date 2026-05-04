FROM nousresearch/hermes-agent:latest

# Hermes CLI lives in its own venv inside the image; put it on PATH.
ENV PATH="/opt/hermes/.venv/bin:$PATH"

# Install Docker CLI so the orchestrator can spawn sub-agent containers
# via the mounted host socket (/var/run/docker.sock).
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends docker.io && \
    rm -rf /var/lib/apt/lists/*

# Bake orchestrator tools and skills into the image.
# entrypoint.sh syncs these into /opt/data (the profile volume) on every start
# using cp -n so user customizations are never overwritten.
COPY tools/  /opt/hermes-builtin/tools/
COPY skills/ /opt/hermes-builtin/skills/

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["setup"]
