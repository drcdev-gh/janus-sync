from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys
import os

import pocket
import outline

logger = logging.getLogger("uvicorn")

REQUIRED_ENVS = [
    "POCKETID_API_URL",
    "POCKETID_API_KEY",
    "OUTLINE_API_URL",
    "OUTLINE_API_KEY",
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
# it also won't work if we add something else in addition to Outline
previous_pocket_userstore = None


@app.get("/outline/sync")
def sync_outline(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        logger.warning("Invalid API Key: %s", x_api_key)
        raise HTTPException(status_code=403)

    global previous_pocket_userstore
    logger.info("Syncing Pocket Groups to Outline")
    pocket_store = pocket.sync_from_pocket_id()
    if pocket_store == previous_pocket_userstore:
        logger.info("Skipping sync since Pocket Store is still the same...")
        return {"status": "ok"}

    if len(pocket_store) == 0:
        logger.warning("Empty Pocket Store Detected -- Failing")
        raise HTTPException(status_code=404)

    pocket_groups = pocket.get_unique_groups(pocket_store)

    if len(pocket_groups) == 0:
        logger.warning("Empty Pocket Groups Detected -- Failing")
        raise HTTPException(status_code=404)

    outline.create_missing_groups(pocket_groups)
    outline.delete_extra_groups(pocket_groups)

    outline.set_missing_group_memberships(pocket_store)
    outline.delete_extra_group_memberships(pocket_store)

    previous_pocket_userstore = pocket_store
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8085)
