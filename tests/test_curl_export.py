import json
import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.helpers import load_weread_bot


BOOK = {
    "name": "测试书",
    "book_id": "book_id_1234567890",
    "chapters": [{"chapter_id": "chapter_id_1234567890", "chapter_index": 3}],
}


def _browser_curl(skey="old_skey_123456", book="cbook_123456789", sm="it's"):
    data = {
        "appId": "wb1234h5678", "b": book, "c": "cchap_123456789", "ci": 7,
        "co": 120, "sm": sm, "pr": 4, "rt": 30, "ps": "ps_value_1",
        "pc": "pc_value_1", "ts": 1, "rn": 2, "sg": "x", "s": "y",
    }
    return (
        "curl 'https://weread.qq.com/web/book/read' \\\n"
        "  -H 'accept: application/json' \\\n"
        "  -H 'user-agent: Mozilla/5.0 Test' \\\n"
        f"  -H 'cookie: wr_vid=1; wr_skey={skey}; wr_rt=rt' \\\n"
        f"  --data-raw '{json.dumps(data).replace(chr(39), chr(92) + 'u0027')}'"
    )


class BooksEnvTests(unittest.TestCase):
    def setUp(self):
        self.bot = load_weread_bot()
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def _load(self, env_value):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"WEREAD_BOOKS": env_value}):
                return self.bot.ConfigManager(
                    str(Path(temp_dir) / "missing.yaml")
                ).config

    def test_weread_books_env_loads_json_list(self):
        config = self._load(json.dumps([BOOK]))
        book = config.reading.books[0]
        self.assertEqual(book.book_id, "book_id_1234567890")
        self.assertEqual(book.chapter_infos[0].chapter_index, 3)

    def test_weread_books_env_rejects_invalid_json(self):
        for value in ("not json", json.dumps(BOOK)):
            with self.subTest(value=value):
                with self.assertRaises(self.bot.ConfigError):
                    self._load(value)


class CurlExportTests(unittest.TestCase):
    def setUp(self):
        self.bot = load_weread_bot()
        logging.disable(logging.CRITICAL)
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()
        logging.disable(logging.NOTSET)

    def _manager(self, content, user="u1"):
        bot = self.bot
        config = bot.WeReadConfig(
            users=[bot.UserConfig(name=user, content=content)],
            human_simulation=bot.HumanSimulationConfig(rotate_user_agent=True),
        )
        return config, bot.WeReadSessionManager(config, config.users[0])

    def test_export_keeps_renewed_cookie_identity_and_position(self):
        bot = self.bot
        _, manager = self._manager(_browser_curl())
        manager.cookies["wr_skey"] = "new_skey_654321"
        manager.headers["user-agent"] = "rotated"

        headers, cookies, data = bot.CurlParser.parse_curl_command(
            manager.export_curl_command()
        )

        self.assertEqual(cookies["wr_skey"], "new_skey_654321")
        self.assertEqual(cookies["wr_rt"], "rt")
        self.assertEqual(headers["user-agent"], "Mozilla/5.0 Test")
        self.assertEqual(data["b"], "cbook_123456789")
        # 导出与会话中实际发送的章节索引一致
        self.assertEqual(data["ci"], manager.reading_manager.current_chapter_ci)
        self.assertEqual(data["sm"], "it's")
        self.assertEqual((data["ps"], data["pc"]), ("ps_value_1", "pc_value_1"))
        for volatile in ("ts", "rn", "sg", "s", "rt"):
            self.assertNotIn(volatile, data)

    def test_save_writes_users_in_config_order_and_keeps_missing(self):
        bot = self.bot
        config = bot.WeReadConfig(users=[
            bot.UserConfig(name="a", content=_browser_curl("a_skey_1234567")),
            bot.UserConfig(name="b", content=_browser_curl("b_skey_1234567")),
        ])
        exports = {"b": (_browser_curl("b_new_skey_123"), True)}
        path = self.dir / "out" / "curl.txt"

        self.assertTrue(bot.save_curl_exports(config, exports, path))

        with patch.dict(os.environ, {"WEREAD_CURL_STRING": path.read_text("utf-8")}):
            users = bot.ConfigManager(str(self.dir / "none.yaml")).config.users
        skeys = [
            bot.CurlParser.parse_curl_command(u.content)[1]["wr_skey"]
            for u in users
        ]
        self.assertEqual(skeys, ["a_skey_1234567", "b_new_skey_123"])

    def test_save_skips_when_no_cookie_renewed(self):
        bot = self.bot
        config = bot.WeReadConfig(users=[bot.UserConfig(name="a", content="x")])
        path = self.dir / "curl.txt"
        self.assertFalse(
            bot.save_curl_exports(config, {"a": ("curl", False)}, path)
        )
        self.assertFalse(path.exists())


class SaveCurlFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_single_session_saves_after_multi_user_run(self):
        bot = load_weread_bot()
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "curl.txt"
            config = bot.WeReadConfig(
                users=[bot.UserConfig(name="a", content=_browser_curl())],
                history=bot.HistoryConfig(enabled=False),
            )
            app = bot.WeReadApplication(config, save_curl_path=str(path))

            async def fake_session(manager):
                manager.cookies["wr_skey"] = "renewed_skey_99"
                manager.cookie_renewed = True
                return bot.SessionResult(
                    bot.SessionStatus.SUCCESS, manager.session_stats
                )

            with patch.object(
                bot.WeReadSessionManager, "start_reading_session", fake_session
            ):
                await bot.WeReadApplication.run_single_session()
            del app
            _, cookies, _ = bot.CurlParser.parse_curl_command(
                path.read_text("utf-8")
            )
        self.assertEqual(cookies["wr_skey"], "renewed_skey_99")


if __name__ == "__main__":
    unittest.main()
