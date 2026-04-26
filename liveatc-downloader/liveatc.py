import re
from pathlib import Path
from urllib.parse import quote
from typing import Generator

import requests
import urllib.request
from bs4 import BeautifulSoup

try:
    import cloudscraper
except Exception:
    cloudscraper = None


def _build_session(user_agent: str | None = None, cookie: str | None = None) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent
                          or (
                              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                          ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://www.liveatc.net/",
            "Upgrade-Insecure-Requests": "1",
        }
    )
    if cookie:
        session.headers["Cookie"] = cookie
    return session


def _build_cloudscraper(user_agent: str | None = None, cookie: str | None = None):
    if cloudscraper is None:
        return None
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    scraper.headers.update(
        {
            "User-Agent": user_agent
                          or (
                              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                          ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://www.liveatc.net/",
            "Upgrade-Insecure-Requests": "1",
        }
    )
    if cookie:
        scraper.headers["Cookie"] = cookie
    return scraper


def _request_liveatc(url: str, user_agent: str | None = None, cookie: str | None = None):
    # 第一步：先用普通 requests 尝试
    session = _build_session(user_agent=user_agent, cookie=cookie)
    resp = None
    try:
        print("正在尝试普通请求...")
        session.get("https://www.liveatc.net/", timeout=20, allow_redirects=True)
        resp = session.get(url, timeout=20, allow_redirects=True)
        if resp.status_code == 200:
            print("普通请求成功！")
            return resp
        else:
            print(f"普通请求失败，状态码: {resp.status_code}")
    except Exception as e:
        print(f"普通请求发生异常: {e}")

    # 第二步：如果有提供Cookie，就不要再试cloudscraper了
    if cookie:
        print("已提供Cookie但仍然失败，请检查Cookie是否有效。")
        return resp

    # 第三步：尝试 cloudscraper（仅当没有提供Cookie时）
    print("正在尝试使用 cloudscraper 绕过 Cloudflare...")
    scraper = _build_cloudscraper(user_agent=user_agent, cookie=cookie)
    if scraper is None:
        print("错误: 未安装 cloudscraper，无法继续。")
        return resp

    try:
        scraper.get("https://www.liveatc.net/", timeout=20, allow_redirects=True)
        resp = scraper.get(url, timeout=20, allow_redirects=True)
        if resp.status_code == 200:
            print("cloudscraper 请求成功！")
            return resp
        else:
            print(f"cloudscraper 也失败了，状态码: {resp.status_code}")
            print("建议使用手动Cookie的方式。")
            return resp
    except Exception as e:
        print(f"cloudscraper 发生异常: {e}")
        return None


def get_stations(icao, user_agent: str | None = None, cookie: str | None = None) -> Generator[dict, None, None]:
    page = _request_liveatc(f'https://www.liveatc.net/search/?icao={icao}', user_agent=user_agent, cookie=cookie)

    # --- 修复点 2: 检查 page 是否为空 ---
    if page is None:
        raise Exception("所有请求方式均失败，无法获取页面。")

    page.raise_for_status()
    soup = BeautifulSoup(page.content, 'html.parser')

    stations = soup.find_all('table', class_='body', border='0', padding=lambda x: x != '0')
    freqs = soup.find_all('table', class_='freqTable', colspan='2')

    for table, freqs in zip(stations, freqs):
        title = table.find('strong').text
        up = table.find('font').text == 'UP'
        href = table.find('a', href=lambda x: x and x.startswith('/archive.php')).attrs['href']

        identifier = re.findall(r'/archive.php\?m=([a-zA-Z0-9_]+)', href)[0]

        frequencies = []
        rows = freqs.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            freq_title = cols[0].text
            freq_frequency = cols[1].text

            frequencies.append({'title': freq_title, 'frequency': freq_frequency})

        yield {'identifier': identifier, 'title': title, 'frequencies': frequencies, 'up': up}


def _infer_archive_dir(station: str, archive_identifier: str) -> str:
    prefix = archive_identifier.split('-', 1)[0].strip().lower()
    if len(prefix) == 4 and prefix.isalnum():
        return prefix
    station_token = re.split(r'[_-]', station.strip().lower())[0]
    letters = ''.join(ch for ch in station_token if ch.isalpha())
    if len(letters) >= 4:
        return letters[:4]
    return station_token or "unknown"


def download_archive(station, date, time, output_dir=".", user_agent: str | None = None, cookie: str | None = None):
    page = _request_liveatc(
        f'https://www.liveatc.net/archive.php?m={station}',
        user_agent=user_agent,
        cookie=cookie,
    )

    if page is None:
        raise Exception("所有请求方式均失败，无法获取页面。")

    page.raise_for_status()
    soup = BeautifulSoup(page.content, 'html.parser')
    archive_identifer = soup.find('option', selected=True).attrs['value']

    filename = f'{archive_identifer}-{date}-{time}.mp3'
    archive_dir = _infer_archive_dir(station=station, archive_identifier=archive_identifer)

    out_dir = Path(output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    encoded_name = quote(filename, safe="-_.()")
    url = f'https://archive.liveatc.net/{archive_dir}/{encoded_name}'
    print(f"正在下载: {url}")

    urllib.request.urlretrieve(url, str(path))
    print(f"成功保存到: {path}")