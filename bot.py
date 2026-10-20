# =====================================================================================##
#
#  ██╗░░██╗███╗░░██╗██████╗░░█████╗░████████╗███████╗██████╗░
#  ██║░░██║████╗░██║██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██╔══██╗
#  ██║░░██║██╔██╗██║██████╔╝███████║░░░██║░░░█████╗░░██║░░██║
#  ██║░░██║██║╚████║██╔══██╗██╔══██║░░░██║░░░██╔══╝░░██║░░██║
#  ╚██████╔╝██║░╚███║██║░░██║██║░░██║░░░██║░░░███████╗██████╔╝
#  ░╚═════╝░╚═╝░░╚══╝╚═╝░░╚═╝╚═╝░░╚═╝░░░╚═╝░░░╚══════╝╚═════╝░
#
#  ░██████╗░██████╗░██████╗░███████╗██████╗░
#  ██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔══██╗
#  ██║░░░░░██║░░░██║██║░░██║█████╗░░██████╔╝
#  ██║░░░░░██║░░░██║██║░░██║██╔══╝░░██╔══██╗
#  ╚██████╗╚██████╔╝██████╔╝███████╗██║░░██║
#  ░╚═════╝░╚═════╝░╚═════╝░╚══════╝╚═╝░░╚═╝
#
#                         ✨ MADE BY ANIZONEFLIX ✨
#                  Join Updates Channel: https://t.me/anizoneflix
#=====================================================================================##

import asyncio
import pyromod.listen
import inspect
from pyrogram.handlers import MessageHandler

# Monkeypatch pyromod's MessageHandler.check to safely handle both synchronous and asynchronous custom/standard filters.
async def safe_check(self, client, update):
    listener = client.listening.get(update.chat.id)
    if listener and not listener['future'].done():
        if callable(listener['filters']):
            res = listener['filters'](client, update)
            if inspect.isawaitable(res):
                return await res
            return res
        return True
    if callable(self.filters):
        res = self.filters(client, update)
        if inspect.isawaitable(res):
            return await res
        return res
    return True

MessageHandler.check = safe_check

from pyrogram import Client
from pyrogram.enums import ParseMode
import functools

# Monkeypatch pyromod's Client.listen to use the currently running event loop,
# preventing "ValueError: The future belongs to a different loop than the one specified as the loop argument".
async def patched_listen(self, chat_id, filters=None, timeout=None):
    if type(chat_id) != int:
        chat = await self.get_chat(chat_id)
        chat_id = chat.id

    loop = asyncio.get_running_loop()
    future = loop.create_future()
    future.add_done_callback(
        functools.partial(self.clear_listener, chat_id)
    )
    self.listening.update({
        chat_id: {"future": future, "filters": filters}
    })
    return await asyncio.wait_for(future, timeout)

Client.listen = patched_listen
import sys
from datetime import datetime, timezone
from config import *
from database.database import db


name ="""
 BY ANIZONEFLIX
"""


class Bot(Client):
    def __init__(self):
        super().__init__(
            name="Bot",
            api_hash=API_HASH,
            api_id=APP_ID,
            plugins={
                "root": "plugins"
            },
            workers=TG_BOT_WORKERS,
            bot_token=TG_BOT_TOKEN
        )
        self.LOGGER = LOGGER

    async def start(self):
        # Flask is started from main.py as __main__, while this method may also
        # import the same file under the module name "main". Keep the event-loop
        # reference synchronized in both module objects so Flask worker threads
        # can submit database coroutines to the bot's actual running loop.
        loop = asyncio.get_running_loop()
        try:
            import sys
            entry_module = sys.modules.get("__main__")
            if entry_module is not None and hasattr(entry_module, "MAIN_LOOP"):
                entry_module.MAIN_LOOP = loop
            import main as main_module
            main_module.MAIN_LOOP = loop
        except Exception as exc:
            try:
                self.LOGGER(__name__).warning(
                    f"Could not synchronize verification event loop: {type(exc).__name__}: {exc}"
                )
            except Exception:
                pass
        await super().start()
        usr_bot_me = await self.get_me()
        self.uptime = datetime.now()
        try:
            from zoneinfo import ZoneInfo
            now_utc = datetime.now(timezone.utc)
            last_shutdown = await db.get_config_val("BOT_LAST_SHUTDOWN_TS", None)
            if last_shutdown:
                last_dt = datetime.fromisoformat(last_shutdown)
                downtime_sec = int((now_utc - last_dt).total_seconds())
                if downtime_sec > 5:
                    self.LOGGER(__name__).info(f"Bot resumed after {downtime_sec}s downtime. Applying compensation...")
                    await db.apply_downtime_compensation(downtime_sec)
            await db.update_config("BOT_LAST_SHUTDOWN_TS", now_utc.isoformat())
        except Exception as comp_err:
            self.LOGGER(__name__).warning(f"Error applying downtime compensation: {comp_err}")

        if CHANNEL_ID:
            try:
                db_channel = await self.get_chat(CHANNEL_ID)
                self.db_channel = db_channel
                test = await self.send_message(chat_id = db_channel.id, text = "Test Message")
                await test.delete()
            except Exception as e:
                self.LOGGER(__name__).warning(e)
                self.LOGGER(__name__).warning(f"Make Sure bot is Admin in DB Channel, and Double check the CHANNEL_ID Value, Current Value {CHANNEL_ID}")
                self.LOGGER(__name__).info("\nBot failed to initialize correctly. Join https://t.me/anizoneflix for support")
        else:
            self.LOGGER(__name__).warning("CHANNEL_ID is not set. Bot will not be able to store/retrieve files.")

        self.set_parse_mode(ParseMode.HTML)
        self.LOGGER(__name__).info(f"Bot Running..!\n\nCreated by \n@anizoneflix")
        self.LOGGER(__name__).info(f"""BOT DEPLOYED BY @anizoneflix""")

        self.set_parse_mode(ParseMode.HTML)
        self.username = usr_bot_me.username
        await db.update_config("BOT_USERNAME", usr_bot_me.username)
        self.LOGGER(__name__).info(f"Bot Running..! Made by @anizoneflix")


        try:
            from pyrogram.types import BotCommand
            await self.set_bot_commands([
                BotCommand("start", "sᴛᴀʀᴛs ᴏʀ ʀᴇsᴛᴀʀᴛs ᴛʜᴇ ʙᴏᴛ"),
                BotCommand("help", "sʜᴏᴡs ᴛʜᴇ sᴜᴘᴘᴏʀᴛ/ʜᴇʟᴘ ᴍᴇssᴀɢᴇ"),
                BotCommand("commands", "ʟɪsᴛs ᴀʟʟ ᴀᴠᴀɪʟᴀʙʟᴇ ʙᴏᴛ ᴄᴏᴍᴍᴀɴᴅs"),
                BotCommand("stats", "sʜᴏᴡs ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs"),
                BotCommand("ping", "ᴄʜᴇᴄᴋs ᴛʜᴇ ʙᴏᴛ's ᴘɪɴɢ ʟᴀᴛᴇɴᴄʏ"),
                BotCommand("users", "sʜᴏᴡs ᴛʜᴇ ᴛᴏᴛᴀʟ ᴜsᴇʀ ᴄᴏᴜɴᴛ"),
                BotCommand("add_admin", "ᴀᴅᴅs ᴀ ɴᴇᴡ ᴀᴅᴍɪɴ ᴜsᴇʀ"),
                BotCommand("admins", "ʟɪsᴛs ᴀʟʟ ᴀᴄᴛɪᴠᴇ ᴀᴅᴍɪɴ ɪᴅs"),
                BotCommand("deladmin", "ʀᴇᴍᴏᴠᴇs ᴀɴ ᴀᴅᴍɪɴ ᴜsᴇʀ"),
                BotCommand("addchnl", "ᴀᴅᴅs ᴀ ɴᴇᴡ ғᴏʀᴄᴇ sᴜʙ ᴄʜᴀɴɴᴇʟ"),
                BotCommand("delchnl", "ʀᴇᴍᴏᴠᴇs ᴀ ғᴏʀᴄᴇ sᴜʙ ᴄʜᴀɴɴᴇʟ"),
                BotCommand("listchnl", "sʜᴏᴡs ᴛʜᴇ ғᴏʀᴄᴇ sᴜʙ ᴄʜᴀɴɴᴇʟs"),
                BotCommand("fsub_mode", "ᴛᴏɢɢʟᴇs ғᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ᴍᴏᴅᴇ"),
                BotCommand("ban", "ʙᴀɴs ᴀ ᴜsᴇʀ ғʀᴏᴍ ᴛʜᴇ ʙᴏᴛ"),
                BotCommand("unban", "ᴜɴʙᴀɴs ᴀ ᴜsᴇʀ"),
                BotCommand("banlist", "sʜᴏᴡs ᴛʜᴇ ʟɪsᴛ ᴏғ ʙᴀɴɴᴇᴅ ᴜsᴇʀs"),
                BotCommand("batch", "ᴄʀᴇᴀᴛᴇs ᴀ ʙᴀᴛᴄʜ ᴏғ ғɪʟᴇ ʟɪɴᴋs"),
                BotCommand("custom_batch", "sᴀᴠᴇs ᴄᴜsᴛᴏᴍ ᴍᴇssᴀɢᴇs ᴀs ᴀ ʙᴀᴛᴄʜ ʟɪɴᴋ"),
                BotCommand("genlink", "ɢᴇɴᴇʀᴀᴛᴇs ᴀ sɪɴɢʟᴇ sʜᴀʀᴇ ʟɪɴᴋ"),
                BotCommand("broadcast", "sᴇɴᴅs ᴀ ʙʀᴏᴀᴅᴄᴀsᴛ ᴍᴇssᴀɢᴇ"),
                BotCommand("pbroadcast", "sᴇɴᴅs ᴀ ᴘʜᴏᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ"),
                BotCommand("dbroadcast", "sᴇɴᴅs ᴀ sɪʟᴇɴᴛ ʙʀᴏᴀᴅᴄᴀsᴛ"),
                BotCommand("dlt_time", "sᴇᴛs ᴛʜᴇ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ᴛɪᴍᴇr"),
                BotCommand("delete", "ᴅᴇʟᴇᴛᴇs ᴍᴇssᴀɢᴇs ғʀᴏᴍ ᴅʙ ᴄʜᴀɴɴᴇʟ"),
                BotCommand("check_dlt_time", "ᴄʜᴇᴄᴋs ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ᴛɪᴍᴇʀ"),
                BotCommand("retrieve_on", "ᴇɴᴀʙʟᴇs ᴛʜᴇ ᴅᴇʟᴇᴛɪᴏɴ ᴀʟᴇʀᴛ ᴍᴇssᴀɢᴇ"),
                BotCommand("retrieve_off", "ᴅɪsᴀʙʟᴇs ᴛʜᴇ ᴅᴇʟᴇᴛɪᴏɴ ᴀʟᴇʀᴛ ᴍᴇssᴀɢᴇ"),
                BotCommand("panel", "ᴏᴘᴇɴs ᴛʜᴇ ᴀɴɪᴢᴏɴᴇғʟɪx ᴄᴏɴᴛʀᴏʟ ᴘᴀɴᴇʟ"),
                BotCommand("verify", "ᴠᴇʀɪғʏ ᴏʀ ᴇxᴛᴇɴᴅ ʏᴏᴜʀ ᴀᴄᴄᴇss ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ"),
                BotCommand("count", "sʜᴏᴡs ᴠᴇʀɪғɪᴇᴅ ᴜsᴇʀs ʀᴇᴘᴏʀᴛ"),
                BotCommand("addpremium", "ᴀᴅᴅs ᴀ ᴘʀᴇᴍɪᴜᴍ ᴜsᴇʀ"),
                BotCommand("delpremium", "ʀᴇᴍᴏᴠᴇs ᴀ ᴘʀᴇᴍɪᴜᴍ ᴜsᴇʀ"),
                BotCommand("premium_users", "ʟɪsᴛs ᴀʟʟ ᴘʀᴇᴍɪᴜᴍ ᴜsᴇʀs"),
                BotCommand("reset", "ᴇxᴘɪʀᴇ ᴜsᴇʀ ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ ɪɴsᴛᴀɴᴛʟʏ"),
                BotCommand("addclone", "ᴀᴅᴅ ᴀ ɴᴇᴡ ᴄʟᴏɴᴇ ʙᴏᴛ"),
                BotCommand("delclone", "ʀᴇᴍᴏᴠᴇ ᴀ ᴄʟᴏɴᴇ ʙᴏᴛ"),
                BotCommand("clones", "ʟɪsᴛ ᴀʟʟ ᴄᴏɴғɪɢᴜʀᴇᴅ ᴄʟᴏɴᴇ ʙᴏᴛs"),
                BotCommand("addshortener", "ᴀᴅᴅ ᴀ ɴᴇᴡ sʜᴏʀᴛᴇɴᴇʀ"),
                BotCommand("delshortener", "ʀᴇᴍᴏᴠᴇ ᴀ sʜᴏʀᴛᴇɴᴇʀ"),
                BotCommand("shorteners", "ʟɪsᴛ ᴀʟʟ sʜᴏʀᴛᴇɴᴇʀs"),
                BotCommand("add_db_channel", "ᴀᴅᴅ ᴀ sᴇᴄᴏɴᴅᴀʀʏ ᴅʙ ᴄʜᴀɴɴᴇʟ"),
                BotCommand("del_db_channel", "ʀᴇᴍᴏᴠᴇ ᴀ sᴇᴄᴏɴᴅᴀʀʏ ᴅʙ ᴄʜᴀɴɴᴇʟ"),
                BotCommand("list_db_channels", "ʟɪsᴛ sᴇᴄᴏɴᴅᴀʀʏ ᴅʙ ᴄʜᴀɴɴᴇʟs"),
                BotCommand("verify_on", "ᴇɴᴀʙʟᴇ sʜᴏʀᴛᴇɴᴇʀ ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ"),
                BotCommand("verify_off", "ᴅɪsᴀʙʟᴇ sʜᴏʀᴛᴇɴᴇʀ ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ"),
                BotCommand("set_base_url", "sᴇᴛ ᴛʜᴇ ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ ʙᴀsᴇ ᴜʀʟ"),
                BotCommand("hyperlink", "ᴇxᴛʀᴀᴄᴛ ʜʏᴘᴇʀʟɪɴᴋs ғʀᴏᴍ ᴍᴇssᴀɢᴇs")
            ])
            self.LOGGER(__name__).info("Bot commands set successfully starting with start.")
        except Exception as e:
            self.LOGGER(__name__).warning(f"Error setting bot commands: {e}")

        try: await self.send_message(OWNER_ID, text = f"<b><blockquote> Bᴏᴛ Rᴇsᴛᴀʀᴛᴇᴅ by @anizoneflix</blockquote></b>")
        except: pass

        try:
            from plugins.panel import start_all_clones
            await start_all_clones(self)
        except Exception as e:
            self.LOGGER(__name__).warning(f"Failed to auto-start clone bots: {e}")

        async def expiry_checker_loop():
            while True:
                try:
                    await asyncio.sleep(10)
                    await db.check_and_notify_expirations(self)
                except Exception as ex_err:
                    print(f"Error in expiry_checker_loop: {ex_err}")

        asyncio.create_task(expiry_checker_loop())

    async def stop(self, *args):
        await super().stop()
        self.LOGGER(__name__).info("Bot stopped.")

    def run(self):
        """Run the bot."""
        super().run()

# =====================================================================================##
#                         ✨ MADE BY ANIZONEFLIX ✨
#                  Join Updates Channel: https://t.me/anizoneflix
#====================================================================================##
