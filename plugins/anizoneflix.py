# =====================================================================================##
#
#  ██╗░░██╗███╗░░██╗██████╗░░█████╗░████████╗███████╗██████╗░
#  ██║░░██║████╗░██║██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██╔══██╗
#  ██║░░██║██╔██╗██║██████╔╝███████║░░░██║░░░█████╗░░██║░░██║
#  ██║░░██║██║╚████║██╔══██╗██╔══██║░░░██║░░░██╔══╝░░██║░░██║
#  ╚█████╔╝██║░╚███║██║░░██║██║░░██║░░░██║░░░███████╗██████╔╝
#  ░╚════╝░╚═╝░░╚══╝╚═╝░░╚═╝╚═╝░░╚═╝░░░╚═╝░░░╚══════╝╚═════╝░
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

from config import OWNER_ID, USER_REPLY_TEXT, USER_ROAST_TEXT
from database.database import db


async def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


async def is_admin(user_id: int) -> bool:
    admin_ids = await db.get_all_admins()
    return user_id in admin_ids


async def check_owner_only(message):
    if not message.from_user:
        return False
    if not await is_owner(message.from_user.id):
        await message.reply(USER_REPLY_TEXT, quote=True)
        return False
    return True


async def check_admin_or_owner(message):
    if not message.from_user:
        return False
    if await is_owner(message.from_user.id) or await is_admin(message.from_user.id):
        return True
    await message.reply(USER_REPLY_TEXT, quote=True)
    return False


async def voidRoast(message):
    if not message.from_user:
        return False
    if await is_owner(message.from_user.id) or await is_admin(message.from_user.id):
        return True
    await message.reply(USER_ROAST_TEXT, quote=True)
    return False


# =====================================================================================##
#                         ✨ MADE BY ANIZONEFLIX ✨
#                  Join Updates Channel: https://t.me/anizoneflix
#====================================================================================##
