import asyncio
import time
import uuid
import re
from collections import defaultdict
from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified, FloodWait
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import USER_REPLY_TEXT, CHANNEL_ID
import config
from helper_func import get_messages, encode
from plugins.anizoneflix import check_admin_or_owner
from database.database import db

# Standalone helper functions & state manager for autobatch functionality

def parse_mixed_inputs(text):
    if not text:
        return []
    items = []

    # Format A: https://t.me/c/CHANNEL_ID/START-https://t.me/c/CHANNEL_ID/END
    double_url_pattern = r"(https?://(?:t\.me|telegram\.me|telegram\.dog)/(?:c/)?([^/?\s]+)/(\d+))-(https?://(?:t\.me|telegram\.me|telegram\.dog)/(?:c/)?([^/?\s]+)/(\d+))"
    # Format B: https://t.me/c/CHANNEL_ID/START-END or raw start-end
    single_url_pattern = r"(https?://(?:t\.me|telegram\.me|telegram\.dog)/(?:c/)?([^/?\s]+)/)?(\d+)-(\d+)"
    # Single link: https://t.me/c/CHANNEL_ID/START or raw start
    single_item_pattern = r"(https?://(?:t\.me|telegram\.me|telegram\.dog)/(?:c/)?([^/?\s]+)/)?(\d+)"

    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        double_matches = list(re.finditer(double_url_pattern, line))
        if double_matches:
            for match in double_matches:
                chan = match.group(2)
                start_id = int(match.group(3))
                end_id = int(match.group(6))
                if start_id > end_id:
                    start_id, end_id = end_id, start_id
                items.append({
                    'channel': chan,
                    'start_id': start_id,
                    'end_id': end_id,
                    'original': match.group(0)
                })
            continue

        single_matches = list(re.finditer(single_url_pattern, line))
        if single_matches:
            for match in single_matches:
                chan = match.group(2)
                start_id = int(match.group(3))
                end_id = int(match.group(4))
                if start_id > end_id:
                    start_id, end_id = end_id, start_id
                items.append({
                    'channel': chan,
                    'start_id': start_id,
                    'end_id': end_id,
                    'original': match.group(0)
                })
            continue

        item_matches = list(re.finditer(single_item_pattern, line))
        for match in item_matches:
            chan = match.group(2)
            start_id = int(match.group(3))
            items.append({
                'channel': chan,
                'start_id': start_id,
                'end_id': start_id,
                'original': match.group(0)
            })
    return items

def match_channel_id(ref_str, db_cid):
    if not ref_str or not db_cid:
        return False
    ref_str = str(ref_str).replace("c/", "").replace("@", "").strip()
    db_cid_str = str(db_cid).strip()

    if ref_str == db_cid_str:
        return True

    ref_digits = re.sub(r'[^\d]', '', ref_str)
    db_digits = re.sub(r'[^\d]', '', db_cid_str)

    if ref_digits and db_digits:
        if ref_digits == db_digits:
            return True
        if db_digits.startswith("100") and db_digits[3:] == ref_digits:
            return True
        if ref_digits.startswith("100") and ref_digits[3:] == db_digits:
            return True

    return False

async def resolve_db_source(client, chan_ref):
    current_username = getattr(client, "username", "bot") or "bot"
    current_username = current_username.replace("@", "").strip().lower()

    main_cid = CHANNEL_ID
    secondary_cids = await db.get_db_channels()
    clones = await db.get_all_clones()

    from plugins.panel import active_clones

    if not chan_ref:
        return main_cid, current_username, client

    norm_ref = str(chan_ref).replace("c/", "").replace("@", "").strip()

    # 1. Check main channel
    if match_channel_id(norm_ref, main_cid):
        return main_cid, current_username, client

    # 2. Check secondary DB channels
    for s_cid in secondary_cids:
        if match_channel_id(norm_ref, s_cid):
            return s_cid, current_username, client

    # 3. Check clone bot DB channels
    for clone in clones:
        c_db_cid = clone.get('db_channel_id')
        c_un = clone.get('bot_username', '').replace("@", "").strip().lower()

        if match_channel_id(norm_ref, c_db_cid) or (c_un and c_un == norm_ref.lower()):
            target_cid = c_db_cid
            target_bot_username = c_un
            if c_un in active_clones:
                running_client = active_clones[c_un]
            else:
                running_client = client
            return target_cid, target_bot_username, running_client

    # 4. Fallback: return main_cid
    return main_cid, current_username, client

def clean_emojis_and_html(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'[\U00010000-\U0010ffff]', ' ', text)
    text = re.sub(r'[._\-\[\]\(\)]', ' ', text)
    return ' '.join(text.split())

def parse_metadata_universal(text):
    if not text:
        return 1, None, 'unknown'

    # Season detection (e.g. S01, S1, Season 1)
    season_match = re.search(r'\b(?:S|Season)\s*(\d+)\b', text, re.IGNORECASE)
    season = int(season_match.group(1)) if season_match else 1

    # Episode / Part detection
    ep_match = re.search(r'\b(?:E|EP|Episode)\s*(\d+(?:\.\d+)?)\b', text, re.IGNORECASE)
    part_match = re.search(r'\b(?:Part|Pt)\s*(\d+)\b', text, re.IGNORECASE)

    if ep_match:
        try:
            val = float(ep_match.group(1))
            val = int(val) if val.is_integer() else val
            return season, val, 'episode'
        except ValueError:
            pass

    if part_match:
        try:
            return season, int(part_match.group(1)), 'part'
        except ValueError:
            pass

    # Standalone S01E05 pattern without spaces
    se_match = re.search(r'\bS(\d+)E(\d+(?:\.\d+)?)\b', text, re.IGNORECASE)
    if se_match:
        try:
            s_val = int(se_match.group(1))
            val = float(se_match.group(2))
            val = int(val) if val.is_integer() else val
            return s_val, val, 'episode'
        except ValueError:
            pass

    # Generic number fallback ignoring resolution numbers & codec tags
    ignore_numbers = {'1080', '720', '480', '2160', '360', '1440', '900', '540', '264', '265', '4', '8'}
    tokens = re.findall(r'\b(\d{1,4}(?:\.\d+)?)\b', text)
    for tok in tokens:
        if tok in ignore_numbers:
            continue
        try:
            val = float(tok)
            val = int(val) if val.is_integer() else val
            return season, val, 'number'
        except ValueError:
            pass

    return season, None, 'unknown'

def detect_quality(text):
    if not text:
        return "UNKNOWN"
    text_upper = text.upper()

    if "2160P" in text_upper or "4K" in text_upper or "UHD" in text_upper:
        return "4K"
    if "1440P" in text_upper:
        return "1440P"
    if "1080P" in text_upper or "FHD" in text_upper or "FULL HD" in text_upper:
        return "1080P"
    if "900P" in text_upper:
        return "900P"
    if "720P" in text_upper or "HD" in text_upper:
        return "720P"
    if "540P" in text_upper:
        return "540P"
    if "480P" in text_upper or "SD" in text_upper:
        return "480P"
    if "360P" in text_upper:
        return "360P"
    return "UNKNOWN"

def get_filename(message):
    media = message.document or message.video or message.audio or message.animation
    if media and hasattr(media, "file_name") and media.file_name:
        return media.file_name
    return ""

async def generate_list_link(client, cid, mids, bot_username="bot"):
    if not mids:
        return ""
    divisor = abs(cid) if cid else 1
    start_id = mids[0] * divisor
    end_id = mids[-1] * divisor
    if start_id == end_id:
        string = f"get-{start_id}"
    else:
        string = f"get-{start_id}-{end_id}"
    base64_string = await encode(string)
    actual_username = bot_username or getattr(client, "username", "bot") or "bot"
    actual_username = actual_username.replace("@", "").strip()
    return f"https://telegram.me/{actual_username}?start={base64_string}"

def split_blocks_into_parts(blocks, max_length=3800):
    parts = []
    current_part = []
    current_len = 0
    for block in blocks:
        b_len = len(block) + 2
        if current_len + b_len > max_length:
            parts.append("\n\n".join(current_part))
            current_part = [block]
            current_len = len(block)
        else:
            current_part.append(block)
            current_len += b_len
    if current_part:
        parts.append("\n\n".join(current_part))
    return parts

def label_parts(parts):
    if len(parts) <= 1:
        return parts
    labeled = []
    total = len(parts)
    for idx, p in enumerate(parts, 1):
        labeled.append(f"<b>[Part {idx}/{total}]</b>\n\n{p}")
    return labeled

class SimpleStateManager:
    def __init__(self):
        self.states = {}

    def set_state(self, bot_username, user_id, cmd, data):
        key = f"{bot_username}_{user_id}"
        self.states[key] = data
        return data

    def get_state(self, bot_username, user_id):
        key = f"{bot_username}_{user_id}"
        return self.states.get(key)

    def clear_state(self, bot_username, user_id):
        key = f"{bot_username}_{user_id}"
        self.states.pop(key, None)

state_manager = SimpleStateManager()

# Quality priority for sorting
QUALITY_PRIORITY = {
    "4K": 1,
    "2160P": 2,
    "1440P": 3,
    "1080P": 4,
    "900P": 5,
    "720P": 6,
    "540P": 7,
    "480P": 8,
    "360P": 9,
    "UNKNOWN": 10
}

# In-memory FIFO tasks queues
AUTO_BATCH_QUEUES = defaultdict(list)          # bot_username -> list of task dicts (queued)
AUTO_BATCH_ACTIVE_TASKS = {}                    # bot_username -> active task dict or None
AUTO_BATCH_PUBLISH_LOCKS = defaultdict(asyncio.Lock) # bot_username -> Lock for serializing publishing

# Helper to edit messages safely without throwing MessageNotModified or crashing
async def edit_msg_safe(client, chat_id, message_id, text, reply_markup=None):
    try:
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup
        )
    except MessageNotModified:
        pass
    except Exception as e:
        if "MESSAGE_NOT_MODIFIED" in str(e):
            pass
        else:
            print(f"[EDIT ERROR] {e}")

# Helper to format progress bar
def make_progressbar(percent, length=10):
    filled = int(percent / (100 / length))
    return "█" * filled + "░" * (length - filled)

def episode_sort_key(ep):
    if isinstance(ep, (int, float)):
        return (0, ep, "")
    elif isinstance(ep, str):
        try:
            val = float(ep)
            return (0, val, "")
        except ValueError:
            return (1, 0, ep)
    return (2, 0, str(ep))

@Client.on_message(filters.private & filters.command(['auto_batch', 'advance_batch', 'advbatch']))
async def autobatch_and_advbatch(client: Client, message: Message):
    # Enforce Admin-only check
    if not await check_admin_or_owner(message):
        await message.reply_text(USER_REPLY_TEXT)
        return

    cmd = message.command[0].lower()
    is_adv = cmd in ['advance_batch', 'advbatch']

    input_text = message.text or ""
    has_arg = len(message.command) > 1 if message.text else False

    # Always prompt for range input unless replying to a message with range
    if message.reply_to_message:
        reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        input_text = f"/{cmd}\n{reply_text}"
    else:
        # Prompt mode
        try:
            ask = await client.ask(
                message.chat.id,
                f"<b>🎬 Send range link(s) or token(s) for /{cmd}.</b>\n\n<i>Supports single or multiple ranges in multi-line text. Type /cancel to cancel.</i>",
                filters=filters.text,
                timeout=120
            )
            if ask.text.lower() == "/cancel":
                await ask.reply("❌ <b>Process Cancelled.</b>")
                return
            input_text = f"/{cmd}\n{ask.text}"
        except asyncio.TimeoutError:
            await message.reply("⏰ <b>Timeout! Process Cancelled.</b>")
            return

    parsed_items = parse_mixed_inputs(input_text.replace(f"/{cmd}", ""))
    if not parsed_items:
        await message.reply_text("❌ <b>No valid ranges found in the input. Please check link format.</b>")
        return

    # Verify each range and resolve source safely
    validated_ranges = []
    for item in parsed_items:
        chan_ref = item.get('channel')
        start = item.get('start_id')
        end = item.get('end_id')

        try:
            cid, bot_username, running_client = await resolve_db_source(client, chan_ref)
            if not cid or not running_client:
                await message.reply_text(f"⚠️ <b>Warning: No configured DB bot/channel was found for:</b> <code>{item.get('original')}</code>")
                continue

            validated_ranges.append({
                'cid': cid,
                'start_id': start,
                'end_id': end,
                'bot_username': bot_username,
                'original_token': item.get('original')
            })
        except Exception as ex:
            print(f"[RANGE RESOLVE ERROR] {ex}")
            await message.reply_text(f"⚠️ <b>Error resolving range:</b> <code>{item.get('original')}</code>")

    if not validated_ranges:
        await message.reply_text("❌ <b>No accessible ranges could be resolved. Please verify database channel permissions.</b>")
        return

    # Sequential Wizard Flow for each validated range
    configured_results = []
    bot_user = (getattr(client, "username", "bot") or "bot").lower()
    admin_id = message.from_user.id

    state_manager.set_state(bot_user, admin_id, cmd, validated_ranges)

    try:
        for idx, item in enumerate(validated_ranges, 1):
            range_disp = f"{item['start_id']}-{item['end_id']}"

            # Step 1: Format & Count
            step1_text = (
                f"📦 <b>[Range {idx}/{len(validated_ranges)}] - Step 1/2</b>\n"
                f"Range: <code>{range_disp}</code>\n\n"
                f"<b>What should be used for generating the batch — episode numbers, message range, or another supported format?</b>\n\n"
                f"<i>Send total episode/file count (e.g. <code>13</code> or <code>25</code>).</i>\n\n"
                f"<i>Type /cancel_batch to cancel.</i>"
            )
            step1_msg = await message.reply_text(step1_text)
            last_msg_id = step1_msg.id

            episode_count = 9999
            while True:
                resp = await client.listen(chat_id=message.chat.id, filters=filters.text, timeout=300)
                if resp.id <= last_msg_id:
                    continue
                resp_text = resp.text.strip()
                if resp_text.lower() == "/cancel_batch":
                    state_manager.clear_state(bot_user, admin_id)
                    await message.reply_text("❌ <b>Auto Batch wizard cancelled.</b>")
                    return

                # Check for digit or format string
                digits = re.findall(r'\d+', resp_text)
                if digits:
                    episode_count = int(digits[0])
                    break
                elif resp_text.lower() in ["all", "auto", "message", "episode", "part", "range"]:
                    episode_count = 9999
                    break
                else:
                    err_msg = await message.reply_text("⚠️ <b>Invalid input! Please send a number (e.g. 13) or 'all'.</b>")
                    last_msg_id = err_msg.id

            # Step 2: Anime Name
            step2_text = (
                f"🎬 <b>[Range {idx}/{len(validated_ranges)}] - Step 2/2</b>\n"
                f"Range: <code>{range_disp}</code>\n"
                f"Requested Count: <code>{episode_count if episode_count < 9999 else 'All Available'}</code>\n\n"
                f"<b>Send the Anime Name to search across filename and file caption.</b>\n\n"
                f"Examples:\n"
                f"<code>Naruto</code>\nor\n<code>Naruto, Naruto Shippuden</code>\n\n"
                f"<i>Type <code>.</code> to search all files without anime name filter.</i>\n\n"
                f"<i>Type /cancel_batch to cancel.</i>"
            )
            step2_msg = await message.reply_text(step2_text)
            last_msg_id = step2_msg.id

            anime_names = None
            while True:
                resp_anime = await client.listen(chat_id=message.chat.id, filters=filters.text, timeout=300)
                if resp_anime.id <= last_msg_id:
                    continue
                anime_text = resp_anime.text.strip()
                if anime_text.lower() == "/cancel_batch":
                    state_manager.clear_state(bot_user, admin_id)
                    await message.reply_text("❌ <b>Auto Batch wizard cancelled.</b>")
                    return
                if anime_text in [".", "..", "...", "-", "_", "*"]:
                    anime_names = None
                else:
                    anime_names = [n.strip() for n in anime_text.split(",") if n.strip()]
                break

            configured_results.append({
                'cid': item['cid'],
                'start_id': item['start_id'],
                'end_id': item['end_id'],
                'bot_username': item['bot_username'],
                'episode_count': episode_count,
                'anime_names': anime_names,
                'original_token': item['original_token']
            })

    except asyncio.TimeoutError:
        state_manager.clear_state(bot_user, admin_id)
        await message.reply_text("⏰ <b>Wizard timed out. Operation aborted. You can run /{cmd} again anytime.</b>")
        return
    except Exception as ex:
        print(f"[WIZARD ERROR] {ex}")
        state_manager.clear_state(bot_user, admin_id)
        await message.reply_text(f"⚠️ <b>Wizard encountered an error:</b> `{ex}`")
        return

    # Clear temporary state
    state_manager.clear_state(bot_user, admin_id)

    # Combined Confirmation Summary
    confirm_text = f"📋 <b>Configure {'Advanced' if is_adv else 'Regular'} Auto Batch Tasks Summary:</b>\n\n"
    for idx, conf in enumerate(configured_results, 1):
        anime_disp = ", ".join(conf['anime_names']) if conf['anime_names'] else "No Anime Filter"
        count_disp = conf['episode_count'] if conf['episode_count'] < 9999 else 'All Available'
        confirm_text += (
            f"<b>{idx}. Range:</b> <code>{conf['original_token']}</code>\n"
            f"   <b>Target Bot:</b> @{conf['bot_username']}\n"
            f"   <b>Requested Count:</b> <code>{count_disp}</code>\n"
            f"   <b>Anime Filter:</b> <code>{anime_disp}</code>\n\n"
        )

    # Cache confirmation session in memory
    wizard_confirm_id = f"conf_{admin_id}_{int(time.time() * 1000)}"
    state_manager.set_state(bot_user, wizard_confirm_id, cmd, configured_results)

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🚀 Start All",
                callback_data=f"ab_start_{wizard_confirm_id}_{'adv' if is_adv else 'reg'}",
                style="primary"
            ),
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="ab_cancel_wizard",
                style="danger"
            )
        ]
    ])
    await message.reply_text(confirm_text, reply_markup=markup)

async def process_queue_worker(client, bot_username):
    while AUTO_BATCH_QUEUES[bot_username]:
        task = AUTO_BATCH_QUEUES[bot_username][0] # peek
        AUTO_BATCH_ACTIVE_TASKS[bot_username] = task
        task['status'] = 'running'

        try:
            loop = asyncio.get_running_loop()
            asyncio_task = loop.create_task(run_auto_batch_scan(client, task))
            task['asyncio_task'] = asyncio_task
            await asyncio_task
        except asyncio.CancelledError:
            task['status'] = 'cancelled'
            await edit_msg_safe(client, task['chat_id'], task['prompt_msg_id'], f"❌ <b>Task was cancelled.</b>")
        except Exception as e:
            task['status'] = 'failed'
            print(f"[WORKER TASK EXCEPTION] {e}")
            await edit_msg_safe(client, task['chat_id'], task['prompt_msg_id'], f"⚠️ <b>Task finished with note:</b> {e}\n\n<i>The bot remains active. You can retry anytime.</i>")
        finally:
            if AUTO_BATCH_QUEUES[bot_username] and AUTO_BATCH_QUEUES[bot_username][0]['task_id'] == task['task_id']:
                AUTO_BATCH_QUEUES[bot_username].pop(0)
            AUTO_BATCH_ACTIVE_TASKS[bot_username] = None

async def run_auto_batch_scan(client, task):
    bot_username = (getattr(client, "username", "bot") or "bot").lower()
    chat_id = task['chat_id']
    msg_id = task['prompt_msg_id']
    start_id = task['start_id']
    end_id = task['end_id']
    cid = task['cid']
    episode_limit = task['episode_count']
    anime_names = task['anime_names']
    target_bot_username = task['bot_username']
    is_adv = task.get('is_adv', False)

    anime_disp = ", ".join(anime_names) if anime_names else "No Anime Filter"

    start_time = time.time()
    scanned_count = 0
    matched_count = 0
    skipped_count = 0
    duplicate_count = 0
    error_count = 0

    try:
        from plugins.panel import active_clones
        target_client = active_clones.get(target_bot_username.lower(), client)

        total_range = list(range(start_id, end_id + 1)) if start_id <= end_id else list(range(start_id, end_id - 1, -1))
        total_count = len(total_range)

        # Structure: season -> quality -> list of (number, num_type, message_id, caption_or_filename)
        groups = defaultdict(lambda: defaultdict(list))
        processed_keys = set()

        chunk_size = 50
        last_update_time = 0

        for idx in range(0, len(total_range), chunk_size):
            batch_ids = total_range[idx:idx+chunk_size]
            try:
                msgs = await get_messages(target_client, batch_ids, chat_id=cid)
                msgs = [m for m in msgs if m]
                # Keep the exact order requested by the user, including descending ranges.
                requested_order = {message_id: pos for pos, message_id in enumerate(batch_ids)}
                msgs.sort(key=lambda m: requested_order.get(m.id, len(requested_order)))

                for m in msgs:
                    if not m or m.empty:
                        skipped_count += 1
                        continue

                    media = m.document or m.video or m.audio or m.animation
                    if not media:
                        skipped_count += 1
                        continue

                    caption = m.caption.html if (m.caption and hasattr(m.caption, "html")) else (m.caption or "")
                    filename = get_filename(m)

                    caption_cleaned = clean_emojis_and_html(caption)
                    filename_cleaned = clean_emojis_and_html(filename)

                    # Search BOTH filename AND file caption for anime name
                    if anime_names:
                        matched = False
                        combined_text = f"{caption_cleaned} {filename_cleaned}".lower()
                        for name in anime_names:
                            cleaned_name = name.lower().strip()
                            if cleaned_name in combined_text:
                                matched = True
                                break
                        if not matched:
                            skipped_count += 1
                            continue

                    # Universal Season, Episode, Part detection
                    season_cap, ep_cap, type_cap = parse_metadata_universal(caption_cleaned)
                    season_fn, ep_fn, type_fn = parse_metadata_universal(filename_cleaned)

                    season = season_cap if ep_cap is not None else season_fn
                    num_val = ep_cap if ep_cap is not None else ep_fn
                    num_type = type_cap if type_cap != 'unknown' else type_fn

                    quality = detect_quality(caption_cleaned)
                    if quality == "UNKNOWN":
                        quality = detect_quality(filename_cleaned)

                    ep_key = (season, num_val, num_type, quality)
                    if ep_key in processed_keys:
                        duplicate_count += 1
                        continue

                    processed_keys.add(ep_key)

                    caption_or_filename = caption.strip() if caption and caption.strip() else filename
                    groups[season][quality].append((num_val, num_type, m.id, caption_or_filename, filename, caption))
                    matched_count += 1


                scanned_count += len(batch_ids)

                now = time.time()
                if now - last_update_time >= 3.5:
                    last_update_time = now
                    elapsed = now - start_time
                    speed = round(scanned_count / elapsed, 1) if elapsed > 0 else 0
                    eta_secs = int((total_count - scanned_count) / speed) if speed > 0 else 0
                    eta_str = f"{eta_secs}s" if speed > 0 else "Calculating..."
                    percent = int((scanned_count / total_count) * 100) if total_count > 0 else 100
                    pbar = make_progressbar(percent)

                    progress_text = (
                        f"⏳ <b>Scanning Files...</b>\n"
                        f"{pbar} {percent}%\n\n"
                        f"• <b>Current Message:</b> <code>{batch_ids[-1]}</code>\n"
                        f"• <b>Anime Filter:</b> <code>{anime_disp}</code>\n"
                        f"• <b>Matched Files:</b> <code>{matched_count}</code>\n"
                        f"• <b>Skipped Files:</b> <code>{skipped_count}</code>\n"
                        f"• <b>Duplicates:</b> <code>{duplicate_count}</code>\n"
                        f"• <b>Speed:</b> <code>{speed} msgs/sec</code>\n"
                        f"• <b>ETA:</b> <code>{eta_str}</code>"
                    )
                    await edit_msg_safe(client, chat_id, msg_id, progress_text)


            except FloodWait as e:
                await asyncio.sleep(e.value)
                error_count += len(batch_ids)
            except Exception as ex:
                print(f"[SCAN CHUNK ERROR] {ex}")
                error_count += len(batch_ids)

        # Check if any matching files found
        if not groups:
            task['status'] = 'failed'
            await edit_msg_safe(
                client, chat_id, msg_id,
                f"⚠️ <b>No matching files were found in this range.</b>\n\n"
                f"• <b>Search Name:</b> <code>{anime_disp}</code>\n"
                f"• <b>Range:</b> <code>{start_id}-{end_id}</code>\n\n"
                f"<i>Please verify the anime name / range and try again.</i>"
            )
            return

        task['status'] = 'generating'
        await edit_msg_safe(
            client, chat_id, msg_id,
            f"🔗 <b>Batching matches and generating protected links...</b>\n\n"
            f"• <b>Total Matched:</b> {matched_count}\n"
            f"• <b>Queue Position:</b> Publishing..."
        )

        final_output_blocks = []
        total_generated_batches = 0

        for season in sorted(groups.keys()):
            qualities_dict = groups[season]

            if is_adv:
                target_qualities = ["480P", "720P", "1080P"]
            else:
                target_qualities = sorted(qualities_dict.keys(), key=lambda q: QUALITY_PRIORITY.get(q, 100))

            for q in target_qualities:
                files = qualities_dict.get(q, [])
                if files:
                    files.sort(key=lambda x: episode_sort_key(x[0]))

                    # Honor requested count limit on actual available matched files
                    if episode_limit < len(files):
                        files = files[:episode_limit]

                    mids = [f[2] for f in files]
                    link = await generate_list_link(target_client, cid, mids, bot_username=target_bot_username)

                    first_filename = files[0][4] if len(files[0]) > 4 and files[0][4] else "N/A"
                    first_caption = files[0][5] if len(files[0]) > 5 and files[0][5] else (files[0][3] or "N/A")
                    last_filename = files[-1][4] if len(files[-1]) > 4 and files[-1][4] else "N/A"
                    last_caption = files[-1][5] if len(files[-1]) > 5 and files[-1][5] else (files[-1][3] or "N/A")

                    block = (
                        f"🎬 <b>Quality: {q}</b>\n"
                        f"<b>First Filename:</b> {first_filename}\n"
                        f"<b>First Caption:</b> {first_caption}\n"
                        f"<b>Last Filename:</b> {last_filename}\n"
                        f"<b>Last Caption:</b> {last_caption}\n\n"
                        f"<b>Link:</b> <code>{link}</code>"
                    )
                    final_output_blocks.append(block)
                    total_generated_batches += 1
                elif is_adv:
                    final_output_blocks.append(f"<b>🎬 Quality: {q}</b>\n❌ <code>NOT FOUND</code>")

        # FIFO Output Serialization
        task['status'] = 'waiting_publish'
        async with AUTO_BATCH_PUBLISH_LOCKS[bot_username]:
            task['status'] = 'publishing'
            await edit_msg_safe(client, chat_id, msg_id, "🚀 <b>Publishing batch results to chat...</b>")

            if final_output_blocks:
                parts = split_blocks_into_parts(final_output_blocks)
                labeled = label_parts(parts)
                for part in labeled:
                    await client.send_message(chat_id, part)

            total_time = round(time.time() - start_time, 1)
            completion_text = (
                f"✅ <b>Auto Batch Task Completed!</b>\n\n"
                f"• <b>Anime:</b> <code>{anime_disp}</code>\n"
                f"• <b>Matched Files:</b> <code>{matched_count}</code>\n"
                f"• <b>Generated Batches:</b> <code>{total_generated_batches}</code>\n"
                f"• <b>Execution Time:</b> <code>{total_time}s</code>"
            )
            await edit_msg_safe(client, chat_id, msg_id, completion_text)

        task['status'] = 'completed'

    except Exception as e:
        task['status'] = 'failed'
        print(f"[RUN AUTO BATCH SCAN ERROR] {e}")
        await edit_msg_safe(
            client, chat_id, msg_id,
            f"⚠️ <b>Auto Batch Scan Completed with note:</b> `{e}`\n\n"
            f"<i>The bot remains active and stable.</i>"
        )


# Cancel active running auto_batch task
@Client.on_message(filters.private & filters.command(['cancel_batch', 'cancel_autobatch']))
async def cancel_batch_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        await message.reply_text(USER_REPLY_TEXT)
        return

    bot_username = (getattr(client, "username", "bot") or "bot").lower()
    active_task = AUTO_BATCH_ACTIVE_TASKS.get(bot_username)
    if active_task:
        asyncio_task = active_task.get('asyncio_task')
        if asyncio_task:
            asyncio_task.cancel()
            active_task['status'] = 'cancelled'
            await message.reply_text("✅ <b>Running Auto Batch task successfully cancelled!</b>")
            return

    if AUTO_BATCH_QUEUES[bot_username]:
        AUTO_BATCH_QUEUES[bot_username].clear()
        await message.reply_text("✅ <b>Cleared all queued Auto Batch tasks!</b>")
        return

    await message.reply_text("❌ <b>No running or queued Auto Batch task found to cancel.</b>")


@Client.on_callback_query(filters.regex(r"^(ab_start_|ab_cancel_wizard)"))
async def auto_batch_callbacks(client: Client, query: CallbackQuery):
    bot_username = (getattr(client, "username", "bot") or "bot").lower()
    admin_id = query.from_user.id

    if not await db.admin_exist(admin_id) and admin_id != config.OWNER_ID:
        await query.answer("❌ You are not authorized!", show_alert=True)
        return

    if query.data == "ab_cancel_wizard":
        await query.message.delete()
        await query.answer("Wizard cancelled.")
        return

    if query.data.startswith("ab_start_"):
        is_adv = query.data.endswith("_adv")
        wizard_confirm_id = query.data.replace("ab_start_", "")
        if is_adv:
            wizard_confirm_id = wizard_confirm_id[:-4]
        else:
            wizard_confirm_id = wizard_confirm_id[:-4]

        configured_results = state_manager.get_state(bot_username, wizard_confirm_id)
        if not configured_results:
            await query.answer("⚠️ Session expired! Please run the command again.", show_alert=True)
            await query.message.delete()
            return

        results = configured_results
        state_manager.clear_state(bot_username, wizard_confirm_id)

        await query.message.delete()
        await query.answer("🚀 Queueing Auto Batch Tasks...")

        for idx, item in enumerate(results, 1):
            task_id = f"ab_{uuid.uuid4().hex[:8]}_{idx}"
            prompt_msg = await query.message.reply_text(f"⏳ <b>Queueing Task {idx}/{len(results)}:</b> <code>{task_id}</code>...")

            task = {
                'task_id': task_id,
                'chat_id': query.message.chat.id,
                'admin_id': admin_id,
                'status': 'queued',
                'cid': item['cid'],
                'start_id': item['start_id'],
                'end_id': item['end_id'],
                'episode_count': item['episode_count'],
                'anime_names': item['anime_names'],
                'bot_username': item['bot_username'],
                'prompt_msg_id': prompt_msg.id,
                'is_adv': is_adv
            }

            AUTO_BATCH_QUEUES[bot_username].append(task)

        if not AUTO_BATCH_ACTIVE_TASKS.get(bot_username):
            asyncio.create_task(process_queue_worker(client, bot_username))

@Client.on_message(filters.private & filters.command(['serielbatch', 'serialbatch']))
async def serielbatch_command(client: Client, message: Message):
    if not await check_admin_or_owner(message):
        await message.reply_text(USER_REPLY_TEXT)
        return

    input_text = message.text or ""

    if message.reply_to_message:
        reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        input_text = f"/serielbatch\n{reply_text}"

    parsed_items = parse_mixed_inputs(input_text.replace("/serielbatch", "").replace("/serialbatch", ""))

    if not parsed_items:
        try:
            ask = await client.ask(
                message.chat.id,
                "<b>📌 Send the Range Link:</b>\n\n"
                "<i>Example:</i> <code>https://t.me/hsjisksjs/23961-https://t.me/hsjisksjs/24035</code>\n\n"
                "<i>Send /cancel to abort.</i>",
                filters=filters.text,
                timeout=120
            )
            if not ask.text or ask.text.strip().lower() == "/cancel":
                await ask.reply("❌ <b>Process Cancelled.</b>")
                return
            parsed_items = parse_mixed_inputs(ask.text)
        except asyncio.TimeoutError:
            await message.reply("⏰ <b>Timeout! Process Cancelled.</b>")
            return

    if not parsed_items:
        await message.reply_text("❌ <b>No valid ranges found in input. Please check the link format.</b>")
        return

    range_item = parsed_items[0]
    chan_ref = range_item.get('channel')
    start_id = range_item.get('start_id')
    end_id = range_item.get('end_id')

    try:
        ask_filter = await client.ask(
            message.chat.id,
            "<b>🔎 Send the Filter Name:</b>\n\n"
            "<i>Only messages containing media/files where this filter name is found in the filename or file caption will be generated.</i>\n"
            "<i>Type <code>.</code> to generate links for all media messages without filtering.</i>\n\n"
            "<i>Send /cancel to abort.</i>",
            filters=filters.text,
            timeout=120
        )
        if not ask_filter.text or ask_filter.text.strip().lower() == "/cancel":
            await ask_filter.reply("❌ <b>Process Cancelled.</b>")
            return
        filter_name = ask_filter.text.strip()
    except asyncio.TimeoutError:
        await message.reply("⏰ <b>Timeout! Process Cancelled.</b>")
        return

    filter_query = None if filter_name in [".", "..", "...", "-", "*"] else filter_name.lower()

    cid, bot_username, running_client = await resolve_db_source(client, chan_ref)
    from plugins.link_generator import extract_file_info
    from helper_func import get_bot_username

    actual_bot_un = bot_username or await get_bot_username(client)

    prog_msg = await message.reply_text("⏳ <b>Fetching messages and generating serial batch links...</b>")

    total_range = list(range(start_id, end_id + 1)) if start_id <= end_id else list(range(start_id, end_id - 1, -1))
    matched_count = 0
    chunk_size = 50
    output_blocks = []

    for idx in range(0, len(total_range), chunk_size):
        batch_ids = total_range[idx:idx+chunk_size]
        try:
            msgs = await get_messages(running_client, batch_ids, chat_id=cid)
            msgs = [m for m in msgs if m and not m.empty]
            # Keep the exact order requested by the user, including descending ranges.
            requested_order = {message_id: pos for pos, message_id in enumerate(batch_ids)}
            msgs.sort(key=lambda m: requested_order.get(m.id, len(requested_order)))

            for m in msgs:
                media = getattr(m, "document", None) or getattr(m, "video", None) or getattr(m, "audio", None) or getattr(m, "animation", None) or getattr(m, "photo", None) or getattr(m, "voice", None)
                if not media:
                    continue

                filename, filecaption = extract_file_info(m)

                if filter_query:
                    combined_text = f"{filename} {filecaption}".lower()
                    if filter_query not in combined_text:
                        continue

                converted_id = m.id * abs(cid)
                base64_str = await encode(f"get-{converted_id}")
                link = f"https://telegram.me/{actual_bot_un}?start={base64_str}"

                block = (
                    f"<b>First Filename:</b> {filename}\n"
                    f"<b>First Caption:</b> {filecaption}\n"
                    f"<b>Last Filename:</b> {filename}\n"
                    f"<b>Last Caption:</b> {filecaption}\n\n"
                    f"<b>Here is your link:</b>\n\n"
                    f"<code>{link}</code>"
                )

                output_blocks.append(block)
                matched_count += 1

        except FloodWait as fw:
            await asyncio.sleep(fw.value + 1)
        except Exception as e:
            print(f"[SERIELBATCH SCAN ERROR] {e}")

    if output_blocks:
        parts = split_blocks_into_parts(output_blocks, max_length=3800)
        labeled_parts = label_parts(parts)
        for part in labeled_parts:
            while True:
                try:
                    await message.reply_text(part, disable_web_page_preview=True)
                    break
                except FloodWait as fw:
                    await asyncio.sleep(fw.value + 1)
                except Exception as send_err:
                    print(f"[SERIELBATCH SEND ERROR] {send_err}")
                    break

    await prog_msg.edit_text(
        f"✅ <b>Serial Batch Link Generation Complete!</b>\n\n"
        f"• <b>Filter Name:</b> <code>{filter_name}</code>\n"
        f"• <b>Total Range:</b> <code>{start_id}-{end_id}</code>\n"
        f"• <b>Matched Links Generated:</b> <code>{matched_count}</code>"
    )
