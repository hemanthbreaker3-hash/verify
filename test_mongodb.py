import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from database.database import db, Rohit

class TestMongoDB(unittest.IsolatedAsyncioTestCase):

    async def test_update_config_and_get_config(self):
        mock_db = MagicMock()
        mock_settings = MagicMock()

        stored_data = {}

        async def mock_find_one(query):
            if query.get('_id') == 'bot_config':
                return {'_id': 'bot_config', 'data': stored_data}
            return None

        async def mock_update_one(filter_query, update_query, upsert=False):
            if filter_query.get('_id') == 'bot_config':
                if '$set' in update_query:
                    for k, v in update_query['$set'].items():
                        if k.startswith('data.'):
                            field = k.split('data.', 1)[1]
                            stored_data[field] = v
                if '$unset' in update_query:
                    for k in update_query['$unset'].keys():
                        if k.startswith('data.'):
                            field = k.split('data.', 1)[1]
                            stored_data.pop(field, None)
            return MagicMock()

        mock_settings.find_one = AsyncMock(side_effect=mock_find_one)
        mock_settings.update_one = AsyncMock(side_effect=mock_update_one)
        mock_db.__getitem__.return_value = mock_settings

        with patch.object(db, 'database', mock_db):
            # Test setting config key
            res = await db.update_config("BASE_URL", "https://customdomain.com")
            self.assertTrue(res)
            val = await db.get_config_val("BASE_URL")
            self.assertEqual(val, "https://customdomain.com")

            # Test setting another config key without overwriting
            await db.update_config("VERIFY_ENABLED", True)
            self.assertEqual(await db.get_config_val("BASE_URL"), "https://customdomain.com")
            self.assertEqual(await db.get_config_val("VERIFY_ENABLED"), True)

            # Test unsetting key by setting value to None
            await db.update_config("BASE_URL", None)
            self.assertIsNone(await db.get_config_val("BASE_URL"))
            self.assertEqual(await db.get_config_val("VERIFY_ENABLED"), True)

    async def test_set_del_timer_and_get_del_timer(self):
        mock_db = MagicMock()
        mock_del_timer = MagicMock()

        stored_timer = {}

        async def mock_find_one(query):
            if query.get('_id') == 'del_timer':
                return stored_timer if stored_timer else None
            return None

        async def mock_update_one(filter_query, update_query, upsert=False):
            if filter_query.get('_id') == 'del_timer':
                if '$set' in update_query:
                    stored_timer['_id'] = 'del_timer'
                    stored_timer['value'] = update_query['$set']['value']
            return MagicMock()

        mock_del_timer.find_one = AsyncMock(side_effect=mock_find_one)
        mock_del_timer.update_one = AsyncMock(side_effect=mock_update_one)
        mock_db.__getitem__.return_value = mock_del_timer

        test_rohit = Rohit(None, None)
        test_rohit.database = mock_db
        test_rohit.del_timer_data = mock_del_timer

        res = await test_rohit.set_del_timer(300)
        self.assertTrue(res)

        timer_val = await test_rohit.get_del_timer()
        self.assertEqual(timer_val, 300)

    async def test_admin_operations(self):
        mock_db = MagicMock()
        mock_admins = MagicMock()

        admin_docs = []

        async def mock_find_one(query):
            for doc in admin_docs:
                if doc['_id'] == query.get('_id'):
                    return doc
            return None

        async def mock_insert_one(doc):
            admin_docs.append(doc)
            return MagicMock()

        async def mock_delete_one(query):
            nonlocal admin_docs
            admin_docs = [d for d in admin_docs if d['_id'] != query.get('_id')]
            return MagicMock()

        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(side_effect=lambda length: admin_docs)
        mock_admins.find.return_value = mock_cursor
        mock_admins.find_one = AsyncMock(side_effect=mock_find_one)
        mock_admins.insert_one = AsyncMock(side_effect=mock_insert_one)
        mock_admins.delete_one = AsyncMock(side_effect=mock_delete_one)

        test_rohit = Rohit(None, None)
        test_rohit.database = mock_db
        test_rohit.admins_data = mock_admins

        # Add admin with 7-digit ID (e.g. 1234567)
        self.assertFalse(await test_rohit.admin_exist(1234567))
        await test_rohit.add_admin(1234567)
        self.assertTrue(await test_rohit.admin_exist(1234567))

        all_admins = await test_rohit.get_all_admins()
        self.assertIn(1234567, all_admins)

        # Delete admin
        await test_rohit.del_admin(1234567)
        self.assertFalse(await test_rohit.admin_exist(1234567))

    async def test_export_backup_and_restore(self):
        import zipfile, os
        from bson import json_util

        mock_db = MagicMock()
        collections_data = {
            'admins': [{'_id': 101}, {'_id': 102}],
            'settings': [{'_id': 'bot_config', 'data': {'BASE_URL': 'https://test.com'}}]
        }

        async def mock_list_collections():
            return list(collections_data.keys())

        mock_db.list_collection_names = AsyncMock(side_effect=mock_list_collections)

        def mock_getitem(coll_name):
            mock_coll = MagicMock()
            async def mock_find_to_list(length=None):
                return collections_data.get(coll_name, [])
            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(side_effect=mock_find_to_list)
            mock_coll.find.return_value = mock_cursor

            restored_docs = []
            async def mock_delete_many(query):
                restored_docs.clear()
                return MagicMock()

            async def mock_insert_many(docs):
                restored_docs.extend(docs)
                return MagicMock()

            mock_coll.delete_many = AsyncMock(side_effect=mock_delete_many)
            mock_coll.insert_many = AsyncMock(side_effect=mock_insert_many)
            mock_coll._restored = restored_docs
            return mock_coll

        mock_db.__getitem__.side_effect = mock_getitem

        test_rohit = Rohit(None, None)
        test_rohit.database = mock_db

        # Test Export
        zip_file = await test_rohit.export_backup_zip("test_backup.zip")
        self.assertIsNotNone(zip_file)
        self.assertTrue(os.path.exists(zip_file))

        with zipfile.ZipFile(zip_file, 'r') as z:
            names = z.namelist()
            self.assertIn("admins.json", names)
            self.assertIn("settings.json", names)

        # Test Restore
        success = await test_rohit.restore_from_zip(zip_file)
        self.assertTrue(success)

        try:
            os.remove(zip_file)
        except Exception:
            pass

if __name__ == "__main__":
    unittest.main()
