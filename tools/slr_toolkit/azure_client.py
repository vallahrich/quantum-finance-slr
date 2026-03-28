"""Reusable Azure OpenAI client via the official ``openai`` SDK.

Handles endpoint normalisation, authentication (API key or Azure AD),
and clear error messaging for common failure modes (missing env vars,
404 deployment mismatch, rate-limiting, transient errors).

Usage::

    from tools.slr_toolkit.azure_client import create_client, chat_completion

    client = create_client(endpoint="https://myresource.openai.azure.com",
                           api_key="...", deployment="gpt-5-mini")
    result = chat_completion(client, deployment="gpt-5-mini",
                             system_prompt="...", user_prompt="...",)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

# Load .env from parent repo (quantum-finance/.env) or local .env
try:
    from dotenv import load_dotenv

    _this_dir = os.path.dirname(os.path.abspath(__file__))
    _parent_env = os.path.normpath(os.path.join(_this_dir, "..", "..", "..", ".env"))
    _local_env = os.path.normpath(os.path.join(_this_dir, "..", "..", ".env"))
    load_dotenv(_parent_env if os.path.isfile(_parent_env) else _local_env)

    # Normalize: accept AZURE_ENDPOINT / AZURE_API_KEY as fallbacks
    if not os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_ENDPOINT"):
        os.environ["AZURE_OPENAI_ENDPOINT"] = os.environ["AZURE_ENDPOINT"]
    if not os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_API_KEY"):
        os.environ["AZURE_OPENAI_API_KEY"] = os.environ["AZURE_API_KEY"]
    if not os.getenv("AZURE_OPENAI_DEPLOYMENT") and os.getenv("AZURE_DEPLOYMENT"):
        os.environ["AZURE_OPENAI_DEPLOYMENT"] = os.environ["AZURE_DEPLOYMENT"]
except ImportError:
    pass  # python-dotenv not installed; rely on shell env vars

log = logging.getLogger(__name__)


# ── Endpoint normalisation ───────────────────────────────────────────────

def normalise_endpoint(endpoint: str) -> str:
    """Ensure *endpoint* ends with ``/openai/v1/`` for the OpenAI SDK.

    Accepts any of:
    - ``https://RESOURCE.openai.azure.com``
    - ``https://RESOURCE.openai.azure.com/``
    - ``https://RESOURCE.openai.azure.com/openai/v1``
    - ``https://RESOURCE.openai.azure.com/openai/v1/``
    """
    endpoint = endpoint.rstrip("/")
    if not endpoint.endswith("/openai/v1"):
        endpoint += "/openai/v1"
    return endpoint + "/"


# ── Azure AD token helper ────────────────────────────────────────────────

_cached_ad_token: dict[str, Any] | None = None


def get_azure_ad_token() -> str:
    """Obtain a bearer token via ``az account get-access-token``.

    Uses the caller's existing ``az login`` session — no stored secrets.
    Tokens are cached until 2 minutes before expiry.
    """
    global _cached_ad_token  # noqa: PLW0603
    now = time.time()
    if _cached_ad_token and _cached_ad_token["expires_on"] - now > 120:
        return _cached_ad_token["token"]

    import shutil
    az_cmd = shutil.which("az") or shutil.which("az.cmd") or "az"

    try:
        result = subprocess.run(  # noqa: S603
            [az_cmd, "account", "get-access-token",
             "--resource", "https://cognitiveservices.azure.com",
             "-o", "json"],
            capture_output=True, text=True, timeout=30,
            check=True,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Azure CLI ('az') not found. Install it or provide --api-key / "
            "set AZURE_OPENAI_API_KEY."
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"'az account get-access-token' failed.\n"
            f"Run 'az login' first.\n{exc.stderr.strip()}"
        )

    try:
        token_data = json.loads(result.stdout)
        token: str = token_data["accessToken"]
        expires_on = float(token_data.get("expires_on", now + 3300))
    except (json.JSONDecodeError, KeyError) as exc:
        raise RuntimeError(
            f"Failed to parse 'az account get-access-token' output: {exc}"
        )
    if not token:
        raise RuntimeError(
            "Azure CLI returned an empty token.  Run 'az login' and retry."
        )

    _cached_ad_token = {"token": token, "expires_on": expires_on}
    log.info("Acquired Azure AD token via 'az account get-access-token'")
    return token


def _refresh_ad_token() -> str:
    """Force-refresh the cached Azure AD token."""
    global _cached_ad_token  # noqa: PLW0603
    _cached_ad_token = None
    return get_azure_ad_token()


# ── Client factory ───────────────────────────────────────────────────────

class AzureOpenAIClient:
    """Thin wrapper around :class:`openai.OpenAI` with Azure AD auto-refresh."""

    def __init__(
        self,
        endpoint: str,
        deployment: str,
        api_key: str = "",
    ) -> None:
        self.endpoint = endpoint
        self.deployment = deployment
        self.use_ad_token = not api_key

        base_url = normalise_endpoint(endpoint)
        if api_key:
            self._client = OpenAI(base_url=base_url, api_key=api_key)
            log.info("Azure OpenAI client: API key auth -> %s", base_url)
        else:
            token = get_azure_ad_token()
            self._client = OpenAI(base_url=base_url, api_key=token)
            log.info("Azure OpenAI client: Azure AD auth -> %s", base_url)

    def _ensure_auth(self) -> None:
        """Refresh Azure AD token if it's about to expire."""
        if not self.use_ad_token:
            return
        token = get_azure_ad_token()          # returns cached if still valid
        self._client.api_key = token          # update in-place

    @property
    def inner(self) -> OpenAI:
        """Access the underlying :class:`openai.OpenAI` client."""
        self._ensure_auth()
        return self._client


def create_client(
    endpoint: str | None = None,
    api_key: str | None = None,
    deployment: str | None = None,
) -> AzureOpenAIClient:
    """Create an :class:`AzureOpenAIClient` from explicit args or env vars.

    Environment variables (fallback):
    - ``AZURE_OPENAI_ENDPOINT``
    - ``AZURE_OPENAI_API_KEY``
    - ``AZURE_OPENAI_DEPLOYMENT``

    Raises :class:`RuntimeError` with a clear message if required values
    are missing.
    """
    endpoint = endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    api_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY", "")
    deployment = deployment or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")

    if not endpoint:
        raise RuntimeError(
            "Azure OpenAI endpoint not set. "
            "Set AZURE_OPENAI_ENDPOINT env var or pass --endpoint."
        )
    if not deployment:
        raise RuntimeError(
            "Azure OpenAI deployment not set. "
            "Set AZURE_OPENAI_DEPLOYMENT env var or pass --deployment."
        )
    if not api_key:
        # Will attempt Azure AD auth inside AzureOpenAIClient.__init__
        log.info("No API key provided — will use Azure AD (az login) auth")

    return AzureOpenAIClient(endpoint=endpoint, deployment=deployment, api_key=api_key)


# ── Chat completion helper ───────────────────────────────────────────────

class AzureAPIError(Exception):
    """Azure OpenAI API error with status code and actionable message."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def chat_completion(
    client: AzureOpenAIClient,
    *,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 256,
    response_schema: dict | None = None,
    timeout: int = 120,
) -> dict:
    """Send a prompt via the Responses API and return a compatibility dict.

    Uses the OpenAI Responses API (``client.responses.create``) which works
    reliably with gpt-5 models on Azure.

    The return dict uses the same shape as a chat completion response
    (``choices[0].message.content`` + ``usage``) so downstream parsers
    don't need changes.

    Parameters
    ----------
    client : AzureOpenAIClient
        Client created by :func:`create_client`.
    system_prompt, user_prompt : str
        Messages for the chat.
    max_tokens : int
        Maximum completion tokens.
    response_schema : dict | None
        If provided, use structured output (``json_schema`` response format).
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    dict
        Compatibility dict with ``choices`` and ``usage`` keys.
    """
    deployment = client.deployment

    instructions = system_prompt
    input_text = user_prompt

    kwargs: dict[str, Any] = {
        "model": deployment,
        "instructions": instructions,
        "input": input_text,
        "max_output_tokens": max_tokens,
        "timeout": timeout,
    }

    if response_schema:
        # Responses API: schema fields (name, strict, schema) go at the
        # top level of the format dict, not nested under 'json_schema'.
        kwargs["text"] = {
            "format": {
                "type": "json_schema",
                **response_schema,
            }
        }
    else:
        # Ensure text output is generated even without a schema
        kwargs["text"] = {"format": {"type": "text"}}

    try:
        resp = client.inner.responses.create(**kwargs)

        # Extract text content from the response
        content = resp.output_text or ""

        # Build compatibility dict matching chat completion shape
        usage_data = {}
        if resp.usage:
            usage_data = {
                "prompt_tokens": resp.usage.input_tokens,
                "completion_tokens": resp.usage.output_tokens,
                "total_tokens": resp.usage.total_tokens,
            }

        return {
            "choices": [{"message": {"content": content, "role": "assistant"}}],
            "usage": usage_data,
        }
    except APIStatusError as exc:
        code = exc.status_code
        body = str(exc.body) if exc.body else ""
        if code == 404:
            raise AzureAPIError(
                f"HTTP 404: Deployment '{deployment}' not found. "
                f"Check that the Azure deployment name matches exactly.\n{body}",
                status_code=404,
            ) from exc
        if code == 401:
            raise AzureAPIError(
                f"HTTP 401: Authentication failed. "
                f"Check your API key or run 'az login'.\n{body}",
                status_code=401,
            ) from exc
        if code == 429:
            raise AzureAPIError(
                f"HTTP 429: Rate limited. Slow down or increase TPM quota.\n{body}",
                status_code=429,
            ) from exc
        raise AzureAPIError(
            f"HTTP {code}: {exc.message}\n{body}",
            status_code=code,
        ) from exc
    except APITimeoutError as exc:
        raise AzureAPIError(f"Request timed out: {exc}") from exc
    except APIConnectionError as exc:
        raise AzureAPIError(f"Connection error: {exc}") from exc
