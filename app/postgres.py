import asyncpg
import os
from typing import Any, List, Optional, Union

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("POSTGRES_URL")

class POSTGRES:
    _pool: Optional[asyncpg.pool.Pool] = None

    @classmethod
    async def init(cls):
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(dsn=DATABASE_URL)
    
    @classmethod
    async def close(cls):
        if cls._pool:
            await cls._pool.close()

    @classmethod
    async def fetch_val(cls, query: str, args: Union[List[Any], tuple] = ()):
        await cls.init()
        async with cls._pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    @classmethod
    async def fetch_one(cls, query: str, args: Union[List[Any], tuple] = ()):
        await cls.init()
        async with cls._pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    @classmethod
    async def fetch_all(cls, query: str, args: Union[List[Any], tuple] = ()):
        await cls.init()
        async with cls._pool.acquire() as conn:
            return await conn.fetch(query, *args)

    @classmethod
    async def execute(cls, query: str, args: Union[List[Any], tuple] = ()):
        await cls.init()
        async with cls._pool.acquire() as conn:
            return await conn.execute(query, *args)

    @classmethod
    async def execute_transaction_with_results(cls, queries: List[tuple]):
        """
        Run multiple queries in a transaction.
        Each query: (query_str, args, return_result=False|True)
        
        Returns a list of results (in order), with None for non-returning queries.
        """
        await cls.init()
        async with cls._pool.acquire() as conn:
            async with conn.transaction():
                results = []
                for query, args, return_result in queries:
                    if return_result:
                        result = await conn.fetchrow(query, *args)
                        results.append(result)
                    else:
                        await conn.execute(query, *args)
                        results.append(None)
                return results
