from danieltn11/opencode:1.0.6

# env LLM_MODEL_ID=z-ai/glm-4.5-air
# env LLM_MODEL_ID_CODE=qwen/qwen3-coder

env LLM_MODEL_ID=zai-org/GLM-4.5-Air-FP8
env LLM_MODEL_ID_CODE=zai-org/GLM-4.5-Air-FP8

env LLM_BASE_URL=http://localhost:65534/v1
env LLM_API_KEY=supersecret

workdir /workspace
copy main.py main.py
copy agent agent
copy mcps mcps
copy public public

expose 12345
cmd ["python", "main.py"]
