"""LinkedIn OAuth 2.0 authentication and token management."""

import json
import logging
import os
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import httpx
from dotenv import load_dotenv, set_key

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class LinkedInAuth:
    """Handles LinkedIn OAuth 2.0 authentication flow.

    Supports:
    - Three-legged OAuth 2.0 for initial authorization
    - Token refresh for long-lived access
    - Token storage in .env file
    """

    AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    REDIRECT_URI = "http://localhost:8080/callback"
    SCOPES = ["openid", "profile", "w_member_social"]

    def __init__(self):
        load_dotenv(ENV_FILE)
        self.client_id = os.getenv("LINKEDIN_CLIENT_ID", "")
        self.client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "")
        self.access_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
        self.refresh_token = os.getenv("LINKEDIN_REFRESH_TOKEN", "")

    @property
    def is_configured(self) -> bool:
        """Check if LinkedIn credentials are configured."""
        return bool(self.client_id and self.client_secret)

    @property
    def has_token(self) -> bool:
        """Check if we have an access token."""
        return bool(self.access_token)

    def get_authorization_url(self) -> str:
        """Generate the OAuth authorization URL."""
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.REDIRECT_URI,
            "scope": " ".join(self.SCOPES),
            "state": "linkedin_commodity_automation",
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, authorization_code: str) -> dict:
        """Exchange authorization code for access token."""
        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.REDIRECT_URI,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()

        self.access_token = token_data.get("access_token", "")
        self.refresh_token = token_data.get("refresh_token", "")

        self._save_tokens()
        logger.info("LinkedIn tokens obtained and saved successfully.")
        return token_data

    async def refresh_access_token(self) -> dict:
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            raise ValueError("No refresh token available. Run setup again.")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()

        self.access_token = token_data.get("access_token", "")
        if token_data.get("refresh_token"):
            self.refresh_token = token_data["refresh_token"]

        self._save_tokens()
        logger.info("LinkedIn tokens refreshed successfully.")
        return token_data

    async def get_profile(self) -> dict:
        """Get the authenticated user's LinkedIn profile."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.linkedin.com/v2/userinfo",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            response.raise_for_status()
            return response.json()

    def _save_tokens(self):
        """Save tokens to .env file."""
        env_path = str(ENV_FILE)
        if not ENV_FILE.exists():
            ENV_FILE.touch()

        set_key(env_path, "LINKEDIN_ACCESS_TOKEN", self.access_token)
        if self.refresh_token:
            set_key(env_path, "LINKEDIN_REFRESH_TOKEN", self.refresh_token)

    def setup_interactive(self):
        """Run the interactive OAuth setup flow.

        Opens browser for LinkedIn login, captures the callback, and stores tokens.
        """
        if not self.is_configured:
            print("LinkedIn API credentials not found in .env file.")
            print("Please add LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET first.")
            print(f"See: {ENV_FILE}")
            return

        auth_url = self.get_authorization_url()
        print(f"\nOpening LinkedIn authorization page...")
        print(f"If the browser doesn't open, visit:\n{auth_url}\n")

        captured_code = {"code": None}

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                query = parse_qs(urlparse(self.path).query)
                if "code" in query:
                    captured_code["code"] = query["code"][0]
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        b"<h1>Authorization successful!</h1>"
                        b"<p>You can close this window and return to the terminal.</p>"
                    )
                else:
                    error = query.get("error", ["unknown"])[0]
                    self.send_response(400)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        f"<h1>Authorization failed: {error}</h1>".encode()
                    )

            def log_message(self, format, *args):
                pass

        webbrowser.open(auth_url)

        server = HTTPServer(("localhost", 8080), CallbackHandler)
        print("Waiting for authorization callback...")
        server.handle_request()
        server.server_close()

        if captured_code["code"]:
            import asyncio
            asyncio.run(self.exchange_code(captured_code["code"]))
            print("Setup complete! Tokens saved to .env")
        else:
            print("Authorization failed. No code received.")
