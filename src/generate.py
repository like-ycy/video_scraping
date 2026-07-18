"""从 javlibrary 刮削视频根目录下各演员目录的元数据与图片，生成 JSON 与预览页。

布局约定:
    <dir>/
        index.json              总索引（演员列表 + 各演员汇总 json 路径）
        index.html              预览页（ROOT 已由本脚本写入绝对路径）
        preview.bat             预览启动器（由本脚本复制并填入 python 路径）
        演员名称/
            meta/
                演员名称.json       该演员汇总：videos 数组
                <视频名>/
                    cover.jpg
                    images/N.jpg
            <视频名>.mp4

用法:
    python src/generate.py --dir <视频根目录>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import httpx
from bs4 import BeautifulSoup
from seleniumbase import BaseCase, SB

SITE = "https://www.javlibrary.com"
SEARCH_URL = f"{SITE}/cn/vl_searchbyid.php?keyword="

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_HTML = ROOT / "src" / "index.html"
PREVIEW_FILES = ("preview.bat", "preview_server.py")


def fetch_html(sb: BaseCase, url: str) -> str | None:
    try:
        sb.activate_cdp_mode(url)
        sb.sleep(5)
        sb.solve_captcha()
        sb.sleep(8)
        sb.solve_captcha()
        sb.sleep(3)
        try:
            sb.click('input[value="我同意"]', timeout=6)
            sb.sleep(3)
        except Exception:
            pass
        return sb.get_page_source()
    except Exception as exc:
        print(f"[ERROR] 无法加载页面 ({url}): {exc}")
        return None


def search_detail_url(sb: BaseCase, fanha: str) -> str | None:
    html = fetch_html(sb, SEARCH_URL + fanha.lower())
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    link = soup.select_one('a[href*="/cn/jav"]')
    if not link:
        print(f"  [ERROR] 搜索结果未找到详情链接: {fanha}")
        return None
    href = str(link.get("href", ""))
    if not href:
        print(f"  [ERROR] 搜索结果链接为空: {fanha}")
        return None
    return SITE + href


def parse_detail(html: str, fanha: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.select_one("#video_title h3 a")
    title = title_tag.get_text(strip=True) if title_tag else ""

    def text_after(div_id: str) -> str:
        # 文本可能在 td.text 直接，也可能在外层 td 内包的 span.text（javlibrary 实际结构）
        node = soup.select_one(f"div#{div_id} td.text") or soup.select_one(
            f"div#{div_id} td .text"
        )
        return node.get_text(strip=True) if node else ""

    release_date = text_after("video_date")
    length = text_after("video_length").replace("分钟", "").strip()

    genres = [a.get_text(strip=True) for a in soup.select("#video_genres .genre a")]
    cast = [
        a.get_text(strip=True) for a in soup.select("#video_cast span.cast span.star a")
    ]

    cover_tag = soup.select_one("#video_jacket img#video_jacket_img")
    cover = str(cover_tag.get("src", "")) if cover_tag else ""
    if cover.startswith("//"):
        cover = "https:" + cover

    screenshots = []
    for img in soup.select("div.previewthumbs img"):
        src = str(img.get("src", ""))
        if src.startswith("//"):
            src = "https:" + src
        if src:
            screenshots.append(src)

    return {
        "fanha": fanha,
        "title": title,
        "release_date": release_date,
        "length": length,
        "genres": genres,
        "cast": cast,
        "cover": cover,
        "screenshots": screenshots,
    }


def download(url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=30)
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
    with SB(uc=True, test=True, locale="en", headless=True) as sb:
        for mp4 in sorted(actor_dir.glob("*.mp4")):
            fanha = mp4.stem.lower().replace("-c", "")
            print(f"[INFO] 刮削 {actor_dir.name}/{fanha}")

            detail_url = search_detail_url(sb, fanha)
            if not detail_url:
                continue
            html = fetch_html(sb, detail_url)
            if not html:
                continue
            data = parse_detail(html, fanha)

            if not data["title"] or not data["cover"]:
                print(f"  [ERROR] 解析不到数据（标题/封面缺失），跳过 {fanha}")
                continue

            video_dir = mp4.stem
            cover_rel = f"meta/{video_dir}/cover.jpg"
            if data["cover"]:
                download(data["cover"], actor_dir / cover_rel)
            data["cover"] = cover_rel

            shot_rels = []
            for i, shot in enumerate(data["screenshots"], 1):
                rel = f"meta/{video_dir}/images/{i}.jpg"
                if download(shot, actor_dir / rel):
                    shot_rels.append(rel)
            data["screenshots"] = shot_rels

            data["video_file"] = mp4.name
            # 播放用绝对路径，前端直接 potplayer:// + 该字段，避免 ROOT/目录拼接错误。
            # PotPlayer 在 Windows 上需要反斜杠路径，故转回反斜杠。
            data["video_path"] = str(mp4.resolve()).replace("/", "\\")
            data["file_size"] = mp4.stat().st_size
            videos.append(data)

    if not videos:
        return None

    summary = {"actress": actor_dir.name, "videos": videos}
    out = actor_dir / "meta" / f"{actor_dir.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 写入 {out} ({len(videos)} 个视频)")
    return {
        "name": actor_dir.name,
        "json": f"{actor_dir.name}/meta/{actor_dir.name}.json",
        "video_count": len(videos),
    }


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
    parser = argparse.ArgumentParser(
        description="从 javbus 刮削视频元数据并生成 JSON/预览页"
    )
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
    copy_preview_files(videos_dir)
    return 0


def copy_preview_files(videos_dir: Path) -> None:
    for name in PREVIEW_FILES:
        src = ROOT / name
        if not src.exists():
            print(f"[WARN] 预览脚本缺失，跳过复制: {src}")
            continue
        text = src.read_text(encoding="utf-8")
        if name == "preview.bat":
            # 视频目录由 bat 内 %~dp0 自适应，避免把中文绝对路径写死进 bat。
            text = text.replace("set PYTHON_EXE=", f"set PYTHON_EXE={sys.executable}")
        dest = videos_dir / name
        dest.write_text(text, encoding="utf-8")
        print(f"[OK] 已复制预览脚本到 {dest}")


if __name__ == "__main__":
    sys.exit(main())
