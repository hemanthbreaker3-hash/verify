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

import motor, asyncio
import motor.motor_asyncio
import time
import os
from config import DB_URI, DB_NAME
import logging
from datetime import datetime, timedelta, timezone
from functools import wraps

logging.basicConfig(level=logging.INFO)

def connection_check(default_return=None):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            uri = DB_URI or os.environ.get("DATABASE_URL", "")
            name = DB_NAME or os.environ.get("DB_NAME", "AniZoneFlix")

            if self.database is None and uri and name:
                try:
                    self.dbclient = motor.motor_asyncio.AsyncIOMotorClient(uri, serverSelectionTimeoutMS=8000, connectTimeoutMS=8000, retryWrites=True)
                    self.database = self.dbclient[name]
                    self._init_collections()
                except Exception as re_err:
                    logging.error(f"Error reconnecting Motor in {func.__name__}: {re_err}")

            if self.database is None:
                logging.error(f"Database not connected. Failed to execute {func.__name__}")
                return default_return

            try:
                return await func(self, *args, **kwargs)
            except Exception as e:
                err_msg = str(e)
                if "Event loop is closed" in err_msg or "attached to a different loop" in err_msg or "closed" in err_msg:
                    if uri and name:
                        try:
                            old_client = self.dbclient
                            self.dbclient = motor.motor_asyncio.AsyncIOMotorClient(uri, serverSelectionTimeoutMS=8000, connectTimeoutMS=8000, retryWrites=True)
                            if old_client is not None:
                                old_client.close()
                            self.database = self.dbclient[name]
                            self._init_collections()
                            return await func(self, *args, **kwargs)
                        except Exception as retry_err:
                            logging.error(f"Error retrying Motor after reconnect in {func.__name__}: {retry_err}")
                logging.error(f"Error in {func.__name__}: {e}")
                return default_return
        return wrapper
    return decorator

class Rohit:

    def __init__(self, DB_URI, DB_NAME):
        try:
            self.dbclient = motor.motor_asyncio.AsyncIOMotorClient(DB_URI, serverSelectionTimeoutMS=8000, connectTimeoutMS=8000, retryWrites=True) if DB_URI else None
            self.database = self.dbclient[DB_NAME] if self.dbclient and DB_NAME else None
        except Exception as e:
            logging.error(f"Error connecting to Motor: {e}")
            self.dbclient = None
            self.database = None

        self._init_collections()

    def _init_collections(self):
        if self.database is not None:
            self.channel_data = self.database['channels']
            self.admins_data = self.database['admins']
            self.user_data = self.database['users']
            self.banned_user_data = self.database['banned_user']
            self.autho_user_data = self.database['autho_user']
            self.del_timer_data = self.database['del_timer']
            self.fsub_data = self.database['fsub']
            self.rqst_fsub_data = self.database['request_forcesub']
            self.rqst_fsub_Channel_data = self.database['request_forcesub_channel']
        else:
            self.channel_data = None
            self.admins_data = None
            self.user_data = None
            self.banned_user_data = None
            self.autho_user_data = None
            self.del_timer_data = None
            self.fsub_data = None
            self.rqst_fsub_data = None
            self.rqst_fsub_Channel_data = None


    @connection_check(default_return=False)
    async def present_user(self, user_id: int):
        found = await self.user_data.find_one({'_id': user_id})
        return bool(found)

    @connection_check(default_return=False)
    async def add_user(self, user_id: int):
        await self.user_data.insert_one({'_id': user_id})
        return True

    @connection_check(default_return=[])
    async def full_userbase(self):
        user_docs = await self.user_data.find().to_list(length=None)
        user_ids = [doc['_id'] for doc in user_docs]
        return user_ids

    @connection_check(default_return=False)
    async def del_user(self, user_id: int):
        await self.user_data.delete_one({'_id': user_id})
        return True


    @connection_check(default_return=False)
    async def admin_exist(self, admin_id: int):
        found = await self.admins_data.find_one({'_id': admin_id})
        return bool(found)

    @connection_check(default_return=False)
    async def add_admin(self, admin_id: int):
        if not await self.admin_exist(admin_id):
            await self.admins_data.insert_one({'_id': admin_id})
        return True

    @connection_check(default_return=False)
    async def del_admin(self, admin_id: int):
        if await self.admin_exist(admin_id):
            await self.admins_data.delete_one({'_id': admin_id})
        return True

    @connection_check(default_return=[])
    async def get_all_admins(self):
        users_docs = await self.admins_data.find().to_list(length=None)
        user_ids = [doc['_id'] for doc in users_docs]
        return user_ids


    @connection_check(default_return=False)
    async def ban_user_exist(self, user_id: int):
        found = await self.banned_user_data.find_one({'_id': user_id})
        return bool(found)

    @connection_check(default_return=False)
    async def add_ban_user(self, user_id: int):
        if not await self.ban_user_exist(user_id):
            await self.banned_user_data.insert_one({'_id': user_id})
        return True

    @connection_check(default_return=False)
    async def del_ban_user(self, user_id: int):
        if await self.ban_user_exist(user_id):
            await self.banned_user_data.delete_one({'_id': user_id})
        return True

    @connection_check(default_return=[])
    async def get_ban_users(self):
        users_docs = await self.banned_user_data.find().to_list(length=None)
        user_ids = [doc['_id'] for doc in users_docs]
        return user_ids



    @connection_check(default_return=False)
    async def set_del_timer(self, value: int):        
        await self.del_timer_data.update_one(
            {'_id': 'del_timer'},
            {'$set': {'value': int(value)}},
            upsert=True
        )
        return True

    @connection_check(default_return=0)
    async def get_del_timer(self):
        data = await self.del_timer_data.find_one({'_id': 'del_timer'})
        if not data:
            data = await self.del_timer_data.find_one({})
        if data:
            return data.get('value', 0)
        return 0


    @connection_check(default_return=False)
    async def channel_exist(self, channel_id: int):
        found = await self.fsub_data.find_one({'_id': channel_id})
        return bool(found)

    @connection_check(default_return=False)
    async def add_channel(self, channel_id: int):
        if not await self.channel_exist(channel_id):
            await self.fsub_data.insert_one({'_id': channel_id})
        return True

    @connection_check(default_return=False)
    async def rem_channel(self, channel_id: int):
        if await self.channel_exist(channel_id):
            await self.fsub_data.delete_one({'_id': channel_id})
        return True

    async def del_channel(self, channel_id: int):
        return await self.rem_channel(channel_id)

    @connection_check(default_return=[])
    async def show_channels(self):
        channel_docs = await self.fsub_data.find().to_list(length=None)
        channel_ids = [doc['_id'] for doc in channel_docs]
        return channel_ids

    
    @connection_check(default_return="off")
    async def get_channel_mode(self, channel_id: int):
        data = await self.fsub_data.find_one({'_id': channel_id})
        return data.get("mode", "off") if data else "off"

    @connection_check(default_return=False)
    async def set_channel_mode(self, channel_id: int, mode: str):
        await self.fsub_data.update_one(
            {'_id': int(channel_id)},
            {'$set': {'mode': mode}},
            upsert=True
        )
        return True


    @connection_check(default_return=False)
    async def req_user(self, channel_id: int, user_id: int):
        await self.rqst_fsub_Channel_data.update_one(
            {'_id': int(channel_id)},
            {'$addToSet': {'user_ids': int(user_id)}},
            upsert=True
        )
        return True


    @connection_check(default_return=False)
    async def del_req_user(self, channel_id: int, user_id: int):
        await self.rqst_fsub_Channel_data.update_one(
            {'_id': int(channel_id)},
            {'$pull': {'user_ids': int(user_id)}}
        )
        return True

    @connection_check(default_return=False)
    async def req_user_exist(self, channel_id: int, user_id: int):
        found = await self.rqst_fsub_Channel_data.find_one({
            '_id': int(channel_id),
            'user_ids': int(user_id)
        })
        return bool(found)


    async def reqChannel_exist(self, channel_id: int):
        channel_ids = await self.show_channels()

        if channel_id in channel_ids:
            return True
        else:
            return False

    @connection_check(default_return=True)
    async def get_retrieve_status(self):
        data = await self.database['settings'].find_one({'_id': 'retrieve_status'})
        if data:
            return data.get('value', True)
        return True

    @connection_check(default_return=False)
    async def set_retrieve_status(self, value: bool):
        await self.database['settings'].update_one(
            {'_id': 'retrieve_status'},
            {'$set': {'value': value}},
            upsert=True
        )
        return True


    # ==================== Admin Custom Images Manager ====================
    @connection_check(default_return=[])
    async def get_admin_images(self):
        doc = await self.database['settings'].find_one({'_id': 'admin_images'})
        urls = doc.get('urls', []) if (doc and isinstance(doc.get('urls'), list)) else []
        self.ADMIN_IMAGES_CACHE = urls
        return urls

    @connection_check(default_return=False)
    async def add_admin_images(self, urls: list):
        current = await self.get_admin_images()
        updated = list(current)
        for u in urls:
            u_clean = str(u).strip()
            if u_clean and u_clean not in updated:
                updated.append(u_clean)
        await self.database['settings'].update_one(
            {'_id': 'admin_images'},
            {'$set': {'urls': updated}},
            upsert=True
        )
        self.ADMIN_IMAGES_CACHE = updated
        return True

    @connection_check(default_return=False)
    async def delete_admin_image(self, url: str):
        current = await self.get_admin_images()
        updated = [u for u in current if u != url.strip()]
        await self.database['settings'].update_one(
            {'_id': 'admin_images'},
            {'$set': {'urls': updated}},
            upsert=True
        )
        self.ADMIN_IMAGES_CACHE = updated
        return True

    @connection_check(default_return=False)
    async def clear_admin_images(self):
        await self.database['settings'].update_one(
            {'_id': 'admin_images'},
            {'$set': {'urls': []}},
            upsert=True
        )
        self.ADMIN_IMAGES_CACHE = []
        return True

    # ==================== Dynamic Configuration & Settings Methods ====================
    @connection_check(default_return={})
    async def get_config(self):
        doc = await self.database['settings'].find_one({'_id': 'bot_config'})
        return doc.get('data', {}) if doc and isinstance(doc.get('data'), dict) else {}

    @connection_check(default_return=False)
    async def update_config(self, key: str, value):
        if key == 'BASE_URL' and value is not None:
            from urllib.parse import urlsplit, urlunsplit
            value = str(value).strip().rstrip('/')
            if not value.startswith(('https://', 'http://')):
                value = 'https://' + value
            parsed = urlsplit(value)
            if not parsed.netloc or parsed.scheme not in ('http', 'https'):
                raise ValueError('BASE_URL must be a valid http(s) URL')
            value = urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), '', '')).rstrip('/')
        if value is None:
            result = await self.database['settings'].update_one(
                {'_id': 'bot_config'}, {'$unset': {f'data.{key}': ""}}, upsert=True
            )
        else:
            result = await self.database['settings'].update_one(
                {'_id': 'bot_config'}, {'$set': {f'data.{key}': value}}, upsert=True
            )
        return bool(result.acknowledged)

    @connection_check(default_return=None)
    async def get_config_val(self, key: str, default=None):
        config = await self.get_config()
        if key == 'BASE_URL' and not config.get(key):
            return (os.environ.get('BASE_URL') or default)
        return config.get(key, default)

    # ==================== Shortener Manager ====================
    @connection_check(default_return=[])
    async def get_shorteners(self):
        docs = await self.database['shorteners'].find().to_list(length=None)
        return docs

    @connection_check(default_return=False)
    async def add_shortener(self, domain: str, api_key: str, method: str = "default", priority: int = 1):
        shortener_id = str(int(time.time() * 1000))
        await self.database['shorteners'].insert_one({
            '_id': shortener_id,
            'domain': domain,
            'api_key': api_key,
            'method': method,
            'priority': priority,
            'enabled': True,
            # Each shortener has an independent Referer-enforcement switch.
            # Default OFF to avoid breaking providers/browsers that omit Referer.
            'referer_enabled': False
        })
        return shortener_id

    @connection_check(default_return=False)
    async def update_shortener(self, shortener_id: str, updates: dict):
        await self.database['shorteners'].update_one({'_id': shortener_id}, {'$set': updates})
        return True

    @connection_check(default_return=False)
    async def delete_shortener(self, shortener_id: str):
        await self.database['shorteners'].delete_one({'_id': shortener_id})
        return True

    # ==================== DB Channels Manager (DB channels store) ====================
    @connection_check(default_return=[])
    async def get_db_channels(self):
        docs = await self.database['db_channels'].find().to_list(length=None)
        return [doc['_id'] for doc in docs]

    @connection_check(default_return=False)
    async def add_db_channel(self, channel_id: int):
        await self.database['db_channels'].update_one({'_id': int(channel_id)}, {'$set': {'_id': int(channel_id)}}, upsert=True)
        return True

    @connection_check(default_return=False)
    async def remove_db_channel(self, channel_id: int):
        await self.database['db_channels'].delete_one({'_id': int(channel_id)})
        return True

    # ==================== Clone Bot Manager ====================
    @connection_check(default_return=[])
    async def get_all_clones(self):
        docs = await self.database['clones'].find().to_list(length=None)
        return docs

    @connection_check(default_return=None)
    async def get_clone(self, bot_username: str):
        return await self.database['clones'].find_one({'bot_username': bot_username.replace('@', '').strip()})

    @connection_check(default_return=False)
    async def add_clone(self, bot_username: str, bot_token: str, db_channel_id: int):
        username = bot_username.replace('@', '').strip()
        doc = {
            'bot_username': username,
            'bot_token': bot_token.strip(),
            'db_channel_id': int(db_channel_id),
            'enabled': True,
            'created_at': datetime.utcnow().isoformat()
        }
        await self.database['clones'].update_one(
            {'bot_username': username},
            {'$set': doc},
            upsert=True
        )
        return True

    @connection_check(default_return=False)
    async def update_clone(self, bot_username: str, updates: dict):
        username = bot_username.replace('@', '').strip()
        await self.database['clones'].update_one({'bot_username': username}, {'$set': updates})
        return True

    @connection_check(default_return=False)
    async def delete_clone(self, bot_username: str):
        username = bot_username.replace('@', '').strip()
        await self.database['clones'].delete_one({'bot_username': username})
        return True

    # ==================== Verification Session Token Store ====================
    @connection_check(default_return=False)
    async def save_verify_token(self, token: str, user_id: int, payload: str, expiry_seconds: int = 0):
        now = datetime.utcnow()
        expiry = max(60, int(expiry_seconds or 3000))
        await self.database['verify_tokens'].update_one(
            {'_id': token},
            {'$set': {
                'user_id': int(user_id), 'payload': payload, 'created_at': now,
                'expires_at': now + timedelta(seconds=expiry), 'verified': False,
                'cached_shortlink': None, 'selected_shortener_id': None,
                'web_verified': False
            }},
            upsert=True
        )
        return True

    @connection_check(default_return=None)
    async def get_verify_token(self, token: str):
        import base64, re
        doc = None
        if self.database is not None:
            try:
                doc = await self.database['verify_tokens'].find_one({'_id': token})
            except Exception:
                doc = None

        if doc:
            # The browser step and Telegram deep-link step are one flow. Do not
            # invalidate a token until the user returns to Telegram; enforce the
            # configured session expiry on every request.
            if doc.get('verified', False):
                return None
            now = datetime.utcnow()
            expires_at = doc.get('expires_at')
            if expires_at:
                if getattr(expires_at, 'tzinfo', None) is not None:
                    expires_at = expires_at.replace(tzinfo=None)
                if now > expires_at:
                    return None
            else:
                created_at = doc.get('created_at')
                if created_at:
                    if getattr(created_at, 'tzinfo', None) is not None:
                        created_at = created_at.replace(tzinfo=None)
                    # Legacy records retain the previous ten-minute lifetime.
                    if (now - created_at).total_seconds() > 600:
                        return None
            return doc

        # Fallback decode self-contained token format so Render cold starts/restarts never fail with 404/expired
        try:
            m = re.search(r'(\d+)_sb_', token)
            uid = int(m.group(1)) if m else 0

            decoded_payload = None

            if '/' in token:
                parts = token.split('/')
                if len(parts) > 1:
                    part1 = parts[1]
                    if '.' in part1:
                        candidate_hex = part1.split('.')[0]
                        try:
                            decoded = bytes.fromhex(candidate_hex).decode('utf-8')
                            if decoded:
                                decoded_payload = decoded
                        except Exception:
                            pass

            if not decoded_payload:
                subparts = re.split(r'[/_.]', token)
                for part in subparts:
                    if not part or len(part) < 4:
                        continue
                    try:
                        dec = bytes.fromhex(part).decode('utf-8')
                        if dec and dec.isprintable():
                            decoded_payload = dec
                            break
                    except Exception:
                        pass
                    try:
                        padded = part + '=' * (-len(part) % 4)
                        dec = base64.urlsafe_b64decode(padded.encode()).decode('utf-8')
                        if dec and dec.isprintable():
                            decoded_payload = dec
                            break
                    except Exception:
                        pass

            if uid > 0 and decoded_payload:
                return {'_id': token, 'user_id': uid, 'payload': decoded_payload}
        except Exception:
            pass

        return None

    @connection_check(default_return=False)
    async def update_verify_token(self, token: str, updates: dict):
        result = await self.database['verify_tokens'].update_one({'_id': token}, {'$set': updates})
        return bool(result.acknowledged)

    @connection_check(default_return=False)
    async def mark_verify_token_used(self, token: str):
        await self.database['verify_tokens'].update_one({'_id': token}, {'$set': {'verified': True}})
        return True

    @connection_check(default_return=False)
    async def is_user_verified(self, user_id: int, bot_client=None):
        doc = await self.database['verified_users'].find_one({'_id': int(user_id)})
        if not doc:
            return False
        expiry = doc.get('expire_at')
        if expiry and datetime.utcnow() > expiry:
            await self.database['verified_users'].delete_one({'_id': int(user_id)})
            if bot_client:
                try:
                    await bot_client.send_message(
                        chat_id=int(user_id),
                        text=(
                            f"<b>⚠️ YOUR VERIFICATION HAS EXPIRED!</b>\n\n"
                            f"Your verified access period has ended. Please verify again using /verify to restore instant access."
                        )
                    )
                except Exception:
                    pass
            return False
        return True

    @connection_check(default_return=None)
    async def get_verified_user(self, user_id: int):
        return await self.database['verified_users'].find_one({'_id': user_id})

    @connection_check(default_return=False)
    async def set_user_verified(self, user_id: int, duration_seconds: int = 86400, username: str = "", first_name: str = ""):
        expire_at = datetime.utcnow() + timedelta(seconds=duration_seconds)
        doc = {
            'expire_at': expire_at,
            'verified_at': datetime.utcnow()
        }
        if username:
            doc['username'] = username
        if first_name:
            doc['first_name'] = first_name

        await self.database['verified_users'].update_one(
            {'_id': user_id},
            {'$set': doc},
            upsert=True
        )
        return True



    @connection_check(default_return=False)
    async def reset_all_verified_users(self):
        await self.database['verified_users'].delete_many({})
        return True

    @connection_check(default_return=0)
    async def reset_verified_users(self, user_ids: list):
        res = await self.database['verified_users'].delete_many({'_id': {'$in': [int(uid) for uid in user_ids if str(uid).isdigit()]}})
        return res.deleted_count


    # ==================== Premium & Time Compensation System ====================
    @connection_check(default_return=False)
    async def add_premium_user(self, user_id: int, username: str, duration_seconds: int):
        from zoneinfo import ZoneInfo
        now_utc = datetime.now(timezone.utc)
        expire_at_utc = now_utc + timedelta(seconds=duration_seconds)
        doc = {
            '_id': int(user_id),
            'username': username or "",
            'start_at': now_utc,
            'expire_at': expire_at_utc,
            'created_at': now_utc
        }
        await self.database['premium_users'].update_one(
            {'_id': int(user_id)},
            {'$set': doc},
            upsert=True
        )
        return True

    @connection_check(default_return=False)
    async def del_premium_user(self, user_id_or_username):
        query = {}
        if str(user_id_or_username).isdigit():
            query = {'_id': int(user_id_or_username)}
        else:
            un = str(user_id_or_username).replace('@', '').strip().lower()
            query = {'username': {'$regex': f"^{un}$", '$options': 'i'}}
        res = await self.database['premium_users'].delete_one(query)
        return res.deleted_count > 0

    @connection_check(default_return=False)
    async def is_premium_user(self, user_id: int, bot_client=None):
        doc = await self.database['premium_users'].find_one({'_id': int(user_id)})
        if not doc:
            return False
        exp = doc.get('expire_at')
        if exp:
            if hasattr(exp, 'tzinfo') and exp.tzinfo is not None:
                exp = exp.replace(tzinfo=None)
            now = datetime.utcnow()
            if now > exp:
                await self.database['premium_users'].delete_one({'_id': int(user_id)})
                if bot_client:
                    try:
                        await bot_client.send_message(
                            chat_id=int(user_id),
                            text=(
                                f"<b>⚠️ YOUR PREMIUM STATUS HAS EXPIRED!</b>\n\n"
                                f"Your premium access period has ended. Contact support to renew your premium access anytime."
                            )
                        )
                    except Exception:
                        pass
                return False
        return True

    @connection_check(default_return=None)
    async def check_and_notify_expirations(self, bot_client):
        if self.database is None or not bot_client:
            return

        now = datetime.utcnow()

        expired_verified = await self.database['verified_users'].find({'expire_at': {'$lt': now}}).to_list(length=None)
        for u in expired_verified:
            uid = u['_id']
            await self.database['verified_users'].delete_one({'_id': uid})
            try:
                await bot_client.send_message(
                    chat_id=uid,
                    text=(
                        f"<b>⚠️ YOUR VERIFICATION HAS EXPIRED!</b>\n\n"
                        f"Your verified access period has ended. Please verify again using /verify to restore instant access."
                    )
                )
            except Exception:
                pass

        expired_premium = await self.database['premium_users'].find({'expire_at': {'$lt': now}}).to_list(length=None)
        for p in expired_premium:
            puid = p['_id']
            await self.database['premium_users'].delete_one({'_id': puid})
            try:
                await bot_client.send_message(
                    chat_id=puid,
                    text=(
                        f"<b>⚠️ YOUR PREMIUM STATUS HAS EXPIRED!</b>\n\n"
                        f"Your premium access period has ended. Contact support to renew your premium access anytime."
                    )
                )
            except Exception:
                pass

    @connection_check(default_return=[])
    async def get_all_premium_users(self):
        docs = await self.database['premium_users'].find().to_list(length=None)
        return docs

    @connection_check(default_return=[])
    async def get_all_verified_users(self):
        docs = await self.database['verified_users'].find().to_list(length=None)
        return docs

    @connection_check(default_return=False)
    async def apply_downtime_compensation(self, downtime_seconds: int):
        if downtime_seconds <= 0:
            return False
        # Extend active verified users
        verified = await self.get_all_verified_users()
        now = datetime.utcnow()
        for u in verified:
            exp = u.get('expire_at')
            if exp:
                if hasattr(exp, 'tzinfo') and exp.tzinfo is not None:
                    exp = exp.replace(tzinfo=None)
                if exp > now:
                    new_exp = exp + timedelta(seconds=downtime_seconds)
                    await self.database['verified_users'].update_one(
                        {'_id': u['_id']},
                        {'$set': {'expire_at': new_exp}}
                    )

        # Extend active premium users
        premiums = await self.get_all_premium_users()
        for p in premiums:
            exp = p.get('expire_at')
            if exp:
                if hasattr(exp, 'tzinfo') and exp.tzinfo is not None:
                    exp = exp.replace(tzinfo=None)
                if exp > now:
                    new_exp = exp + timedelta(seconds=downtime_seconds)
                    await self.database['premium_users'].update_one(
                        {'_id': p['_id']},
                        {'$set': {'expire_at': new_exp}}
                    )
        return True

    # ==================== Backup & Restore Methods ====================
    @connection_check(default_return=None)
    async def export_backup_zip(self, zip_filename: str = "backup_anizoneflix.zip"):
        import json, zipfile, tempfile
        from bson import json_util

        if self.database is None:
            return None

        collections = await self.database.list_collection_names()
        temp_dir = tempfile.mkdtemp()
        zip_filepath = os.path.join(temp_dir, zip_filename)

        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for coll_name in collections:
                docs = await self.database[coll_name].find().to_list(length=None)
                json_data = json_util.dumps(docs, indent=2)
                zipf.writestr(f"{coll_name}.json", json_data)

        return zip_filepath

    @connection_check(default_return=False)
    async def restore_from_zip(self, zip_filepath: str):
        import json, zipfile
        from bson import json_util

        if self.database is None:
            return False

        if not os.path.exists(zip_filepath) or not zipfile.is_zipfile(zip_filepath):
            return False

        with zipfile.ZipFile(zip_filepath, 'r') as zipf:
            for file_info in zipf.infolist():
                if file_info.filename.endswith('.json'):
                    coll_name = os.path.basename(file_info.filename)[:-5]
                    content = zipf.read(file_info.filename).decode('utf-8')
                    docs = json_util.loads(content)
                    # Merge backup records instead of wiping the live collection.
                    # This prevents partial/old backups from erasing newer users or settings.
                    if isinstance(docs, list) and coll_name and not coll_name.startswith('system.'):
                        collection = self.database[coll_name]
                        for document in docs:
                            if not isinstance(document, dict):
                                continue
                            doc_id = document.get('_id')
                            if doc_id is None:
                                await collection.insert_one(document)
                            else:
                                await collection.replace_one({'_id': doc_id}, document, upsert=True)

        return True

db = Rohit(DB_URI, DB_NAME)

# =====================================================================================##
#                         ✨ MADE BY ANIZONEFLIX ✨
#                  Join Updates Channel: https://t.me/anizoneflix
#====================================================================================##
