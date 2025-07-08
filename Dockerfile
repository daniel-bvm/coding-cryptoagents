from golang:1.24-alpine as builder

run go install github.com/opencode-ai/opencode@latest

from python:3.12-slim

run apt-get update \
    && apt-get install -y gnupg curl npm wget sudo build-essential cmake git libjson-c-dev libwebsockets-dev net-tools lolcat cowsay jq ripgrep fzf \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

run git clone https://github.com/tsl0922/ttyd.git \
    && cd ttyd \
    && mkdir build \
    && cd build \
    && cmake .. \
    && make \
    && make install

copy --from=builder /go/bin/opencode /bin/opencode

copy requirements.txt requirements.txt
run pip install -r requirements.txt

workdir /workspace
copy main.py main.py
copy agent agent
expose 7681

env LLM_API_KEY="just-a-value-to-by-pass-validation"
env OPENAI_API_KEY="just-a-value-to-by-pass-validation"

cmd ["python", "main.py"]