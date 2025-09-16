from danieltn11/opencode:1.0.8

# env LLM_MODEL_ID=z-ai/glm-4.5-air
# env LLM_MODEL_ID_CODE=qwen/qwen3-coder

env LLM_MODEL_ID=zai-org/GLM-4.5-Air-FP8
env LLM_MODEL_ID_CODE=zai-org/GLM-4.5-Air-FP8
env LLM_API_KEY=supersecret

env PROXY_SCOPE="*api.tavily.com*,*api.search.brave.com*,*api.exa.ai*,*imagine-backend.bvm.network*"

workdir /workspace
copy main.py main.py
copy agent agent
copy mcps mcps
copy public public

expose 12345
cmd ["python", "main.py"]
