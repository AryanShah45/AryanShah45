"""LinkedIn post publisher — handles text, image, and carousel posts."""

import json
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class LinkedInPoster:
    """Publishes content to LinkedIn via the API.

    Supports:
    - Text-only posts
    - Image posts (with uploaded image)
    - Document/carousel posts (PDF upload)
    - First comment posting (for links)
    """

    API_BASE = "https://api.linkedin.com/v2"
    REST_API_BASE = "https://api.linkedin.com/rest"

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202401",
        }
        self._person_id = None

    async def _get_person_id(self) -> str:
        """Get the authenticated user's person URN."""
        if self._person_id:
            return self._person_id

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE}/userinfo",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            response.raise_for_status()
            data = response.json()
            self._person_id = data["sub"]
            return self._person_id

    async def post_text(self, text: str) -> dict:
        """Publish a text-only post to LinkedIn.

        Args:
            text: The post body text (with hashtags).

        Returns:
            API response dict with post ID.
        """
        person_id = await self._get_person_id()

        payload = {
            "author": f"urn:li:person:{person_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.API_BASE}/ugcPosts",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

        post_id = result.get("id", "")
        logger.info(f"Text post published: {post_id}")
        return result

    async def _upload_image(self, image_path: str) -> str:
        """Upload an image to LinkedIn and return the asset URN."""
        person_id = await self._get_person_id()

        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": f"urn:li:person:{person_id}",
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent",
                    }
                ],
            }
        }

        async with httpx.AsyncClient() as client:
            reg_response = await client.post(
                f"{self.API_BASE}/assets?action=registerUpload",
                headers=self.headers,
                json=register_payload,
            )
            reg_response.raise_for_status()
            reg_data = reg_response.json()

        upload_url = reg_data["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset = reg_data["value"]["asset"]

        with open(image_path, "rb") as f:
            image_data = f.read()

        async with httpx.AsyncClient() as client:
            upload_response = await client.put(
                upload_url,
                content=image_data,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/octet-stream",
                },
            )
            upload_response.raise_for_status()

        logger.info(f"Image uploaded: {asset}")
        return asset

    async def post_with_image(self, text: str, image_path: str) -> dict:
        """Publish a post with an image attachment.

        Args:
            text: Post body text.
            image_path: Path to the image file.

        Returns:
            API response dict.
        """
        person_id = await self._get_person_id()
        asset = await self._upload_image(image_path)

        payload = {
            "author": f"urn:li:person:{person_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "IMAGE",
                    "media": [
                        {
                            "status": "READY",
                            "media": asset,
                        }
                    ],
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.API_BASE}/ugcPosts",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

        logger.info(f"Image post published: {result.get('id', '')}")
        return result

    async def post_with_document(self, text: str, pdf_path: str, title: str = "") -> dict:
        """Publish a post with a document/carousel (PDF) attachment.

        Args:
            text: Post body text.
            pdf_path: Path to the PDF file.
            title: Title for the document.

        Returns:
            API response dict.
        """
        person_id = await self._get_person_id()

        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-document"],
                "owner": f"urn:li:person:{person_id}",
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent",
                    }
                ],
            }
        }

        async with httpx.AsyncClient() as client:
            reg_response = await client.post(
                f"{self.API_BASE}/assets?action=registerUpload",
                headers=self.headers,
                json=register_payload,
            )
            reg_response.raise_for_status()
            reg_data = reg_response.json()

        upload_url = reg_data["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset = reg_data["value"]["asset"]

        with open(pdf_path, "rb") as f:
            pdf_data = f.read()

        async with httpx.AsyncClient() as client:
            await client.put(
                upload_url,
                content=pdf_data,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/octet-stream",
                },
            )

        payload = {
            "author": f"urn:li:person:{person_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NATIVE_DOCUMENT",
                    "media": [
                        {
                            "status": "READY",
                            "media": asset,
                            "title": {"text": title or "Commodity Market Insights"},
                        }
                    ],
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.API_BASE}/ugcPosts",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

        logger.info(f"Document/carousel post published: {result.get('id', '')}")
        return result

    async def post_comment(self, post_urn: str, comment_text: str) -> dict:
        """Post a comment on a LinkedIn post (for first comment with links).

        Args:
            post_urn: The URN of the post to comment on.
            comment_text: The comment text.

        Returns:
            API response dict.
        """
        person_id = await self._get_person_id()

        payload = {
            "actor": f"urn:li:person:{person_id}",
            "message": {"text": comment_text},
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.API_BASE}/socialActions/{post_urn}/comments",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()
