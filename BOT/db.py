import os
import asyncpg

async def create_pool():
    DATABASE_URL = os.environ["DATABASE_URL"]
    return await asyncpg.create_pool(dsn=DATABASE_URL)

async def setup_db(pool):
    async with pool.acquire() as conn:
        # Таблица пользователей
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                invited_by BIGINT,
                bonuses_sent INTEGER[]
            );
        """)
        # Таблица персональных ссылок
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS invite_links (
                invite_link TEXT PRIMARY KEY,
                inviter_id BIGINT NOT NULL
            );
        """)

async def save_user(pool, user_id: int, username: str, invited_by: int = None):
    async with pool.acquire() as conn:
        # Вставляем или обновляем username, invited_by записываем только если пусто
        await conn.execute(
            """
            INSERT INTO users (user_id, username, invited_by, bonuses_sent)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE SET
              username = EXCLUDED.username
            """,
            user_id, username, invited_by, []
        )
        if invited_by is not None:
            await conn.execute(
                "UPDATE users SET invited_by = $1 WHERE user_id = $2 AND invited_by IS NULL",
                invited_by, user_id
            )

async def save_invite_link(pool, link: str, inviter_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO invite_links (invite_link, inviter_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            link, inviter_id
        )

async def get_user_refs(pool, ref_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, username FROM users WHERE invited_by = $1", ref_id
        )
        return [(r["user_id"], r["username"]) for r in rows]

async def get_all_referrers(pool):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.user_id, u.username, COUNT(i.user_id) AS count
            FROM users u
            LEFT JOIN users i ON i.invited_by = u.user_id
            GROUP BY u.user_id, u.username
            HAVING COUNT(i.user_id) > 0
            ORDER BY count DESC
        """)
        return [(r["user_id"], r["username"], r["count"]) for r in rows]

async def add_bonus(pool, user_id: int, level: int) -> bool:
    async with pool.acquire() as conn:
        current = await conn.fetchval(
            "SELECT bonuses_sent FROM users WHERE user_id = $1", user_id
        )
        if current is None:
            current = []
        if level in current:
            return False
        current.append(level)
        await conn.execute(
            "UPDATE users SET bonuses_sent = $1 WHERE user_id = $2",
            current, user_id
        )
        return True

async def get_inviter_by_link(pool, link: str) -> int | None:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT inviter_id FROM invite_links WHERE invite_link = $1", link
        )
