from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, quote, urlparse
from urllib.parse import urljoin

import httpx

from app.core.config import settings

try:
    import cloudscraper
except Exception:  # pragma: no cover - optional dependency
    cloudscraper = None

@dataclass
class HistoricalAudioLink:
    url: str
    file_name: str


class LiveATCHTTPClient:
    """LiveATC page parser and downloader."""

    HREF_PATTERN = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
    MP3_PATTERN = re.compile(r"\.mp3($|\?)", re.IGNORECASE)
    MP3_FILE_PATTERN = re.compile(r"([A-Za-z0-9._-]+\.mp3)\b", re.IGNORECASE)
    SELECTED_OPTION_PATTERN = re.compile(
        r"<option\b[^>]*\bselected\b[^>]*\bvalue=[\"']?([^\"'>\s]+)",
        re.IGNORECASE,
    )

    def __init__(self):
        self.base_url = settings.a2_liveatc_base_url.rstrip("/")
        self.archive_base_url = settings.a2_liveatc_archive_base_url.rstrip("/")
        self.search_tpl = settings.a2_liveatc_search_url
        self.mount_ids = [item.strip() for item in settings.a2_liveatc_mount_ids.split(",") if item.strip()]
        self.archive_file_prefixes = [
            item.strip() for item in settings.a2_liveatc_archive_file_prefixes.split(",") if item.strip()
        ]
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

    @staticmethod
    def _cookie_header_from_client(client: httpx.AsyncClient) -> str:
        pairs = []
        for cookie in client.cookies.jar:
            if cookie.name and cookie.value:
                pairs.append(f"{cookie.name}={cookie.value}")
        return "; ".join(pairs)

    @staticmethod
    def cookie_count(client: httpx.AsyncClient) -> int:
        return sum(1 for cookie in client.cookies.jar if cookie.name and cookie.value)

    @staticmethod
    def _infer_archive_dir(station: str, archive_identifier: str) -> str:
        prefix = archive_identifier.split("-", 1)[0].strip().lower()
        if len(prefix) == 4 and prefix.isalnum():
            return prefix
        station_token = re.split(r"[_-]", station.strip().lower())[0]
        letters = "".join(ch for ch in station_token if ch.isalpha())
        if len(letters) >= 4:
            return letters[:4]
        return station_token or "unknown"

    @classmethod
    def _selected_archive_identifier(cls, html: str) -> str | None:
        matched = cls.SELECTED_OPTION_PATTERN.search(html)
        return matched.group(1).strip() if matched else None

    @staticmethod
    def _last_finished_half_hour(now: datetime | None = None) -> datetime:
        value = now or datetime.now(timezone.utc)
        value = value - timedelta(minutes=30)
        floored_minute = (value.minute // 30) * 30
        return value.replace(minute=floored_minute, second=0, microsecond=0)

    def _recent_archive_candidates(
        self, *, station: str, archive_identifier: str, now: datetime | None = None
    ) -> list[HistoricalAudioLink]:
        archive_dir = self._infer_archive_dir(station=station, archive_identifier=archive_identifier)
        slots = max(settings.a2_historical_candidate_slots, 1)
        start_slot = self._last_finished_half_hour(now)
        candidates: list[HistoricalAudioLink] = []
        for index in range(slots):
            slot = start_slot - timedelta(minutes=30 * index)
            file_name = f"{archive_identifier}-{slot.strftime('%b-%d-%Y-%H%MZ')}.mp3"
            encoded_name = quote(file_name, safe="-_.()")
            candidates.append(
                HistoricalAudioLink(
                    url=f"{self.archive_base_url}/{archive_dir}/{encoded_name}",
                    file_name=file_name,
                )
            )
        return candidates

    @staticmethod
    def _mount_from_archive_page_url(page_url: str) -> str:
        parsed = urlparse(page_url)
        mount = parse_qs(parsed.query).get("m", [""])[0].strip()
        return mount or page_url

    async def ensure_public_session_cookie(self, client: httpx.AsyncClient, icao: str) -> bool:
        seed_urls = [
            self.base_url,
            self.build_search_url(icao),
            f"{self.base_url}/archive.php?m={self.mount_ids[0]}" if self.mount_ids else self.base_url,
        ]
        for url in seed_urls:
            try:
                await client.get(url, follow_redirects=True)
            except httpx.HTTPError:
                # 尝试 cloudscraper 回退以获取会话 cookie
                if cloudscraper is not None:
                    try:
                        sc = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
                        sc.get(url, timeout=10)
                    except Exception:
                        pass
                continue
        return bool(self._cookie_header_from_client(client))

    def _cloudscraper_get_text(self, url: str, headers: dict | None = None) -> tuple[int, str, str | None]:
        """同步 cloudscraper 请求，返回 (status_code, text, cookie_header)"""
        if cloudscraper is None:
            return 0, "", None
        try:
            sc = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
            if headers:
                sc.headers.update(headers)
            r = sc.get(url, timeout=20)
            cookie = None
            if hasattr(sc, 'cookies'):
                # 构建 Cookie header
                try:
                    cookie = "; ".join(f"{c.name}={c.value}" for c in sc.cookies.jar if c.name and c.value)
                except Exception:
                    cookie = None
            return getattr(r, 'status_code', 0) or 0, getattr(r, 'text', '') or '', cookie
        except Exception:
            return 0, "", None

    async def enrich_headers_with_session_cookie(
        self, client: httpx.AsyncClient, base_headers: dict[str, str]
    ) -> dict[str, str]:
        merged = dict(base_headers)
        cookie_header = self._cookie_header_from_client(client)
        if cookie_header:
            merged["Cookie"] = cookie_header
        return merged

    async def get_search_page(self, client: httpx.AsyncClient, icao: str) -> tuple[str, str]:
        search_url = self.build_search_url(icao)
        try:
            resp = await client.get(search_url)
            resp.raise_for_status()
            return search_url, resp.text
        except httpx.HTTPStatusError as exc:
            # 如果被 403 拦截，尝试 cloudscraper 回退（同步）
            if cloudscraper is not None and getattr(exc.response, 'status_code', None) == 403:
                status, text, cookie = self._cloudscraper_get_text(search_url, headers={
                    'User-Agent': settings.a2_http_user_agent,
                    'Referer': self.base_url,
                })
                if status and status < 400:
                    return search_url, text
            raise

    async def resolve_realtime_stream_url(self, client: httpx.AsyncClient, icao: str) -> str | None:
        if self.realtime_stream_override:
            return self.realtime_stream_override

        for mount in self.mount_ids:
            for playlist_url in (f"{self.base_url}/play/{mount}.pls", f"{self.base_url}/play/{mount}.m3u"):
                try:
                    resp = await client.get(playlist_url, follow_redirects=True)
                except httpx.HTTPError:
                    # 回退到 cloudscraper 同步请求
                    if cloudscraper is not None:
                        status, text, cookie = self._cloudscraper_get_text(playlist_url, headers={'User-Agent': settings.a2_http_user_agent})
                        if status and status < 400:
                            resp = type('R', (), {'status_code': status, 'text': text})()
                        else:
                            continue
                    else:
                        continue
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
            # 如果 cloudscraper 可用，尝试直接用 cloudscraper 拉取 search page
            if cloudscraper is not None:
                status, text, cookie = self._cloudscraper_get_text(self.build_search_url(icao), headers={'User-Agent': settings.a2_http_user_agent})
                if status and status < 400:
                    for href in self._extract_hrefs(text):
                        if "listen.php?" in href.lower():
                            candidate_listen_pages.append(self._to_abs(href, self.build_search_url(icao)))
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
                if await self._probe_stream_url(client, direct_url):
                    return direct_url
        return None

    @staticmethod
    async def _probe_stream_url(client: httpx.AsyncClient, url: str) -> bool:
        try:
            async with client.stream("GET", url, follow_redirects=True) as resp:
                if resp.status_code >= 400:
                    return False
                async for chunk in resp.aiter_bytes(chunk_size=1):
                    return bool(chunk)
                return True
        except httpx.HTTPError:
            return False

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
            try:
                resp = await client.get(page_url, follow_redirects=True)
            except httpx.HTTPError:
                # cloudscraper 回退
                if cloudscraper is not None:
                    status, text, cookie = self._cloudscraper_get_text(page_url, headers={'User-Agent': settings.a2_http_user_agent})
                    if status and status < 400:
                        resp = type('R', (), {'status_code': status, 'text': text})()
                    else:
                        continue
                else:
                    continue
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
                        archive_dir = self._infer_archive_dir(station=mount, archive_identifier=file_name)
                        absolute = f"{self.archive_base_url}/{archive_dir}/{quote(file_name, safe='-_.()')}"
                        links[absolute] = HistoricalAudioLink(url=absolute, file_name=file_name)
            if "archive.php" in page_url.lower():
                archive_identifier = self._selected_archive_identifier(resp.text)
                if archive_identifier:
                    station = self._mount_from_archive_page_url(page_url)
                    for item in self._recent_archive_candidates(station=station, archive_identifier=archive_identifier):
                        links.setdefault(item.url, item)
        for mount, archive_identifier in zip(self.mount_ids, self.archive_file_prefixes):
            for item in self._recent_archive_candidates(station=mount, archive_identifier=archive_identifier):
                links.setdefault(item.url, item)
        return list(links.values())
