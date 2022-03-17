from dotenv import load_dotenv
import os
import asyncio
import re
import logging
import aiohttp

from aiogram import Bot, Dispatcher, executor, types, md

load_dotenv()


API_TOKEN = os.getenv("bot_token")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN, parse_mode="html")
dp = Dispatcher(bot)


def extract_links(message: types.Message):
    text = message.text or message.caption
    links = []

    for e in message.entities:
        if e.type == "text_link":
            links.append(e.url)
        elif e.type == "url":
            links.append(e.get_text(text))

    links = list(set(links))
    message.links = links
    return bool(links)


link_regex = re.compile(
    r"(?P<protocol>https?:\/\/)?(?P<url>(?P<domain>[^\s\/\\,?\.]+(\.[^\s\/\\,?\.]+)+)(?P<port>:\d+)?(?P<qs>\/\S*)?)",
    flags=re.I | re.M,
)


def extract_links_from_text(text):
    links = []
    for match in link_regex.finditer(text):
        links.append(match.group("url"))

    links = list(set(links))
    return links


def extract_links_from_query(q):
    q.links = extract_links_from_text(q.query)
    return bool(q.links)


# return Dict with "ok" bool
async def get_json(url: str):
    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.get(
                "https://a.devs.today/json", params={"url": url, "timeout": 60 * 2}
            )
            return await resp.json()
    except Exception as e:
        logger.exception("get_json")
        return {"ok": False, "error": "local error", "exception": str(e)}


async def get_cached_json(url: str):
    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.get(
                "https://a.devs.today/cachedJson",
                params={"url": url, "timeout": 60 * 2},
            )
            return await resp.json()
    except Exception as e:
        logger.exception("get_json")
        return {"ok": False, "error": "local error", "exception": str(e)}


@dp.message_handler(commands=["start", "help"])
async def send_welcome(message: types.Message):
    """
    This handler will be called when user sends `/start` or `/help` command
    """
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Try inline!", switch_inline_query=""))

    await message.reply(
        """
Hello! I am Instant Read Bot!
I make an Instant View from any web page.

You can use me here, <a href="t.me/{me.username}?startgroup=1">add me to group</a> or channel or use me inline.
In groups and dms I will try to create Instant View for each link I will see, in channels I will do this for only first link in each post.

<i>If Instant View does not work for some sites, write about it to <a href="tg://user?id=2505806">BrinDev support</a> and we will try to fix it.</i>

Send me link or use me inline:
    """.format(
            me=await message.bot.me
        ),
        reply_markup=kb,
    )


@dp.channel_post_handler(extract_links)
async def channel_iv(message: types.Message):
    link = message.links[0]

    result = await get_json(link)
    if not result.get("ok"):
        return

    await asyncio.sleep(0.5)
    await message.edit_text(
        md.hide_link(f"""https://a.devs.today/{result["url"]}""") + message.text
    )


@dp.message_handler(extract_links)
async def iv(message: types.Message):
    asyncio.gather(*[iv_loader(message, link) for link in message.links])


async def iv_loader(message: types.Message, link: str):
    m = await message.reply(
        f"""Loading <a href="{link}">article</a>, wait a little..."""
    )

    result = await get_json(link)
    if not result.get("ok"):
        await m.edit_text(f"""Sorry, can't load this <a href="{link}">article</a> :(""")
        if m.chat.id < 0:
            await asyncio.sleep(5)
            await m.delete()
        return

    await m.edit_text(
        f"""<a href="https://a.devs.today/{result["url"]}">{result["title"]}</a>"""
    )


@dp.message_handler(lambda m: m.chat.id > 0)
async def not_iv(message: types.Message):
    await message.reply("Links not found.")


@dp.inline_handler(extract_links_from_query)
async def inline_iv(inline_query: types.InlineQuery):
    items = await asyncio.gather(
        *[inline_iv_loader(link, id) for (id, link) in enumerate(inline_query.links)]
    )

    await inline_query.answer(results=items, cache_time=1)


async def inline_iv_loader(link: str, id: int):
    result = await get_cached_json(link)
    if not result["ok"]:
        iv_link = f"https://a.devs.today/{link}"

        input_content = types.InputTextMessageContent(iv_link)
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Loading...", callback_data="pass"))
        return types.InlineQueryResultArticle(
            id=id,
            url=iv_link,
            title="⚡️Instant View",
            # description=iv_link,
            input_message_content=input_content,
            reply_markup=kb,
        )

    input_content = types.InputTextMessageContent(
        f"""<a href="https://a.devs.today/{result["url"]}">{result["title"]}</a>"""
    )
    return types.InlineQueryResultArticle(
        id=id,
        url=result["url"],
        title=f"""{result["title"]} | ⚡️Instant View""",
        description=result.get("excerpt"),
        input_message_content=input_content,
    )


@dp.chosen_inline_handler()
async def on_chosen_inline(chosen: types.ChosenInlineResult):
    links = extract_links_from_text(chosen.query)
    id = int(chosen.result_id)
    link = links[id]

    result = await get_json(link)
    if not result.get("ok"):
        await chosen.bot.edit_message_text(
            f"""Sorry, can't load this <a href="{link}">article</a> :(""",
            inline_message_id=chosen.inline_message_id,
            reply_markup=types.InlineKeyboardMarkup(),
        )
        return

    await chosen.bot.edit_message_text(
        f"""<a href="https://a.devs.today/{result["url"]}">{result["title"]}</a>""",
        inline_message_id=chosen.inline_message_id,
        reply_markup=types.InlineKeyboardMarkup(),
    )


@dp.inline_handler()
async def not_inline_iv(inline_query: types.InlineQuery):
    await inline_query.answer(
        results=[],
        cache_time=1,
        switch_pm_text="Links not found.",
        switch_pm_parameter="links_not_found",
    )


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
