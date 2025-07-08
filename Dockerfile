from python:3.12-slim

run curl -fsSL https://deb.nodesource.com/setup_23.x | bash - \
    && apt-get update \
    && apt-get install -y nodejs npm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

run npm install -g @anthropic-ai/claude-code
copy requirements.txt requirements.txt
run pip install -r requirements.txt
copy main.py main.py
copy agent agent

cmd ["uvicorn", "main"]