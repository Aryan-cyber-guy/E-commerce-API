"""Shared Redis client for caching and rate limiting."""

from redis import Redis
from dotenv import load_dotenv
import os

load_dotenv()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
