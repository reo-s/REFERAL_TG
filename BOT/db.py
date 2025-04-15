import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

async def create_pool():
    return await asyncpg.create_pool(DATABASE_URL)

async def setup_db(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                invited_by BIGINT,
                bonuses_sent INTEGER[]
            );
        """)

async def save_user(pool, user_id, username, invited_by=None):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username, invited_by, bonuses_sent)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username;
        """, user_id, username, invited_by, [])

# async def add_bonus(pool, user_id, level):
#     async with pool.acquire() as conn:
#         bonuses = await conn.fetchval("SELECT bonuses_sent FROM users WHERE user_id = $1", user_id)
#         if bonuses and level in bonuses:
#             return False
#         new_bonuses = bonuses + [level] if bonuses else [level]
#         await conn.execute("UPDATE users SET bonuses_sent = $1 WHERE user_id = $2", new_bonuses, user_id)
#         return True
async def add_bonus(pool, user_id: int, level: int) -> bool:
    async with pool.acquire() as conn:
        current = await conn.fetchval("SELECT bonuses_sent FROM users WHERE user_id = $1", user_id)
        
        if current is None:
            current = []

        if level in current:
            return False  # Уже получал бонус за этот уровень

        current.append(level)
        await conn.execute("UPDATE users SET bonuses_sent = $1 WHERE user_id = $2", current, user_id)
        return True

async def get_user_refs(pool, ref_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT user_id, username FROM users
            WHERE invited_by = $1
        """, ref_id)
        return [(row["user_id"], row["username"]) for row in rows]

async def get_all_referrers(pool):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.user_id, u.username, COUNT(r.user_id) AS invited_count
            FROM users u
            JOIN users r ON r.invited_by = u.user_id
            GROUP BY u.user_id, u.username
        """)
        return [(row["user_id"], row["username"], row["invited_count"]) for row in rows]
