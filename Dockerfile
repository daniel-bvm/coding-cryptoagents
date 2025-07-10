FROM golang:1.24-alpine AS builder
RUN apk add --no-cache git ca-certificates
WORKDIR /src
RUN git clone --depth 1 https://github.com/vinkent420/opencode-agent-local-ai.git
RUN cd opencode-agent-local-ai && go build -o /bin/opencode .

from python:3.12-slim

run apt-get update \
    && apt-get install -y gnupg curl wget sudo build-essential cmake git libjson-c-dev libwebsockets-dev net-tools jq ripgrep fzf \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

run git clone https://github.com/tsl0922/ttyd.git \
    && cd ttyd \
    && mkdir build \
    && cd build \
    && cmake .. \
    && make \
    && make install

copy --from=builder /bin/opencode /bin/opencode
run chmod +x /bin/opencode

copy requirements.txt requirements.txt

run pip install -r requirements.txt

workdir /workspace
copy main.py main.py
copy agent agent
expose 7681


cmd ["python", "main.py"]