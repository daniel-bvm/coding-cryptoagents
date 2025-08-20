from danieltn11/opencode:1.0.2

env LLM_MODEL_ID=zai-org/GLM-4.5-Air-FP8
env LLM_MODEL_ID_CODE=z-ai/glm-4.5
env LLM_BASE_URL=http://localhost:65534/v1
env LLM_API_KEY=supersecret

workdir /workspace
copy main.py main.py
copy agent agent
copy mcps mcps

cmd ["python", "main.py"]