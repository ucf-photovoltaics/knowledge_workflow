"""Dashboard-owned Zotero discovery and recursive selection, using authenticated headers.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
from __future__ import annotations

import re
import time
import requests


class Libraries:
    def __init__(self, key):
        if not key or not key.strip():
            raise ValueError("Save an .env containing ZOTERO_API_KEY first.")
        self.key = key.strip()
        self.deadline = time.monotonic() + 180

    def get(self, path, params=None):
        if time.monotonic() > self.deadline:
            raise ValueError("Zotero browsing timed out. Retry with fewer libraries.")
        try:
            response = requests.get("https://api.zotero.org" + path, params=params,
                                    headers={"Zotero-API-Key": self.key, "Zotero-API-Version": "3"}, timeout=25)
            if not response.ok:
                raise ValueError(f"Zotero returned HTTP {response.status_code}. Check library permissions or retry later.")
            return response.json()
        except requests.RequestException:
            raise ValueError("Cannot reach Zotero. Check connectivity and retry.") from None

    def pages(self, path):
        rows = []
        for start in range(0, 100000, 100):
            page = self.get(path, {"start": start, "limit": 100})
            if not isinstance(page, list):
                raise ValueError("Unexpected Zotero response.")
            rows.extend(page)
            if len(page) < 100:
                return rows
        raise ValueError("Library exceeds the browsing safety limit.")

    @staticmethod
    def prefix(library):
        if library.get("type") not in ("user", "group") or not str(library.get("id", "")).isdigit():
            raise ValueError("Invalid Zotero library.")
        return f"/{'users' if library['type'] == 'user' else 'groups'}/{library['id']}"

    def libraries(self):
        info = self.get("/keys/current")
        user = str(info.get("userID", ""))
        if not user.isdigit():
            raise ValueError("Zotero did not identify the API key owner.")
        access = info.get("access", {})
        result = []
        if access.get("user", {}).get("library"):
            result.append({"type": "user", "id": user, "name": "My library"})
        groups = self.pages(f"/users/{user}/groups")
        permitted = access.get("groups", {})
        for row in groups:
            identifier = str(row.get("id", row.get("data", {}).get("id", "")))
            permission = permitted.get(identifier, permitted.get("all", {}))
            if permission.get("library"):
                result.append({"type": "group", "id": identifier,
                               "name": row.get("data", {}).get("name", identifier)})
        # Keys can grant access to a group outside the owner's membership list.
        known = {r["id"] for r in result if r["type"] == "group"}
        for identifier, permission in permitted.items():
            if identifier.isdigit() and permission.get("library") and identifier not in known:
                row = self.get(f"/groups/{identifier}")
                result.append({"type": "group", "id": identifier, "name": row.get("data", {}).get("name", identifier)})
        return result

    def collections(self, library):
        return [{"library": library, "key": row["key"], "name": row["data"]["name"],
                 "parent": row["data"].get("parentCollection") or ""}
                for row in self.pages(self.prefix(library) + "/collections")]

    def expand(self, selected):
        result = {}
        for source in selected:
            library, key = source["library"], source["key"]
            if not re.fullmatch(r"[A-Z0-9]{8}", key):
                raise ValueError("Invalid collection key.")
            rows = self.collections(library)
            keys = {key}
            while True:
                expanded = keys | {r["key"] for r in rows if r["parent"] in keys}
                if expanded == keys:
                    break
                keys = expanded
            for row in rows:
                if row["key"] in keys:
                    result[(library["type"], library["id"], row["key"])] = row
        return list(result.values())


def deduplicate(papers):
    """Prefer DOI identity; retain all accessible attachment sources for duplicates."""
    result = {}
    for paper in papers:
        doi = re.sub(r"^(https?://(dx\.)?doi.org/|doi:\s*)", "", paper.get("doi", "").strip().lower())
        identity = "doi:" + doi if doi else paper["key"]
        if identity in result:
            result[identity]["sources"].extend(paper["sources"])
        else:
            result[identity] = {**paper, "sources": list(paper["sources"])}
    return list(result.values())
