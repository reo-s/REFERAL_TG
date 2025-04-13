from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command

# from dotenv import load_dotenv
from config import API_TOKEN, ADMIN_ID

import os
import json
import asyncio

DB_PATH = "ref_db.json"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

bonuses = {
    "levels": [1, 3, 5, 10],
    "links": {
        1: "https://disk.yandex.ru/i/1EIIjw3htWkWXw",
        3: "https://disk.yandex.ru/i/N5S6eYQBgfyn5Q",
        5: "https://disk.yandex.ru/d/_WqG8_kiFYUpYw"
    }
}

# === Работа с базой ===
def load_db():
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "r") as f:
            return json.load(f)
    return {}

def save_db(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)


# === /start ===
@dp.message(Command("start"))
async def handle_start(message: types.Message):
    db = load_db()
    user_id = str(message.from_user.id)
    username = message.from_user.username or "без_username"

    ref_id = message.text.split(" ")[1] if len(message.text.split(" ")) > 1 else None

    # If user get transfered by smns' ref-link
    if ref_id and ref_id != user_id:
        ref_data = db.get(ref_id, {
            "invited_users": [],
            "bonuses_sent": [],

            "username": "неизвестно"
        })

        # If user is invited in first time
        if user_id not in ref_data["invited_users"]:
            ref_data["invited_users"].append(user_id)
            db[ref_id] = ref_data

            # Bonuses check
            await check_bonus(
                ref_id,
                ref_data.get("username", "неизвестно"),

                len(ref_data["invited_users"]),
                db
            )

    # User save (if he's not in data)
    if user_id not in db:
        db[user_id] = {
            "invited_users": [],
            "bonuses_sent": [],
            "username": username
        }
    else:
        db[user_id]["username"] = username  # Update user if smt changed

    save_db(db)

    # Ref-link sending
    bot_username = (await bot.get_me()).username
    await message.answer(
        f"👋 Привет! Вот твоя реферальная ссылка:\n"
        f"https://t.me/{bot_username}?start={user_id}"
    )

# === Проверка бонусов ===
async def check_bonus(ref_id: str, ref_username: str, invited_count: int, db: dict):
    ref_data = db.get(ref_id, {
        "invited_users": [],
        "bonuses_sent": [],
        "username": "неизвестно"
    })

    for level in bonuses["levels"]:
        if invited_count >= level and level not in ref_data["bonuses_sent"]:
            ref_data["bonuses_sent"].append(level)

            # Link -> send
            if level in bonuses["links"]:
                await bot.send_message(
                    ref_id,
                    f"🎁 Вы получили бонус за {level} приглашённых!\nВот ваша ссылка:\n{bonuses['links'][level]}"
                )

            # 🎉 За 10 — только уведомление
            elif level == 10:
                await bot.send_message(
                    ADMIN_ID,
                    f"🎉 Пользователь @{ref_username} (ID: {ref_id}) пригласил 10 человек!"
                )

    db[ref_id] = ref_data

    with open("ref_db.json", "w") as f:
        json.dump(db, f, indent=2)

# === /myrefs ===
@dp.message(Command("myrefs"))
async def handle_myrefs(message: types.Message):
    with open("ref_db.json", "r") as f:
        db = json.load(f)

    user_id = str(message.from_user.id)

    if user_id not in db or not db[user_id]["invited_users"]:
        await message.answer("Вы пока никого не пригласили.")
        return

    invited_ids = db[user_id]["invited_users"]
    result = f"Вы пригласили {len(invited_ids)} человек(а):\n\n"

    for uid in invited_ids:
        # Updating the inviteds' username in real time
        try:
            user = await bot.get_chat(int(uid))
            updated_username = user.username or "без_username"
        except Exception:
            updated_username = "недоступен"

        # Saving new username
        if uid not in db:
            db[uid] = {
                "invited_users": [],
                "bonuses_sent": [],
                "username": updated_username
            }
        else:
            db[uid]["username"] = updated_username

        # Final line
        name_display = f"@{updated_username}" if updated_username != "без_username" else "пользователь"
        mention = f"<a href='tg://user?id={uid}'>{name_display}</a> (ID: {uid})"
        result += f"— {mention}\n"

    # Saving data
    with open("ref_db.json", "w") as f:
        json.dump(db, f, indent=2)

    await message.answer(result, parse_mode="HTML")

# === /allrefs ===
@dp.message(Command("allrefs"))
async def handle_allrefs(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Эта команда только для администратора.")
        return

    # Data loading
    with open("ref_db.json", "r") as f:
        db = json.load(f)

    result = "👥 Список активных рефералов:\n\n"
    found = False

    for user_id, user_data in db.items():
        if not user_id.isdigit():
            continue

        invited = user_data.get("invited_users", [])
        username = user_data.get("username", "пользователь")

        if invited:
            found = True
            name_display = f"@{username}" if username != "без_username" else "пользователь"
            mention = f"<a href='tg://user?id={user_id}'>{name_display}</a>"
            result += f"— {mention} (ID: {user_id}) — пригласил: {len(invited)} чел.\n"

    if not found:
        result = "❌ Пока никто никого не пригласил."

    await message.answer(result, parse_mode="HTML")

# === Запуск бота ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
