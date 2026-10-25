import contextlib
import io
import json
import logging
import tempfile
import unittest
from pathlib import Path

import httpx

from tests.helpers import load_weread_bot


CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _credentials(bot, refresh_token="rt/token+="):
    return bot.QrLoginCredentials(
        vid="12345678",
        skey="skey_value_123456",
        refresh_token=refresh_token,
        fingerprint="987654321",
        user_agent=CHROME_UA,
    )


class ProtocolEncodingTests(unittest.TestCase):
    def setUp(self):
        self.bot = load_weread_bot()

    def test_encode_weread_id_matches_reference_vectors(self):
        # 向量来自 27Aaron/WeRead-Kit internal/weread/read_test.go
        cases = {
            "3300060341": "81032840813ab7e12g0111d4",
            "ce032b305a9bc1ce0b0dd2a": (
                "a5b42b72e63653033326233303561396263316365306230646432613eb"
            ),
            "0": "cfc32da010cfcd208495488",
            "123456789012345678901234567890": (
                "a46321d0775bcd15g06bc614eg0835b7bf87g0337aa1c"
            ),
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(self.bot.encode_weread_id(value), expected)

    def test_generate_web_app_id_matches_reference(self):
        self.assertEqual(
            self.bot.generate_web_app_id(CHROME_UA),
            "wb182564874663h1256619504",
        )

    def test_existing_signature_matches_reference_payload(self):
        bot = self.bot
        payload = {
            "appId": bot.generate_web_app_id(CHROME_UA),
            "b": bot.encode_weread_id("3300060341"),
            "c": bot.encode_weread_id("1"),
            "ci": 1, "co": 389, "ct": 1744264311, "dy": 0, "fm": "epub",
            "pc": bot.encode_weread_id("0"), "pr": 74,
            "ps": bot.encode_weread_id("0"), "sm": "", "rt": 30,
            "ts": 1744264311434, "rn": 466,
        }
        manager = bot.WeReadSessionManager
        self.assertEqual(
            manager._calculate_hash(manager._encode_data(payload)), "7406cc1f"
        )


class LoginCurlTests(unittest.TestCase):
    def setUp(self):
        self.bot = load_weread_bot()

    def test_generated_curl_passes_existing_parser_and_validation(self):
        bot = self.bot
        curl = bot.build_login_curl_command(_credentials(bot))

        headers, cookies, data = bot.CurlParser.parse_curl_command(curl)
        valid, errors = bot.CurlParser.validate_curl_headers(
            headers, cookies, data, "login"
        )

        self.assertTrue(valid, errors)
        self.assertEqual(cookies["wr_skey"], "skey_value_123456")
        self.assertEqual(cookies["wr_vid"], "12345678")
        self.assertEqual(cookies["wr_fp"], "987654321")
        self.assertEqual(cookies["wr_rt"], "rt%2Ftoken%2B%3D")
        self.assertEqual(headers["user-agent"], CHROME_UA)
        self.assertEqual(data["appId"], "wb182564874663h1256619504")
        self.assertEqual(data["ps"], bot.encode_weread_id("0"))
        self.assertNotIn("b", data)

    def test_generated_curl_omits_empty_refresh_token(self):
        bot = self.bot
        curl = bot.build_login_curl_command(
            _credentials(bot, refresh_token="")
        )
        _, cookies, _ = bot.CurlParser.parse_curl_command(curl)
        self.assertNotIn("wr_rt", cookies)

    def test_session_manager_falls_back_to_configured_books(self):
        bot = self.bot
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "curl.txt"
            bot.write_curl_file(
                path, bot.build_login_curl_command(_credentials(bot))
            )
            config = bot.WeReadConfig(
                curl_file_path=str(path),
                reading=bot.ReadingConfig(
                    books=[bot.BookInfo(
                        name="测试书", book_id="book_id_1234567890",
                        chapters=["chapter_id_1234567890"],
                    )],
                ),
            )
            manager = bot.WeReadSessionManager(config)

        self.assertEqual(manager.cookies["wr_skey"], "skey_value_123456")
        self.assertEqual(
            manager.reading_manager.current_book_id, "book_id_1234567890"
        )


class LoginOutputPathTests(unittest.TestCase):
    def setUp(self):
        self.bot = load_weread_bot()

    def test_explicit_output_wins(self):
        config = self.bot.WeReadConfig(curl_file_path="global.txt")
        path = self.bot.resolve_login_output_path(config, None, "out.txt")
        self.assertEqual(path, Path("out.txt"))

    def test_single_user_uses_curl_file_path_or_default(self):
        bot = self.bot
        self.assertEqual(
            bot.resolve_login_output_path(
                bot.WeReadConfig(curl_file_path="me.txt")
            ),
            Path("me.txt"),
        )
        self.assertEqual(
            bot.resolve_login_output_path(bot.WeReadConfig()),
            Path("curl_command.txt"),
        )

    def test_multi_user_requires_known_user_with_file_path(self):
        bot = self.bot
        config = bot.WeReadConfig(users=[
            bot.UserConfig(name="a", file_path="a.txt"),
            bot.UserConfig(name="b", content="curl ..."),
        ])
        self.assertEqual(
            bot.resolve_login_output_path(config, "a"), Path("a.txt")
        )
        for user_name in (None, "b", "missing"):
            with self.subTest(user_name=user_name):
                with self.assertRaises(bot.QrLoginError):
                    bot.resolve_login_output_path(config, user_name)

    def test_login_options_require_login_flag(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                self.bot.parse_arguments(["--login-user", "a"])
        args = self.bot.parse_arguments(["--login", "--login-user", "a"])
        self.assertTrue(args.login)
        self.assertEqual(args.login_user, "a")


class QrLoginFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bot = load_weread_bot()
        self.bot.qrcode = None
        self.requests = []
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def _client(self, login_infos):
        login_infos = list(login_infos)

        def handler(request):
            self.requests.append(request)
            if request.url.path == "/r/weread-skills":
                return httpx.Response(200, text="<html></html>")
            if request.url.path == "/api/auth/getLoginUid":
                return httpx.Response(200, json={"uid": "login uid"})
            if request.url.path == "/api/auth/getLoginInfo":
                return httpx.Response(200, json=login_infos.pop(0))
            return httpx.Response(404)

        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def test_login_with_otp_writes_curl_file(self):
        bot = self.bot
        client = self._client([
            {"logicCode": "NEED_OTP"},
            {
                "succeed": True,
                "webLoginVid": 12345678,
                "accessToken": "skey_value_123456",
                "refreshToken": "refresh",
            },
        ])
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "nested" / "curl.txt"
            with contextlib.redirect_stdout(stdout):
                path = await bot.run_qr_login(
                    bot.WeReadConfig(),
                    output=str(output),
                    otp_reader=lambda _prompt: " 1234 ",
                    client=client,
                )
            content = path.read_text(encoding="utf-8")
        await client.aclose()

        _, cookies, data = bot.CurlParser.parse_curl_command(content)
        self.assertEqual(cookies["wr_skey"], "skey_value_123456")
        self.assertEqual(cookies["wr_vid"], "12345678")
        self.assertEqual(cookies["wr_rt"], "refresh")
        self.assertIn("appId", data)
        self.assertIn(
            "https://weread.qq.com/web/confirm?uid=login%20uid",
            stdout.getvalue(),
        )

        polls = [
            r for r in self.requests if r.url.path == "/api/auth/getLoginInfo"
        ]
        self.assertEqual(polls[0].url.params["otp"], "")
        self.assertEqual(polls[1].url.params["otp"], "1234")
        self.assertEqual(polls[1].url.params["uid"], "login uid")
        self.assertIn(f"wr_fp={cookies['wr_fp']}", polls[0].headers["cookie"])

    async def test_waiting_state_keeps_polling(self):
        client = self._client([
            {},
            {"succeed": True, "webLoginVid": "1", "accessToken": "skey"},
        ])
        result = await self.bot.wait_for_qr_login(
            client, "uid", poll_interval=0
        )
        await client.aclose()
        self.assertTrue(result["succeed"])

    async def test_expired_login_raises(self):
        client = self._client([{"logicCode": "LOGIN_TIMEOUT"}])
        with self.assertRaises(self.bot.QrLoginError):
            await self.bot.wait_for_qr_login(client, "uid", poll_interval=0)
        await client.aclose()

    async def test_success_without_token_raises(self):
        with self.assertRaises(self.bot.QrLoginError):
            self.bot.credentials_from_login_result(
                {"succeed": True, "webLoginVid": "1"}, "fp"
            )


if __name__ == "__main__":
    unittest.main()
