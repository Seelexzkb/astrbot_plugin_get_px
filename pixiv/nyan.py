from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import aiohttp

from astrbot.api import logger


LOG_PREFIX = "[GetPx]"
DEFAULT_API_URL = "https://sex.nyan.run/api/v2/"
MAX_NUM = 10
MAX_TAGS = 10


@dataclass
class NyanRunClient:
    """Small async client for the nyan.run (sex.nyan.run) setu API."""

    api_url: str = DEFAULT_API_URL
    r18: bool = False
    request_timeout: float = 30.0
    _session: aiohttp.ClientSession | None = field(default=None, repr=False)
    _closed: bool = field(default=False, repr=False)

    @property
    def available(self) -> bool:
        return bool(self.api_url.strip()) and not self._closed

    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._closed:
            raise RuntimeError("Nyan.run 客户端已关闭")
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    @staticmethod
    def _normalize_tags(tags: object) -> list[str]:
        items = tags if isinstance(tags, (list, tuple)) else [tags]
        result: list[str] = []
        for item in items:
            value = str(item or "").strip()
            if value and value not in result:
                result.append(value)
            if len(result) >= MAX_TAGS:
                break
        return result

    async def fetch(
        self,
        *,
        tags: object = (),
        count: int = 20,
    ) -> list[dict[str, Any]]:
        if not self.available:
            raise RuntimeError("Nyan.run API 未配置")
        tag_list = self._normalize_tags(tags)
        params: list[tuple[str, str]] = [
            ("r18", "true" if self.r18 else "false"),
            ("num", str(max(1, min(int(count), MAX_NUM)))),
        ]
        # 数组参数通过追加同名参数发送；服务端多 tag 语义不明，
        # 这里请求后还会在本地校验「同时包含所有标签」。
        params.extend(("tag", tag) for tag in tag_list)

        session = self._ensure_session()
        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        async with session.get(self.api_url, params=params, timeout=timeout) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Nyan.run API HTTP {resp.status}")
            payload = await resp.json(content_type=None)
        if not isinstance(payload, dict):
            raise RuntimeError("Nyan.run API 返回格式无效")
        if not payload.get("success"):
            raise RuntimeError(
                f"Nyan.run API 请求失败: status={payload.get('status')} "
                f"message={payload.get('message') or ''}"
            )
        items = [self._normalize(item) for item in payload.get("data") or []]
        if tag_list:
            wanted = {tag.casefold() for tag in tag_list}
            items = [
                item
                for item in items
                if wanted.issubset(
                    tag.get("name", "").casefold()
                    for tag in item.get("tags") or []
                )
            ]
        return items

    async def search(
        self, tags: object, *, count: int = 20
    ) -> list[dict[str, Any]]:
        return await self.fetch(tags=tags, count=count)

    async def random(self, *, count: int = 20) -> list[dict[str, Any]]:
        return await self.fetch(count=count)

    @staticmethod
    def _normalize(item: dict[str, Any]) -> dict[str, Any]:
        pid = str(item.get("pid") or "")
        url = str(item.get("url") or "")
        return {
            "id": pid,
            "pid": pid,
            "page": 0,
            "title": str(item.get("title") or "无标题"),
            "user": {
                "id": str(item.get("author_uid") or ""),
                "name": str(item.get("author") or ""),
            },
            # Nyan.run 不返回 x_restrict；r18 开关在请求侧控制。
            "width": item.get("width") or 0,
            "height": item.get("height") or 0,
            "tags": [{"name": str(tag)} for tag in item.get("tags") or []],
            "type": "illust",
            "meta_single_page": {"original_image_url": url},
            "image_urls": {"large": url, "medium": url, "square_medium": url},
            "_source": "nyan_run",
        }

    async def close(self) -> None:
        self._closed = True
        session, self._session = self._session, None
        if session is not None and not session.closed:
            try:
                await session.close()
            except Exception as exc:
                logger.warning(
                    f"{LOG_PREFIX} Nyan.run 客户端关闭失败: "
                    f"error_type={type(exc).__name__}"
                )
