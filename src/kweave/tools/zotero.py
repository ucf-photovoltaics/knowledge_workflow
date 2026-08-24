"""Small Zotero Web API client with injectable transport for deterministic tests."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from kweave.contracts import Paper


JsonTransport = Callable[[str, dict[str, str]], Any]


def _http_json(url: str, headers: dict[str, str]) -> Any:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed HTTPS API root
        return json.load(response)


@dataclass(frozen=True, slots=True)
class ZoteroConfig:
    library_id: str
    api_key: str
    library_type: str = "groups"

    def __post_init__(self) -> None:
        if self.library_type not in {"groups", "users"}:
            raise ValueError("library_type must be 'groups' or 'users'")
        if not self.library_id.strip():
            raise ValueError("library_id is required")
        if not self.api_key.strip():
            raise ValueError("api_key is required")


class ZoteroClient:
    """Read collections and indexed full text without global credentials."""

    def __init__(self, config: ZoteroConfig, transport: JsonTransport = _http_json) -> None:
        self.config = config
        self._transport = transport
        self._root = f"https://api.zotero.org/{config.library_type}/{config.library_id}"
        self._headers = {"Zotero-API-Key": config.api_key, "Zotero-API-Version": "3"}

    def _get(self, path: str, **params: str | int) -> Any:
        query = f"?{urlencode(params)}" if params else ""
        return self._transport(f"{self._root}{path}{query}", self._headers)

    def current_key(self) -> dict[str, Any]:
        return self._transport("https://api.zotero.org/keys/current", self._headers)

    def list_accessible_libraries(self) -> list[dict[str, str]]:
        key = self.current_key()
        libraries: list[dict[str, str]] = []
        if user_id := key.get("userID"):
            libraries.append({"id": str(user_id), "type": "users", "name": "Personal library"})
        for group_id, access in (key.get("access", {}).get("groups", {}) or {}).items():
            name = access.get("name", "") if isinstance(access, dict) else ""
            libraries.append({"id": str(group_id), "type": "groups", "name": name})
        return libraries

    def _all(self, path: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        start = 0
        while True:
            page = self._get(path, limit=100, start=start)
            if not isinstance(page, list):
                raise ValueError(f"Expected a list from Zotero endpoint {path}")
            records.extend(page)
            if len(page) < 100:
                return records
            start += len(page)

    def collection_map(self) -> dict[str, str]:
        collections = self._all("/collections")
        by_key = {record["key"]: record["data"] for record in collections}
        result: dict[str, str] = {}
        for record in collections:
            data = record["data"]
            names = [data["name"]]
            parent = data.get("parentCollection")
            visited: set[str] = set()
            while parent and parent not in visited:
                visited.add(parent)
                parent_data = by_key.get(parent)
                if parent_data is None:
                    break
                names.append(parent_data["name"])
                parent = parent_data.get("parentCollection")
            result[" > ".join(reversed(names))] = record["key"]
        return result

    def _indexed_full_text(self, item_key: str) -> str:
        for child in self._all(f"/items/{item_key}/children"):
            data = child.get("data", {})
            if data.get("contentType") != "application/pdf":
                continue
            try:
                payload = self._get(f"/items/{child['key']}/fulltext")
            except Exception:  # Zotero returns 404 when the attachment is not indexed.
                continue
            if isinstance(payload, dict) and payload.get("content"):
                return str(payload["content"])
        return ""

    def _collection_ids(self, collection_id: str, include_subcollections: bool) -> tuple[str, ...]:
        if not include_subcollections:
            return (collection_id,)
        collections = self._all("/collections")
        children: dict[str, list[str]] = {}
        for record in collections:
            parent = record.get("data", {}).get("parentCollection")
            if parent:
                children.setdefault(str(parent), []).append(str(record["key"]))
        ordered: list[str] = []
        pending = [collection_id]
        while pending:
            current = pending.pop(0)
            if current in ordered:
                continue
            ordered.append(current)
            pending.extend(children.get(current, ()))
        return tuple(ordered)

    def get_collection(
        self,
        collection_id: str,
        limit: int | None = None,
        include_subcollections: bool = True,
    ) -> dict[str, Paper]:
        if not collection_id.strip():
            raise ValueError("collection_id is required")
        papers: dict[str, Paper] = {}
        for current_collection in self._collection_ids(collection_id, include_subcollections):
            for item in self._all(f"/collections/{current_collection}/items"):
                data = item.get("data", {})
                if data.get("itemType") in {"attachment", "note"} or not data.get("title"):
                    continue
                creators = tuple(
                    " ".join(filter(None, (creator.get("firstName"), creator.get("lastName")))).strip()
                    or creator.get("name", "")
                    for creator in data.get("creators", [])
                )
                key = str(item["key"])
                papers[key] = Paper(
                    key=key,
                    title=str(data["title"]),
                    doi=str(data.get("DOI", "")),
                    abstract=str(data.get("abstractNote", "")),
                    full_text=self._indexed_full_text(key),
                    date=str(data.get("date", "")),
                    authors=tuple(author for author in creators if author),
                    metadata=dict(data),
                )
                if limit is not None and len(papers) >= limit:
                    return papers
        return papers
