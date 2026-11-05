# A focused Ubuntu image avoids unrelated package repositories and toolchains.
FROM mcr.microsoft.com/devcontainers/base:noble

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER root

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       build-essential ca-certificates clang cmake curl git libclang-dev \
       libssl-dev pkg-config protobuf-compiler python3 python3-venv time \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install as the same non-root user used by the Codespaces terminal.
USER vscode
ENV PATH="/home/vscode/.cargo/bin:${PATH}"

# Keep the toolchain version and components in one authoritative file.
COPY rust-toolchain.toml /tmp/iink-rust-toolchain.toml
COPY .devcontainer/install-rust.py /tmp/iink-install-rust.py

RUN curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs -o /tmp/iink-rustup-init.sh \
    && sh /tmp/iink-rustup-init.sh -y --no-modify-path --profile minimal --default-toolchain none \
    && python3 /tmp/iink-install-rust.py /tmp/iink-rust-toolchain.toml \
    && rustup --version \
    && rustc --version \
    && cargo --version \
    && protoc --version
