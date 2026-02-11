import os
import requests
from typing import Set
from dataclasses import dataclass, field

BASE_URL = os.getenv("POCKETID_API_URL")
API_KEY = os.getenv("POCKETID_API_KEY")

if not BASE_URL or not API_KEY:
    raise RuntimeError("POCKETID_API_URL and POCKETID_API_KEY must be set")

HEADERS = {
    "X-API-KEY": API_KEY,
    "Accept": "application/json",
}


@dataclass
class PocketUser:
    username: str
    user_id: str
    email: str | None
    groups: Set[str] = field(default_factory=set)


def fetch_users():
    all_users = []
    page = 1
    limit = 50

    while True:
        resp = requests.get(
            f"{BASE_URL}/api/users",
            headers=HEADERS,
            params={
                "pagination[page]": page,
                "pagination[limit]": limit
            },
            timeout=2,
        )
        resp.raise_for_status()

        users = resp.json()["data"]
        lastPage = resp.json()["pagination"]["totalPages"]

        if not users:
            break

        all_users.extend(users)
        if lastPage == page:
            break

        page = page + 1

    return all_users


def sync_from_pocket_id():
    user_store: list[PocketUser] = []

    users = fetch_users()

    for user in users:
        # TODO DC: At some point, probably will need to use this also to disable users
        # in other services as well
        if user["disabled"] is True:
            continue

        groups = user["userGroups"]
        # TODO DC: Filtered groups is a misnomer from when this had a regex check as well
        filtered_groups = []
        for group in groups:
            group_name = group["name"]
            filtered_groups.append(group_name)

        userobj = PocketUser(username=user["username"],
                             user_id=user["id"],
                             email=user["email"],
                             groups=filtered_groups)
        user_store.append(userobj)

    return user_store


def get_unique_groups(user_store=None):
    if user_store is None:
        user_store = sync_from_pocket_id()

    unique_groups = set()
    for user in user_store:
        for group in user.groups:
            unique_groups.add(group)

    return unique_groups

