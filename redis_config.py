from contextlib import asynccontextmanager
import os
import redis.asyncio as redis
from fastapi import FastAPI
from database import Base, engine
from dotenv import load_dotenv

load_dotenv()

REDIS_CONNECT = os.getenv("RED_URL")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = redis.from_url(REDIS_CONNECT, decode_responses=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await app.state.redis.close()
