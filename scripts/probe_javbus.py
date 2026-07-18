"""探测 javbus 直连可用性，并用 bs4 解析详情页关键字段。

用法:
    uv run python scripts/probe_javbus.py
"""

from __future__ import annotations

import sys

import httpx
from bs4 import BeautifulSoup

URL = "https://www.javbus.com/CAWD-991"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def main() -> int:
    try:
        resp = httpx.get(
            URL,
            headers={"User-Agent": UA, "Cookie": "age_verified=1"},
            follow_redirects=True,
            timeout=20,
        )
    except httpx.HTTPError as exc:
        print(f"[ERROR] 请求失败: {exc}")
        return 1

    print(f"[INFO] HTTP 状态: {resp.status_code}")
    print(f"[INFO] 最终 URL: {resp.url}")
    print(f"[INFO] 响应长度: {len(resp.text)} 字节")
    if resp.status_code != 200:
        print("[WARN] 非 200，可能触发 Cloudflare 防护或域名失效")
        return 1

    soup = BeautifulSoup(resp.text, "html.parser")

    # 标题
    title = soup.select_one("title")
    print(f"[PARSE] <title>: {title.get_text(strip=True) if title else 'N/A'}")

    # 番号（详情页常用 .header h3 / .col-md-3.info h3 之类）
    h3 = soup.select_one(".info h3, .col-md-3.info h3")
    if h3:
        print(f"[PARSE] 番号(h3): {h3.get_text(strip=True)}")

    # 封面图
    cover = soup.select_one("a.bigImage, a[href*='cover']")
    if cover and cover.get("href"):
        print(f"[PARSE] 封面图: {cover['href']}")

    # 发布日期（info 区块内的日期文本）
    info_text = soup.select_one(".info, .col-md-3.info")
    if info_text:
        for line in info_text.get_text("\n").split("\n"):
            line = line.strip()
            if "发行" in line or "日期" in line or "-" in line and len(line) == 10:
                print(f"[PARSE] info 行: {line}")

    # 内容截图
    screenshots = [
        img.get("src") for img in soup.select("#sample-waterfall img, .screencap img")
    ]
    print(f"[PARSE] 截图数量: {len(screenshots)}")
    for s in screenshots[:5]:
        print(f"  - {s}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
