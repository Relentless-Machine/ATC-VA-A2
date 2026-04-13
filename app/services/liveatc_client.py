from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from app.core.config import settings


@dataclass
class HistoricalAudioLink:
    url: str
    file_name: str


class LiveATCHTTPClient:
    """LiveATC page parser and downloader."""

    HREF_PATTERN = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
    MP3_PATTERN = re.compile(r"\.mp3($|\?)", re.IGNORECASE)
    MP3_FILE_PATTERN = re.compile(r"([A-Za-z0-9._-]+\.mp3)\b", re.IGNORECASE)

    def __init__(self):
        self.base_url = settings.a2_liveatc_base_url.rstrip("/")
        self.archive_base_url = settings.a2_liveatc_archive_base_url.rstrip("/")
        self.search_tpl = settings.a2_liveatc_search_url
        self.mount_ids = [item.strip() for item in settings.a2_liveatc_mount_ids.split(",") if item.strip()]
        self.realtime_stream_override = settings.a2_liveatc_realtime_stream_url.strip()

    def build_search_url(self, icao: str) -> str:
        return self.search_tpl.format(icao=icao.upper())

    @classmethod
    def _extract_hrefs(cls, html: str) -> list[str]:
        return [m.group(1).strip() for m in cls.HREF_PATTERN.finditer(html)]

    def _to_abs(self, href: str, source_url: str) -> str:
        if href.startswith("http://") or href.startswith("https://"):
            return href
        if href.startswith("/"):
            return urljoin(source_url, href)
        return urljoin(source_url, href)

    async def get_search_page(self, client: httpx.AsyncClient, icao: str) -> tuple[str, str]:
        search_url = self.build_search_url(icao)
        resp = await client.get(search_url)
        resp.raise_for_status()
        return search_url, resp.text

    async def resolve_realtime_stream_url(self, client: httpx.AsyncClient, icao: str) -> str | None:
        if self.realtime_stream_override:
            return self.realtime_stream_override

        for mount in self.mount_ids:
            for playlist_url in (f"{self.base_url}/play/{mount}.pls", f"{self.base_url}/play/{mount}.m3u"):
                resp = await client.get(playlist_url, follow_redirects=True)
                if resp.status_code >= 400:
                    continue
                playlist_urls = re.findall(r"https?://[^\s'\"<>]+", resp.text)
                for url in playlist_urls:
                    lowered = url.lower()
                    if any(k in lowered for k in ("liveatc", "stream", "mount", ".mp3", ".aac")):
                        return url

        candidate_listen_pages = [
            f"{self.base_url}/hlisten.php?mount={mount}&icao={icao.lower()}" for mount in self.mount_ids
        ]
        try:
            search_url, html = await self.get_search_page(client, icao)
            for href in self._extract_hrefs(html):
                if "listen.php?" in href.lower():
                    candidate_listen_pages.append(self._to_abs(href, search_url))
        except httpx.HTTPStatusError:
            pass

        for listen_url in candidate_listen_pages:
            listen_resp = await client.get(listen_url, follow_redirects=True)
            if listen_resp.status_code >= 400:
                continue
            text = listen_resp.text
            for candidate in self._extract_hrefs(text):
                absolute = self._to_abs(candidate, listen_url)
                lowered = absolute.lower()
                if any(k in lowered for k in ("audio", "stream", "mount", ".pls", ".m3u", ".mp3", "d.liveatc.net")):
                    return absolute
            http_urls = re.findall(r"https?://[^\s'\"<>]+", text)
            for item in http_urls:
                lowered = item.lower()
                if any(k in lowered for k in ("audio", "stream", "mount", ".pls", ".m3u", ".mp3", "d.liveatc.net")):
                    return item

        for mount in self.mount_ids:
            # 最后兜底：常见直连模式（部分节点可用）。
            for direct_url in (f"https://d.liveatc.net/{mount}", f"https://d.liveatc.net/{mount}.mp3"):
                probe = await client.get(direct_url, follow_redirects=True)
                if probe.status_code < 400:
                    return direct_url
        return None

    async def list_historical_links(self, client: httpx.AsyncClient, icao: str) -> list[HistoricalAudioLink]:
        candidate_pages = [f"{self.base_url}/archive.php?m={mount}" for mount in self.mount_ids]
        for mount in self.mount_ids:
            candidate_pages.append(f"{self.archive_base_url}/{mount}/")
        try:
            search_url, html = await self.get_search_page(client, icao)
            candidate_pages.append(search_url)
            for href in self._extract_hrefs(html):
                lowered = href.lower()
                if "archive" in lowered or "recordings" in lowered:
                    candidate_pages.append(self._to_abs(href, search_url))
        except httpx.HTTPStatusError:
            pass
        links: dict[str, HistoricalAudioLink] = {}
        for page_url in candidate_pages:
            resp = await client.get(page_url, follow_redirects=True)
            if resp.status_code >= 400:
                continue
            for href in self._extract_hrefs(resp.text):
                absolute = self._to_abs(href, page_url)
                if not self.MP3_PATTERN.search(absolute):
                    continue
                file_name = absolute.split("/")[-1].split("?")[0] or "liveatc.mp3"
                links[absolute] = HistoricalAudioLink(url=absolute, file_name=file_name)

            # 有些页面只显示文件名文本，不在 href 里；此处补充提取并拼接归档域名。
            for file_name in {m.group(1) for m in self.MP3_FILE_PATTERN.finditer(resp.text)}:
                for mount in self.mount_ids:
                    if file_name.lower().startswith(mount.lower()):
                        absolute = f"{self.archive_base_url}/{mount}/{file_name}"
                        links[absolute] = HistoricalAudioLink(url=absolute, file_name=file_name)
        return list(links.values())
