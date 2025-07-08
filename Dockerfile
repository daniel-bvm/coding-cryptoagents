from python:3.12-slim

run apt-get update \
    && apt-get install -y nodejs npm gnupg curl npm wget sudo build-essential cmake git libjson-c-dev libwebsockets-dev net-tools lolcat cowsay jq \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

run git clone https://github.com/tsl0922/ttyd.git \
    && cd ttyd \
    && mkdir build \
    && cd build \
    && cmake .. \
    && make \
    && make install

run npm install -g @openai/codex
copy requirements.txt requirements.txt
run pip install -r requirements.txt

copy main.py main.py
copy agent agent
expose 7681

env LLM_API_KEY="just-a-value-to-by-pass-validation"

cmd ["python", "main.py"]