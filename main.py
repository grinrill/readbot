from dotenv import load_dotenv
import os
import asyncio
import re
import logging

from aiogram import Bot, Dispatcher, executor, types, md

load_dotenv()


API_TOKEN = os.getenv("bot_token")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
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


def extract_links_from_query(q):
    text = q.query
    links = []
    for match in link_regex.finditer(text):
        links.append(match.group("url"))

    q.links = links
    return bool(links)


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
Send me link or use me inline:
    """,
        reply_markup=kb,
    )


@dp.channel_post_handler(extract_links)
async def channel_iv(message: types.Message):
    link = message.links[0]
    await message.edit_text(md.hide_link(f"https://a.devs.today/{link}") + message.text)


@dp.message_handler(extract_links)
async def iv(message: types.Message):
    # print(message.links)
    await message.chat.do("typing")
    for link in message.links:
        await asyncio.sleep(0.5)
        await message.reply(f"https://a.devs.today/{link}")


@dp.message_handler(lambda m: m.chat.id > 0)
async def not_iv(message: types.Message):
    await message.reply("Links not found.")


@dp.inline_handler(extract_links_from_query)
async def inline_iv(inline_query: types.InlineQuery):
    items = []
    for link in inline_query.links:
        iv_link = f"https://a.devs.today/{link}"

        input_content = types.InputTextMessageContent(iv_link)
        item = types.InlineQueryResultArticle(
            id=hash(link),
            title="⚡️Instant View",
            description=iv_link,
            input_message_content=input_content,
        )
        items.append(item)

    await inline_query.answer(results=items, cache_time=1)


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
