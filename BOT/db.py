import os
import asyncpg

async def create_pool():
    DATABASE_URL = os.environ["DATABASE_URL"]
    return await asyncpg.create_pool(dsn=DATABASE_URL)

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

async def save_user(pool, user_id: int, username: str, invited_by: int = None):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, username, invited_by, bonuses_sent)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE
              SET username = EXCLUDED.username
            """,
            user_id, username, invited_by, []
        )
        # если впервые пришёл с рефом — установим invited_by
        if invited_by is not None:
            await conn.execute(
                "UPDATE users SET invited_by = $1 WHERE user_id = $2 AND invited_by IS NULL",
                invited_by, user_id
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
        # Получаем текущее значение
        row = await conn.fetchrow(
            "SELECT bonuses_sent FROM users WHERE user_id = $1", user_id
        )
        bonuses = row["bonuses_sent"] or []

        # Если уже есть — выходим
        if level in bonuses:
            return False

        # Добавляем и сохраняем
        bonuses.append(level)
        await conn.execute(
            "UPDATE users SET bonuses_sent = $1 WHERE user_id = $2",
            bonuses, user_id
        )
        # Для отладки: убедимся, что в БД теперь массив с добавленным уровнем
        new_row = await conn.fetchrow(
            "SELECT bonuses_sent FROM users WHERE user_id = $1", user_id
        )
        print(f"[add_bonus] user={user_id} levels before append, after append: {row['bonuses_sent']} → {new_row['bonuses_sent']}")
        return True

async def get_inviter(pool, user_id: int) -> int | None:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT invited_by FROM users WHERE user_id = $1", user_id
        )
