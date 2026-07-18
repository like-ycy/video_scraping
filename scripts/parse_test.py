"""用本地样本 HTML 验证 bs4 解析逻辑（不依赖网络）。

用法:
    uv run python scripts/parse_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from bs4 import BeautifulSoup

SAMPLE = Path(__file__).parent / "_sample_cawd991.html"


def parse(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # 标题（h3）
    h3 = soup.select_one("h3")
    title = h3.get_text(strip=True) if h3 else None

    # 番号 / 发布日期 / 时长：info 区块内 <p> 中 "header" 标签后的文本
    info = soup.select_one(".col-md-3.info")
    fanha = release_date = None
    if info:
        for p in info.select("p"):
            header = p.select_one(".header")
            if not header:
                continue
            key = header.get_text(strip=True)
            if "識別碼" in key:
                spans = p.select("span")
                fanha = spans[-1].get_text(strip=True) if len(spans) > 1 else p.get_text(strip=True).replace(key, "").strip()
            elif "發行日期" in key:
                release_date = p.get_text(strip=True).replace(key, "").strip()

    # 封面图：a.bigImage 的 href
    cover = soup.select_one("a.bigImage")
    cover_href = cover["href"] if cover and cover.get("href") else None

    # 演员：star-name 下的 a title
    actress = None
    star = soup.select_one(".star-name a")
    if star:
        actress = star.get("title") or star.get_text(strip=True)

    # 内容截图：#sample-waterfall a.sample-box 的 href
    screenshots = [a["href"] for a in soup.select("#sample-waterfall a.sample-box") if a.get("href")]

    return {
        "title": title,
        "fanha": fanha,
        "release_date": release_date,
        "cover": cover_href,
        "actress": actress,
        "screenshots": screenshots,
    }


def main() -> int:
    if not SAMPLE.exists():
        print(f"[ERROR] 样本不存在: {SAMPLE}")
        return 1
    result = parse(SAMPLE.read_text(encoding="utf-8"))
    import json

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
