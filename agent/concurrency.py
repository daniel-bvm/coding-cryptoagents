from typing import Callable, Generator, AsyncGenerator
import asyncio
from functools import partial, wraps
from starlette.concurrency import run_in_threadpool

def sync2async(sync_func: Callable):
    async def async_func(*args, **kwargs):
        res = run_in_threadpool(partial(sync_func, *args, **kwargs))

        if isinstance(res, (Generator, AsyncGenerator)):
            return res

        return await res

    return async_func if not asyncio.iscoroutinefunction(sync_func) else sync_func


def limit_asyncio_concurrency(num_of_concurrent_calls: int):
    semaphore = asyncio.Semaphore(num_of_concurrent_calls)

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with semaphore:
                res = func(*args, **kwargs)

                if isinstance(res, (Generator, AsyncGenerator)):
                    return res

                return await res

        return wrapper
    return decorator

def batching(gen: Generator, batch_size: int = 1):
    batch = []

    for item in gen:
        batch.append(item)
        if len(batch) == batch_size:
            yield batch
            batch = []

    if batch:
        yield batch
        
async def batching_async(gen: AsyncGenerator, batch_size: int = 1):
    batch = []

    async for item in gen:
        batch.append(item)
        if len(batch) == batch_size:
            yield batch
            batch = []

    if batch:
        yield batch