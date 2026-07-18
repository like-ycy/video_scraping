"""从 javbus 刮削视频根目录下各演员目录的元数据与图片，生成 JSON 与预览页。

布局约定:
    <dir>/
        index.json              总索引（演员列表 + 各演员汇总 json 路径）
        index.html              预览页（ROOT 已由本脚本写入绝对路径）
        演员名称/
            演员名称.json       该演员汇总：videos 数组
            <番号>.mp4
            covers/<番号>.jpg
            images/<番号>_N.jpg

用法:
    uv run python src/generate.py --dir <视频根目录>
"""

from __future__ import annotations

import argparse
import json
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
TEMPLATE_HTML = ROOT / "src" / "index.html"


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
        print(f"[ERROR] 无法连接 javbus ({url}): {exc}")
        sys.exit(1)
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
        fanha = mp4.stem
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


def export_html(videos_dir: Path) -> None:
    if not TEMPLATE_HTML.exists():
        print(f"[WARN] 模板缺失，跳过 HTML 输出: {TEMPLATE_HTML}")
        return
    html = TEMPLATE_HTML.read_text(encoding="utf-8")
    # ROOT 用正斜杠以外的反斜杠，且转义供 JS 字符串使用
    root_js = str(videos_dir.resolve()).replace("\\", "\\\\")
    html = html.replace("__ROOT__", root_js)
    out = videos_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"[OK] 写出预览页 {out}")


def main() -> int:
    parser = argparse.ArgumentParser(description="从 javbus 刮削视频元数据并生成 JSON/预览页")
    parser.add_argument(
        "--dir",
        required=True,
        help="视频根目录（必填）",
    )
    args = parser.parse_args()

    videos_dir = Path(args.dir)
    if not videos_dir.exists():
        print(f"[ERROR] 找不到目录: {videos_dir}")
        return 1

    index_entries = []
    for actor_dir in sorted(p for p in videos_dir.iterdir() if p.is_dir()):
        if not any(actor_dir.glob("*.mp4")):
            continue
        entry = scrape_actress(actor_dir)
        if entry:
            index_entries.append(entry)

    index_path = videos_dir / "index.json"
    index_path.write_text(
        json.dumps({"actresses": index_entries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] 写入总索引 {index_path} ({len(index_entries)} 个演员)")

    export_html(videos_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
