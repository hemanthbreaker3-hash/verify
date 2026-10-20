import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from bot import Bot
from database.database import db
from plugins.anizoneflix import check_admin_or_owner

def build_backup_menu():
    buttons = [
        [InlineKeyboardButton("📦 Backup Data", callback_data="backup_export", style="primary"),
         InlineKeyboardButton("📥 Restore Data", callback_data="backup_restore_prompt", style="success")],
        [InlineKeyboardButton("❌ Close", callback_data="close", style="danger")]
    ]
    return InlineKeyboardMarkup(buttons)

@Bot.on_message((filters.command("save") | filters.command("backup")) & filters.private)
async def save_backup_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        return

    text = (
        "<b>📦 AniZoneFlix Database Backup & Restore Center</b>\n\n"
        "<i>Save all bot configurations, shorteners, secondary DB channels, force-sub channels, admins, banned users, and verified users permanently into a ZIP archive, or restore from an existing backup:</i>"
    )
    await message.reply_text(text, reply_markup=build_backup_menu())

@Bot.on_callback_query(filters.regex("^backup_"))
async def backup_callback_handler(client: Client, query: CallbackQuery):
    if not await check_admin_or_owner(query):
        return await query.answer("⛔ Unauthorized access!", show_alert=True)

    data = query.data

    if data == "backup_export":
        await query.answer("Generating backup ZIP archive...", show_alert=False)
        msg = await query.message.reply_text("<b>⏳ Generating MongoDB backup ZIP archive...</b>")
        try:
            zip_path = await db.export_backup_zip("backup_anizoneflix.zip")
            if zip_path and os.path.exists(zip_path):
                await client.send_document(
                    chat_id=query.message.chat.id,
                    document=zip_path,
                    file_name="backup_anizoneflix.zip",
                    caption=(
                        "<b>📦 AniZoneFlix Database Backup</b>\n\n"
                        "<i>Here is your complete MongoDB backup file. Keep it safe or use it to restore on any instance.</i>"
                    ),
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close", style="danger")]])
                )
                await msg.delete()
                try:
                    os.remove(zip_path)
                except Exception:
                    pass
            else:
                await msg.edit_text("<b>❌ Failed to generate database backup. Please ensure database connection is active.</b>")
        except Exception as e:
            await msg.edit_text(f"<b>❌ Error generating backup:</b> <code>{e}</code>")

    elif data == "backup_restore_prompt":
        await query.answer()
        await query.message.edit_text(
            "<b>📥 Restore Database</b>\n\n"
            "<i>Please reply or send your <code>backup_anizoneflix.zip</code> file now.</i>\n\n"
            "<i>(Send /cancel to abort)</i>"
        )
        try:
            doc_msg = await client.listen(query.message.chat.id, timeout=120)
            if not doc_msg or (doc_msg.text and doc_msg.text.strip() == "/cancel"):
                return await query.message.reply_text("<b>❌ Restore operation cancelled.</b>")

            if not doc_msg.document or not (doc_msg.document.file_name and doc_msg.document.file_name.endswith(".zip")):
                return await doc_msg.reply_text("<b>❌ Invalid file format! Please send a valid <code>.zip</code> backup file.</b>")

            proc_msg = await doc_msg.reply_text("<b>⏳ Downloading and restoring database from backup file...</b>")
            downloaded_path = await client.download_media(doc_msg)

            if downloaded_path and os.path.exists(downloaded_path):
                success = await db.restore_from_zip(downloaded_path)
                try:
                    os.remove(downloaded_path)
                except Exception:
                    pass

                if success:
                    await proc_msg.edit_text(
                        "<b>✅ Database Restored Successfully!</b>\n\n"
                        "<i>All MongoDB collections, configurations, shorteners, DB channels, force-subs, and admins have been restored from your backup ZIP file.</i>",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close", style="danger")]])
                    )
                else:
                    await proc_msg.edit_text("<b>❌ Database restore failed. Please verify the ZIP file format.</b>")
            else:
                await proc_msg.edit_text("<b>❌ Failed to download backup ZIP file.</b>")

        except Exception as e:
            await query.message.reply_text(f"<b>❌ Error during restore:</b> <code>{e}</code>")
