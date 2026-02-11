import os
import requests
from dataclasses import dataclass
import logging

logger = logging.getLogger("uvicorn")

BASE_URL = os.getenv("OUTLINE_API_URL")

# Required Outline permissions:
# groups.create groups.list users.list groups.add_user groups.remove_user groups.delete groups.memberships
API_KEY = os.getenv("OUTLINE_API_KEY")
if not API_KEY:
    raise RuntimeError("OUTLINE_API_KEY must be set")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


@dataclass
class OutlineUser:
    id: str
    name: str
    email: str | None
    groups: []


# TODO Pagination isn't fully handled, so anything above the 100 limit will cause issues
def outline_post_get(endpoint: str, payload: dict = {}):
    resp = requests.post(
        f"{BASE_URL}/api/{endpoint}",
        json=payload,
        headers=HEADERS,
        timeout=5,
    )
    resp.raise_for_status()
    ret = resp.json()
    return ret.get("data", [])


def fetch_outline_users():
    payload = {}
    payload["limit"] = 100
    payload["filter"] = "active"
    return outline_post_get("users.list", payload)


def fetch_outline_groups():
    payload = {}
    payload["limit"] = 100
    return outline_post_get("groups.list", payload)


def create_outline_group(name):
    payload = {}
    payload["name"] = name
    return outline_post_get("groups.create", payload)


def delete_outline_group(name):
    group_id = get_group_id_for_name(name)
    if group_id is None:
        return False

    payload = {}
    payload["id"] = group_id
    return outline_post_get("groups.delete", payload)


def add_group_membership(group_name, userid):
    group_id = get_group_id_for_name(group_name)
    if group_id is None:
        return False

    payload = {}
    payload["id"] = group_id
    payload["userId"] = userid
    return outline_post_get("groups.add_user", payload)


def delete_group_membership(group_name, userid):
    group_id = get_group_id_for_name(group_name)
    if group_id is None:
        return False

    payload = {}
    payload["id"] = group_id
    payload["userId"] = userid
    return outline_post_get("groups.remove_user", payload)


def get_group_id_for_name(name):
    payload = {}
    payload["query"] = name
    matched_groups = outline_post_get("groups.list", payload)["groups"]

    for group in matched_groups:
        if group["name"] == name:
            group_id = group["id"]
            return group_id

    return None


def build_outline_user_store():
    users_raw = fetch_outline_users()
    groups_raw = fetch_outline_groups()

    groups = groups_raw.get("groups", [])
    group_id_to_name = {g["id"]: g["name"] for g in groups}

    store = {}

    for u in users_raw:
        store[u["id"]] = OutlineUser(
            id=u["id"],
            name=u["name"],
            email=u.get("email"),
            groups=[]
        )

    for g in groups:
        group_id = g["id"]
        payload = {}
        payload["id"] = group_id
        payload["limit"] = 100
        group_membership = outline_post_get("groups.memberships", payload)

        for user in group_membership.get("users", []):
            user_id = user["id"]
            if store[user_id]:
                group_name = group_id_to_name[group_id]
                store[user_id].groups.append(group_name)
            else:
                logger.error("Invalid user found while looking for group: %s",
                             str(user))

    return list(store.values())


def get_unique_groups():
    groups_raw = fetch_outline_groups()
    groups = groups_raw.get("groups", [])

    unique_groups = set()
    for group in groups:
        unique_groups.add(group["name"])

    return unique_groups


def create_missing_groups(pocket_groups):
    outline_groups = get_unique_groups()

    for pocket_group in pocket_groups:
        if pocket_group not in outline_groups:
            logger.info("Creating group %s", pocket_group)
            create_outline_group(pocket_group)


def delete_extra_groups(pocket_groups):
    outline_groups = get_unique_groups()

    for outline_group in outline_groups:
        if outline_group not in pocket_groups:
            logger.info("Deleting group %s", outline_group)
            delete_outline_group(outline_group)


def find_matching_pocket_user(pocket_users, outline_user):
    for pocket_user in pocket_users:
        if pocket_user.email == outline_user.email:
            return pocket_user

    logger.warning("Didn't find pocket user for: %s", str(outline_user))
    return None


def set_missing_group_memberships(pocket_users):
    outline_users = build_outline_user_store()
    for outline_user in outline_users:
        pocket_user = find_matching_pocket_user(pocket_users, outline_user)
        if pocket_user is None:
            continue

        for group in pocket_user.groups:
            if group not in outline_user.groups:
                logger.info("Adding missing group membership %s to %s",
                            group, str(pocket_user.email))
                add_group_membership(group, outline_user.id)


def delete_extra_group_memberships(pocket_users):
    outline_users = build_outline_user_store()
    for outline_user in outline_users:
        pocket_user = find_matching_pocket_user(pocket_users, outline_user)
        if pocket_user is None:
            continue

        for group in outline_user.groups:
            if group not in pocket_user.groups:
                logger.info("Deleting extra group membership %s on %s",
                            group, str(pocket_user.email))
                delete_group_membership(group, outline_user.id)

