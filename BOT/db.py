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
        # Попытка прочитать строку пользователя
        row = await conn.fetchrow(
            "SELECT bonuses_sent FROM users WHERE user_id = $1", user_id
        )
        print(f"[add_bonus] fetched row for user={user_id}: {row!r}")

        # Если пользователя нет в таблице — прекращаем
        if row is None:
            print(f"[add_bonus] user {user_id} not found → abort")
            return False

        # Извлекаем текущий массив бонусов (или пустой)
        current = row.get("bonuses_sent") or []
        print(f"[add_bonus] current bonuses for user={user_id}: {current}")

        # Если уже есть этот уровень — ничего не делаем
        if level in current:
            print(f"[add_bonus] level={level} already granted → abort")
            return False

        # Добавляем новый уровень и сохраняем
        new_list = current + [level]
        print(f"[add_bonus] updating bonuses for user={user_id}: {new_list}")
        await conn.execute(
            "UPDATE users SET bonuses_sent = $1 WHERE user_id = $2",
            new_list, user_id
        )

        # Проверяем результат
        row2 = await conn.fetchrow(
            "SELECT bonuses_sent FROM users WHERE user_id = $1", user_id
        )
        print(f"[add_bonus] after update, row2={row2!r}")

        return True

async def get_inviter(pool, user_id: int) -> int | None:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT invited_by FROM users WHERE user_id = $1", user_id
        )
