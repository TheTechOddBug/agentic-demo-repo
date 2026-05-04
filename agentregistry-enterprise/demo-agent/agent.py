"""Minimal echo agent for AgentRegistry demo.

This agent receives a message and echoes it back with a prefix.
Designed to be as small as possible for testing AWS Bedrock AgentCore deployments.
"""

import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("echo-agent")


def handle_request(event, context=None):
    """Handle an incoming A2A request."""
    logger.info("Received request: %s", json.dumps(event, default=str)[:200])

    # Extract the message from the request
    message = ""
    if isinstance(event, dict):
        # A2A protocol: look for the message in the standard location
        parts = event.get("params", {}).get("message", {}).get("parts", [])
        for part in parts:
            if part.get("kind") == "text":
                message = part.get("text", "")
                break
        if not message:
            message = event.get("message", event.get("input", str(event)))

    response_text = f"Echo: {message}"
    logger.info("Responding: %s", response_text)

    return {
        "result": {
            "parts": [
                {
                    "kind": "text",
                    "text": response_text
                }
            ]
        }
    }
