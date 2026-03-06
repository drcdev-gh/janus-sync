from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import logging
import sys
import os

import pocket
import outline
import ssh

logger = logging.getLogger("uvicorn")

REQUIRED_ENVS = [
    "POCKETID_API_URL",
    "POCKETID_API_KEY",
    "OUTLINE_API_URL",
    "OUTLINE_API_KEY",
    "SSH_ALLOWED_GROUP",
    "API_KEY",
]

for var in REQUIRED_ENVS:
    if var not in os.environ:
        logger.error("Required environment variable %s not set", var)
        sys.exit(1)

app = FastAPI()

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET"]
)

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("API_KEY must be set")

# Quick caching mechanism
# TODO DC: probably not thread safe.
pocket_userstore = None
last_updated_timestamp = None


def update_pocket_userstore(force_update: bool):
    global pocket_userstore, last_updated_timestamp

    has_been_updated = False
    now = datetime.utcnow()

    def should_refresh():
        return (
            pocket_userstore is None or
            last_updated_timestamp is None or
            now - last_updated_timestamp > timedelta(minutes=30)
        )

    if force_update or should_refresh():
        new_userstore = pocket.sync_from_pocket_id()

        if new_userstore != pocket_userstore:
            has_been_updated = True

        pocket_userstore = new_userstore
        last_updated_timestamp = now

    return has_been_updated


@app.get("/outline/sync")
def sync_outline(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        logger.warning("Invalid API Key: %s", x_api_key)
        raise HTTPException(status_code=403)

    global pocket_userstore
    logger.info("Syncing Pocket Groups to Outline")
    pocket_was_updated = update_pocket_userstore(True)
    if pocket_was_updated:
        logger.info("Skipping sync since Pocket Store is still the same...")
        return {"status": "ok"}

    if len(pocket_userstore) == 0:
        logger.warning("Empty Pocket Store Detected -- Failing")
        raise HTTPException(status_code=404)

    pocket_groups = pocket.get_unique_groups(pocket_userstore)

    if len(pocket_groups) == 0:
        logger.warning("Empty Pocket Groups Detected -- Failing")
        raise HTTPException(status_code=404)

    outline.create_missing_groups(pocket_groups)
    outline.delete_extra_groups(pocket_groups)

    outline.set_missing_group_memberships(pocket_userstore)
    outline.delete_extra_group_memberships(pocket_userstore)

    return {"status": "ok"}


@app.get("/ssh/validate")
def validate_ssh_login(pubkey: str, x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        logger.warning("Invalid API Key: %s", x_api_key)
        raise HTTPException(status_code=403)

    global pocket_userstore
    update_pocket_userstore(False)
    return ssh.validate_pubkey(pubkey, pocket_userstore)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8085)
