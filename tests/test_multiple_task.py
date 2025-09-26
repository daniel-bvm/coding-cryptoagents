import asyncio
import httpx
import uuid

timeout = httpx.Timeout(60.0 * 1000, connect=10.0)

async def run_task(task: str):
    payload = {
        "messages": [{"role": "user", "content": task}],
        "id": str(uuid.uuid4()),
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post("http://localhost:80/prompt", json=payload)
        return response.json()


async def test_multiple_task():
    tasks = [
        "Explain about entropy",
        "How did people clip their fingernails 1000 years ago?",
        "Tell me everything about eternalai.org",
        "What is ERC8004?",
        "Explain the paper: https://arxiv.org/pdf/1706.03762"
    ]

    task_results = await asyncio.gather(
        *[run_task(task) for task in tasks]
    )

    for task, result in zip(tasks, task_results):
        print(f"Task: {task}")
        print(f"Result: {result}")
        print("-" * 100)

if __name__ == "__main__":
    asyncio.run(test_multiple_task())