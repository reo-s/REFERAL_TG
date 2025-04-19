import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated

from config import API_TOKEN, ADMIN_ID
from db import (
    create_pool, setup_db,
    save_user, save_invite_link,
    add_bonus, get_user_refs,
    get_all_referrers, get_inviter_by_link
)

bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher()
pool = None

CHANNEL_ID   = -1001182955252               # твой канал
CHANNEL_LINK = "https://t.me/fleshkatrenera"
bonuses = {
    "levels": [1, 3, 5, 10],
    "links": {
        1: "https://disk.yandex.ru/i/1EIIjw3htWkWXw",
        3: "https://disk.yandex.ru/i/N5S6eYQBgfyn5Q",
        5: "https://disk.yandex.ru/d/_WqG8_kiFYUpYw"
    }
}

@dp.message(Command("invite"))
async def cmd_invite(message: types.Message):
    inviter = message.from_user.id
    # создаём персональную ссылку
    link_obj = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        name=str(inviter),      # сохраняем inviter_id в name
        expire_date=None,
        member_limit=None
    )
    link = link_obj.invite_link

    # сохраняем в БД
    await save_invite_link(pool, link, inviter)

    await message.answer(
        f"🔗 Ваша персональная ссылка‑приглашение:\n{link}\n\n"
        "Попросите друзей подписаться сразу по ней!"
    )

@dp.chat_member(ChatMemberUpdated.filter(F.chat.id == CHANNEL_ID))
async def on_channel_join(evt: ChatMemberUpdated):
    old, new = evt.old_chat_member, evt.new_chat_member
    # только новые подписки
    if old.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED) \
       and new.status == ChatMemberStatus.MEMBER:

        user = new.user
        username = user.username or "без_username"

        # узнаём, по какой ссылке пришёл
        inv_link = evt.invite_link.invite_link if evt.invite_link else None
        inviter = await get_inviter_by_link(pool, inv_link) if inv_link else None

        # сохраняем P2 в таблице users
        await save_user(pool, user.id, username, inviter)

        # начисляем бонус P1
        if inviter:
            refs = await get_user_refs(pool, inviter)
            for lvl in bonuses["levels"]:
                if len(refs) >= lvl:
                    granted = await add_bonus(pool, inviter, lvl)
                    if granted:
                        text = (f"🎁 Бонус за {lvl} приглашённых:\n"
                                f"{bonuses['links'].get(lvl,'')}")
                        await bot.send_message(inviter, text)


@dp.message(Command("myrefs"))
async def handle_myrefs(message: types.Message):
    uid = message.from_user.id
    refs = await get_user_refs(pool, uid)
    if not refs:
        return await message.answer("Вы пока никого не пригласили.")
    text = f"Вы пригласили {len(refs)} человек(а):\n"
    for r_uid, r_uname in refs:
        text += f"— <a href='tg://user?id={r_uid}'>@{r_uname or 'user'}</a>\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("allrefs"))
async def handle_allrefs(message: types.Message):
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
