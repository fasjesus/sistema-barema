import unittest

from app import app
from core.security import login_attempt_limiter


class LoginRateLimitViewTest(unittest.TestCase):
    def setUp(self):
        self.previous_config = {
            "LOGIN_MAX_ATTEMPTS": app.config["LOGIN_MAX_ATTEMPTS"],
            "LOGIN_BLOCK_SECONDS": app.config["LOGIN_BLOCK_SECONDS"],
        }
        app.config.update(
            TESTING=True,
            LOGIN_MAX_ATTEMPTS=3,
            LOGIN_BLOCK_SECONDS=60,
        )
        login_attempt_limiter.clear()

    def tearDown(self):
        app.config.update(self.previous_config)
        login_attempt_limiter.clear()

    def test_login_button_is_disabled_when_user_is_blocked(self):
        with app.test_client() as client:
            response = None
            for _ in range(3):
                response = client.post(
                    "/login",
                    data={
                        "username": "usuario-bloqueado",
                        "password": "senha-incorreta",
                    },
                )

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "60")
        self.assertIn('id="loginButton"', html)
        self.assertIn('data-retry-after="60"', html)
        self.assertIn("disabled", html)
        self.assertIn('value="usuario-bloqueado"', html)

    def test_login_page_keeps_button_disabled_while_session_is_blocked(self):
        with app.test_client() as client:
            for _ in range(3):
                client.post(
                    "/login",
                    data={
                        "username": "usuario-bloqueado",
                        "password": "senha-incorreta",
                    },
                )

            response = client.get("/login")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="loginButton"', html)
        self.assertIn('data-retry-after="60"', html)
        self.assertIn("disabled", html)
        self.assertIn('value="usuario-bloqueado"', html)


if __name__ == "__main__":
    unittest.main()
