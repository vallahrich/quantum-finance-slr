"""Smoke test: send one prompt to Azure OpenAI and print the response.

Usage::

    python -m tools.slr_toolkit.smoke_test

Uses the same env vars / az-login auth as the main CLI commands.
Pass --endpoint and --deployment to override env vars.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Azure OpenAI smoke test")
    parser.add_argument("--endpoint", default=None, help="Azure OpenAI endpoint URL")
    parser.add_argument("--deployment", default=None, help="Deployment / model name (e.g. gpt-5-mini)")
    parser.add_argument("--api-key", default=None, help="API key (default: env var or az login)")
    args = parser.parse_args()

    from tools.slr_toolkit.azure_client import chat_completion, create_client

    client = create_client(
        endpoint=args.endpoint,
        api_key=args.api_key,
        deployment=args.deployment,
    )

    print(f"Endpoint:   {client.endpoint}")
    print(f"Deployment: {client.deployment}")
    print(f"Auth:       {'Azure AD (az login)' if client.use_ad_token else 'API key'}")
    print()

    result = chat_completion(
        client,
        system_prompt="You are a helpful assistant. Reply in one sentence.",
        user_prompt="What is quantum computing?",
        max_tokens=100,
    )

    content = result["choices"][0]["message"]["content"]
    usage = result.get("usage", {})

    print(f"Response: {content!r}")
    print(f"Tokens:   {usage.get('prompt_tokens', '?')} prompt / "
          f"{usage.get('completion_tokens', '?')} completion")
    print("\n[ok] Smoke test passed.")


if __name__ == "__main__":
    main()
