from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated
from aiogram import F
from config import API_TOKEN, ADMIN_ID
from db import create_pool, setup_db, save_user, add_bonus, get_user_refs, get_all_referrers

import asyncio

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
pool = None

bonuses = {
    "levels": [1, 3, 5, 10],
    "links": {
        1: "https://disk.yandex.ru/i/1EIIjw3htWkWXw",
        3: "https://disk.yandex.ru/i/N5S6eYQBgfyn5Q",
        5: "https://disk.yandex.ru/d/_WqG8_kiFYUpYw"
    }
}

CHANNEL_ID = -1001182955252
CHANNEL_LINK = "https://t.me/fleshkatrenera"


@dp.message(Command("start"))
async def handle_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "без_username"

    args = message.text.split()
    ref_id = None

    # если есть рефка
    if len(args) > 1 and args[1].isdigit():
        ref_id_candidate = int(args[1])
        if ref_id_candidate != user_id:
            ref_id = ref_id_candidate

    # проверка подписки
    try:
        member = await bot.get_chat_member(chat_id="@fleshkatrenera", user_id=user_id)
        if member.status not in ("member", "administrator", "creator"):
            await message.answer("❗ Подпишитесь на канал:\nhttps://t.me/fleshkatrenera\n\nЗатем снова нажмите /start")
            return
    except Exception:
        await message.answer("⚠️ Ошибка при проверке подписки. Повторите позже.")
        return

    # сохраняем пользователя (всё делается внутри save_user)
    await save_user(pool, user_id, username, ref_id)

    # пробуем начислить бонус
    if ref_id:
        invited_users = await get_user_refs(pool, ref_id)
        invited_count = len(invited_users)

        ref_user = await bot.get_chat(ref_id)
        ref_username = ref_user.username or "без_username"

        await check_bonus(ref_id, ref_username, invited_count)

    await message.answer(
        "🎉 Вы успешно зарегистрированы!\n"
        "📢 Канал: https://t.me/fleshkatrenera\n"
        "🔗 Ваша ссылка: /invite"
    )


@dp.message(Command("myrefs"))
async def handle_myrefs(message: types.Message):
    user_id = message.from_user.id
    invited_users = await get_user_refs(pool, user_id)

    if not invited_users:
        await message.answer("Вы пока никого не пригласили.")
        return

    result = f"Вы пригласили {len(invited_users)} человек(а):\n"
    for uid, uname in invited_users:
        name_display = f"@{uname}" if uname else "пользователь"
        mention = f"<a href='tg://user?id={uid}'>{name_display}</a> (ID: {uid})"
        result += f"— {mention}\n"

    await message.answer(result, parse_mode="HTML")


@dp.message(Command("allrefs"))
async def handle_allrefs(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Эта команда только для администратора.")
        return

    referrers = await get_all_referrers(pool)
    if not referrers:
        await message.answer("❌ Пока никто никого не пригласил.")
        return

    result = "👥 Список активных рефералов:\n"
    for uid, uname, count in referrers:
        name_display = f"@{uname}" if uname else "пользователь"
        mention = f"<a href='tg://user?id={uid}'>{name_display}</a>"
        result += f"— {mention} (ID: {uid}) — пригласил: {count} чел.\n"

    await message.answer(result, parse_mode="HTML")


# async def check_bonus(ref_id: int, ref_username: str, invited_count: int):
#     for level in bonuses["levels"]:
#         if invited_count >= level:
#             granted = await add_bonus(pool, ref_id, level)
#             if granted:
#                 if level in bonuses["links"]:
#                     await bot.send_message(
#                         ref_id,
#                         f"🎁 Вы получили бонус за {level} приглашённых!\n"
#                         f"Вот ваша ссылка: {bonuses['links'][level]}"
#                     )
#                 elif level == 10:
#                     await bot.send_message(
#                         ADMIN_ID,
#                         f"🎉 Пользователь @{ref_username} (ID: {ref_id}) пригласил 10 человек!"
#                     )
async def check_bonus(ref_id: int, ref_username: str, invited_count: int):
    for level in bonuses["levels"]:
        if invited_count >= level:
            granted = await add_bonus(pool, ref_id, level)
            if granted:
                if level in bonuses["links"]:
                    await bot.send_message(
                        ref_id,
                        f"🎁 Вы получили бонус за {level} приглашённых!\n"
                        f"Вот ваша ссылка: {bonuses['links'][level]}"
                    )
                elif level == 10:
                    await bot.send_message(
                        ADMIN_ID,
                        f"🎉 Пользователь @{ref_username} (ID: {ref_id}) пригласил 10 человек!"
                    )


async def main():
    global pool
    pool = await create_pool()
    await setup_db(pool)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
