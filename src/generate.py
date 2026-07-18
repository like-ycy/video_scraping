"""从 javbus 刮削 videos/ 下各演员目录的视频元数据与图片，生成 JSON。

布局约定:
    videos/
        index.json              总索引（演员列表 + 各演员汇总 json 路径）
        演员名称/
            演员名称.json       该演员汇总：videos 数组
            <番号>.mp4
            covers/<番号>.jpg
            images/<番号>_N.jpg

用法:
    uv run python src/generate.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.javbus.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
COOKIES = {"age_verified": "1"}

ROOT = Path(__file__).resolve().parent.parent
VIDEOS_DIR = ROOT / "videos"


def extract_fanha(filename: str) -> str:
    return Path(filename).stem


def fetch_html(url: str) -> str | None:
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": UA, "Referer": BASE_URL + "/"},
            cookies=COOKIES,
            follow_redirects=True,
            timeout=20,
        )
    except httpx.HTTPError as exc:
        print(f"  [WARN] 请求失败 {url}: {exc}")
        return None
    if resp.status_code != 200:
        print(f"  [WARN] 非 200 ({resp.status_code}): {url}")
        return None
    return resp.text


def parse_detail(html: str, fanha: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.select_one("h3")
    title = title_tag.get_text(strip=True) if title_tag else ""

    info = soup.select_one(".col-md-3.info")
    release_date = None
    if info:
        for p in info.select("p"):
            header = p.select_one(".header")
            if not header:
                continue
            key = header.get_text(strip=True)
            if "發行日期" in key or "发行日期" in key:
                release_date = p.get_text(strip=True).replace(key, "").strip()

    cover_tag = soup.select_one("a.bigImage")
    cover = cover_tag["href"] if cover_tag and cover_tag.get("href") else None

    screenshots = [
        a["href"] for a in soup.select("#sample-waterfall a.sample-box") if a.get("href")
    ]

    return {
        "fanha": fanha,
        "title": title,
        "release_date": release_date,
        "cover": cover,
        "screenshots": screenshots,
    }


def download(url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": UA, "Referer": BASE_URL + "/"},
            cookies=COOKIES,
            follow_redirects=True,
            timeout=30,
        )
    except httpx.HTTPError as exc:
        print(f"  [WARN] 下载失败 {url}: {exc}")
        return False
    if resp.status_code != 200:
        print(f"  [WARN] 下载非 200 ({resp.status_code}): {url}")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return True


def scrape_actress(actor_dir: Path) -> dict | None:
    videos = []
    for mp4 in sorted(actor_dir.glob("*.mp4")):
        fanha = extract_fanha(mp4.name)
        print(f"[INFO] 刮削 {actor_dir.name}/{fanha}")

        html = fetch_html(f"{BASE_URL}/{fanha}")
        if not html:
            continue
        data = parse_detail(html, fanha)

        cover_rel = f"covers/{fanha}.jpg"
        if data["cover"]:
            cover_url = urljoin(BASE_URL, data["cover"])
            download(cover_url, actor_dir / cover_rel)
        data["cover"] = cover_rel

        shot_rels = []
        for i, shot in enumerate(data["screenshots"], 1):
            rel = f"images/{fanha}_{i}.jpg"
            if download(shot, actor_dir / rel):
                shot_rels.append(rel)
        data["screenshots"] = shot_rels

        data["video_file"] = mp4.name
        data["file_size"] = mp4.stat().st_size
        videos.append(data)

    if not videos:
        return None

    summary = {"actress": actor_dir.name, "videos": videos}
    out = actor_dir / f"{actor_dir.name}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 写入 {out} ({len(videos)} 个视频)")
    return {"name": actor_dir.name, "json": f"{actor_dir.name}/{actor_dir.name}.json", "video_count": len(videos)}


def main() -> int:
    if not VIDEOS_DIR.exists():
        print(f"[ERROR] 找不到 videos 目录: {VIDEOS_DIR}")
        return 1

    index_entries = []
    for actor_dir in sorted(p for p in VIDEOS_DIR.iterdir() if p.is_dir()):
        if not any(actor_dir.glob("*.mp4")):
            continue
        entry = scrape_actress(actor_dir)
        if entry:
            index_entries.append(entry)

    index_path = VIDEOS_DIR / "index.json"
    index_path.write_text(
        json.dumps({"actresses": index_entries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] 写入总索引 {index_path} ({len(index_entries)} 个演员)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
