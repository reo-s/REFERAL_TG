import os
import asyncpg

async def create_pool():
    database_url = os.environ["DATABASE_URL"]  # из Railway переменной
    return await asyncpg.create_pool(dsn=database_url)

async def setup_db(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                invited_by BIGINT,
                bonuses_sent INTEGER[]
            )
        """)

async def save_user(pool, user_id: int, username: str, invited_by: int = None):
    async with pool.acquire() as conn:
        # вставка если нового нет
        await conn.execute(
            """
            INSERT INTO users (user_id, username, invited_by, bonuses_sent)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username
            """,
            user_id, username, invited_by, []
        )

        # если invited_by передан, но не установлен — установим
        if invited_by is not None:
            await conn.execute(
                "UPDATE users SET invited_by = $1 WHERE user_id = $2 AND invited_by IS NULL",
                invited_by, user_id
            )

async def get_user_refs(pool, user_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, username FROM users WHERE invited_by = $1", user_id
        )
        return [(r["user_id"], r["username"]) for r in rows]

async def get_all_referrers(pool):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT invited_by, COUNT(*) AS count, u.username FROM users "
            "JOIN users u ON u.user_id = invited_by "
            "GROUP BY invited_by, u.username"
        )
        return [(r["invited_by"], r["username"], r["count"]) for r in rows]

async def add_bonus(pool, user_id: int, level: int) -> bool:
    async with pool.acquire() as conn:
        bonuses = await conn.fetchval("SELECT bonuses_sent FROM users WHERE user_id = $1", user_id)
        if bonuses is None:
            bonuses = []

        if level in bonuses:
            return False

        bonuses.append(level)
        await conn.execute("UPDATE users SET bonuses_sent = $1 WHERE user_id = $2", bonuses, user_id)
        return True
