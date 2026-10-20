import logging
from pyrogram import Client as PyroClient
from pyrogram.raw import types as pyro_types, functions as pyro_functions

logger = logging.getLogger(__name__)

async def copy_video(pyrogram_bot: PyroClient, chat_id, from_chat_id, message_id, caption=None, reply_markup=None, protect_content=False):
    """
    Copies a video message using Pyrogram Raw API (ForwardMessages with drop_author=True)
    to perfectly preserve FHD video covers and other advanced video qualities, and then
    customizes/edits the caption and reply markup on the resulting message.
    """
    try:
        peer = await pyrogram_bot.resolve_peer(chat_id)
        from_peer = await pyrogram_bot.resolve_peer(from_chat_id)
        random_id = pyrogram_bot.rnd_id()

        # Server-side forward with drop_author=True acts as a copy and preserves 100% of FHD cover & media metadata!
        res = await pyrogram_bot.invoke(
            pyro_functions.messages.ForwardMessages(
                from_peer=from_peer,
                id=[message_id],
                random_id=[random_id],
                to_peer=peer,
                drop_author=True,
                noforwards=protect_content or None
            )
        )

        new_msg_id = None
        if hasattr(res, "updates"):
            for u in res.updates:
                if isinstance(u, (pyro_types.UpdateNewMessage, pyro_types.UpdateNewChannelMessage)):
                    new_msg_id = u.message.id
                    break

        if new_msg_id is None:
            raise Exception("Could not retrieve newly copied message ID from ForwardMessages response.")

        # Customize caption or reply markup on the newly copied message if provided
        if caption is not None or reply_markup is not None:
            try:
                if caption is not None:
                    await pyrogram_bot.edit_message_caption(
                        chat_id=chat_id,
                        message_id=new_msg_id,
                        caption=caption,
                        reply_markup=reply_markup
                    )
                elif reply_markup is not None:
                    await pyrogram_bot.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=new_msg_id,
                        reply_markup=reply_markup
                    )
            except Exception as edit_err:
                logger.error(f"Error customizing copied message caption/markup: {edit_err}")

        # Return the new Message object
        return await pyrogram_bot.get_messages(chat_id, message_ids=new_msg_id)

    except Exception as e:
        logger.error(f"Error in copy_video: {e}. Falling back to standard copy_message.")
        return await pyrogram_bot.copy_message(
            chat_id=chat_id,
            from_chat_id=from_chat_id,
            message_id=message_id,
            caption=caption,
            reply_markup=reply_markup,
            protect_content=protect_content
        )
