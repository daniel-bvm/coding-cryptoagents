from golang:1.24-alpine as builder
run apk add --no-cache git ca-certificates
workdir /src
run git clone --depth 1 https://github.com/vinkent420/opencode-agent-local-ai.git
run cd opencode-agent-local-ai && go build -o /bin/opencode .

from python:3.12-slim

run apt-get update \
    && apt-get install -y gnupg curl wget sudo build-essential cmake git libjson-c-dev libwebsockets-dev net-tools jq ripgrep fzf tmux xclip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

run git clone https://github.com/tsl0922/ttyd.git \
    && cd ttyd \
    && mkdir build \
    && cd build \
    && cmake .. \
    && make \
    && make install
    
copy requirements.txt requirements.txt
run pip install -r requirements.txt

copy --from=builder /bin/opencode /bin/opencode
run chmod +x /bin/opencode

workdir /workspace
copy main.py main.py
copy agent agent
copy .tmux.conf .tmux.conf

expose 7681

cmd ["python", "main.py"]