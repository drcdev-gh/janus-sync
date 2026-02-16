import logging
import os
from fastapi.responses import PlainTextResponse
import re

logger = logging.getLogger("uvicorn")

SSH_ALLOWED_GROUP = os.environ["SSH_ALLOWED_GROUP"]

PUBKEY_RE = re.compile(
    r"^(ssh-(rsa|ed25519)|ecdsa-sha2-nistp(256|384|521)) [A-Za-z0-9+/=]+(?: .*)?$"
)


def validate_keyformat(pubkey: str) -> bool:
    return bool(PUBKEY_RE.fullmatch(pubkey.strip()))


def validate_pubkey(pubkey: str, users):
    if not validate_keyformat(pubkey):
        logger.warning("Invalid Public Key Format: %s", pubkey)
        return PlainTextResponse("", status_code=204)

    if not users or len(users) == 0:
        logger.warning("Unable to fetch users")
        return PlainTextResponse("", status_code=204)

    for user in users:
        for group in user.groups:
            if SSH_ALLOWED_GROUP == group:
                for custom_claim in user.custom_claims:
                    if custom_claim["key"] == "ssh-pubkey":
                        if custom_claim["value"] == pubkey:
                            logger.info("Authorizing login for %s with key %s",
                                        user.username, pubkey)
                            return PlainTextResponse(custom_claim["value"] + "\n")
                # No need to continue running through the group loop
                break

    logger.warning("No matching Public Key found: %s", pubkey)
    return PlainTextResponse("", status_code=204)
