# AWS Secrets Manager agent sidecar.
# Builds the upstream agent from the pinned release tag.

FROM rust:alpine AS builder

ARG AWS_SECRETSMANAGER_AGENT_VERSION=v2.0.0

RUN apk add --no-cache build-base ca-certificates git
RUN update-ca-certificates

WORKDIR /app

RUN git clone --depth 1 --branch "${AWS_SECRETSMANAGER_AGENT_VERSION}" \
    https://github.com/aws/aws-secretsmanager-agent.git .
RUN cargo build --release -p aws_secretsmanager_agent

FROM scratch

WORKDIR /app

COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /app/target/release/aws_secretsmanager_agent .

ENTRYPOINT ["./aws_secretsmanager_agent"]
