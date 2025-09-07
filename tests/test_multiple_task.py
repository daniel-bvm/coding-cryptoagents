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
        "Create a slides about Ado discography",
        "Create a slides to compare between 9lana and Ado",
        "Create a slides to report the results of 2025 ICPC World Finals, have a section dedicated to Vietnamese teams.",
        "Create a slides to compare between marijuana and tobacco",
        "Create a slides to report latest trends in AI",
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