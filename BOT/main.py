import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import Command, Text
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import API_TOKEN, ADMIN_ID
from db import (
    create_pool, setup_db,
    save_user, get_user_refs,
    add_bonus, get_inviter, get_all_referrers
)

bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
pool = None

CHANNEL_ID   = -1001182955252
CHANNEL_URL  = "https://t.me/fleshkatrenera"
bonuses = {
    "levels": [1, 3, 5, 10],
    "links": {
        1: "https://disk.yandex.ru/i/1EIIjw3htWkWXw",
        3: "https://disk.yandex.ru/i/N5S6eYQBgfyn5Q",
        5: "https://disk.yandex.ru/d/_WqG8_kiFYUpYw"
    }
}


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id  = message.from_user.id
    username = message.from_user.username or "без_username"

    # парсим ref_id из /start 12345
    parts = message.text.split()
    ref_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() and int(parts[1]) != user_id else None

    # сохраняем сразу
    await save_user(pool, user_id, username, ref_id)

    # клавиатура с кнопкой "Я подписался"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Я подписался", callback_data=f"confirm_sub:{user_id}")
        ]]
    )

    await message.answer(
        f"👋 Привет, @{username}!\n\n"
        f"Чтобы завершить регистрацию, подпишитесь на канал:\n{CHANNEL_URL}",
        reply_markup=kb
    )


@dp.callback_query(Text(startswith="confirm_sub:"))
async def on_confirm_sub(call: types.CallbackQuery):
    user_id = int(call.data.split(":", 1)[1])

    # проверяем подписку
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
    except:
        return await call.answer("Ошибка проверки. Попробуйте позже.", show_alert=True)

    if member.status not in (ChatMemberStatus.MEMBER, ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR):
        return await call.answer("⚠️ Вы ещё не подписались на канал.", show_alert=True)

    # получили подписку — начисляем бонус пригласившему
    inviter = await get_inviter(pool, user_id)
    if inviter:
        refs = await get_user_refs(pool, inviter)
        for lvl in bonuses["levels"]:
            if len(refs) >= lvl and await add_bonus(pool, inviter, lvl):
                link = bonuses["links"].get(lvl, "")
                await bot.send_message(
                    inviter,
                    f"🎁 Бонус за {lvl} приглашённых!\n{link}"
                )

    await call.answer("✅ Подписка подтверждена! Спасибо.", show_alert=True)
    # убрать кнопку
    await call.message.edit_reply_markup(reply_markup=None)


@dp.message(Command("invite"))
async def cmd_invite(message: types.Message):
    user_id = message.from_user.id
    bot_username = (await bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={user_id}"
    await message.answer(f"🔗 Твоя реферальная ссылка:\n{link}")


@dp.message(Command("myrefs"))
async def cmd_myrefs(message: types.Message):
    user_id = message.from_user.id
    refs = await get_user_refs(pool, user_id)
    if not refs:
        return await message.answer("Вы пока никого не пригласили.")
    text = f"Вы пригласили {len(refs)} человек(а):\n"
    for uid, uname in refs:
        text += f"— <a href='tg://user?id={uid}'>@{uname or 'user'}</a>\n"
    await message.answer(text, parse_mode="HTML")


@dp.message(Command("allrefs"))
async def cmd_allrefs(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ Только админ.")
    rows = await get_all_referrers(pool)
    if not rows:
        return await message.answer("❌ Никто ещё никого не пригласил.")
    text = "👥 Список рефереров:\n"
    for uid, uname, cnt in rows:
        text += f"— <a href='tg://user?id={uid}'>@{uname or 'user'}</a> — {cnt}\n"
    await message.answer(text, parse_mode="HTML")


async def main():
    global pool
    pool = await create_pool()
    await setup_db(pool)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
