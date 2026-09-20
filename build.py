#!/usr/bin/env python3
"""原稿/*.md からブログの静的HTMLを生成する。

- 記事タイトル: ファイル名（frontmatter に title: があればそちらを優先）
- 更新日時: git の最終コミット日時（未コミットのファイルはファイル更新時刻）
- 出力先: _site/
    _site/index.html                ホーム（記事一覧）
    _site/posts/<記事タイトル>/index.html   各記事
    _site/assets/style.css
"""

import html
import os
import shutil
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

import markdown

BLOG_TITLE = "ウェブログ"
ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "原稿"
OUT_DIR = ROOT / "_site"
ASSETS_DIR = ROOT / "assets"
JST = timezone(timedelta(hours=9))
DATE_FORMAT = "%Y年%m月%d日"


def split_frontmatter(text):
    """先頭の --- で囲まれた frontmatter を辞書として取り出す（単純な key: value のみ）。"""
    meta = {}
    if not text.startswith("---"):
        return meta, text
    lines = text.split("\n")
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() in ("---", "..."):
            end = i
            break
    if end is None:
        return meta, text
    for line in lines[1:end]:
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip("\"'")
    return meta, "\n".join(lines[end + 1:]).lstrip("\n")


def git_updated_at(path):
    """そのファイルの最終コミット日時。git 管理外・未コミットなら None。"""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(path)],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    if not out:
        return None
    return datetime.fromisoformat(out).astimezone(JST)


def updated_at(path, meta):
    """更新日時: frontmatter の updated: > git のコミット日時 > ファイル更新時刻。"""
    raw = meta.get("updated") or meta.get("date")
    if raw:
        try:
            return datetime.fromisoformat(raw).replace(tzinfo=JST)
        except ValueError:
            print(f"  警告: updated の日付を解釈できません: {raw}", file=sys.stderr)
    return git_updated_at(path) or datetime.fromtimestamp(path.stat().st_mtime, JST)


def page(title, body, depth):
    """共通のHTMLの骨格。depth はサイトルートまでの階層数（相対リンク用）。"""
    up = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{up}assets/style.css">
</head>
<body>
<header class="site-header">
  <a class="site-title" href="{up}">{html.escape(BLOG_TITLE)}</a>
</header>
<main>
{body}
</main>
</body>
</html>
"""


def build():
    if not SRC_DIR.is_dir():
        sys.exit(f"原稿ディレクトリが見つかりません: {SRC_DIR}")

    posts = []
    for path in sorted(SRC_DIR.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, body_md = split_frontmatter(text)
        title = meta.get("title") or path.stem
        posts.append({
            "title": title,
            "updated": updated_at(path, meta),
            # Obsidian と同じく、1行の改行をそのまま改行として表示する
            "body": markdown.markdown(body_md, extensions=["extra", "sane_lists", "nl2br"]),
        })

    posts.sort(key=lambda p: p["updated"], reverse=True)

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    shutil.copytree(ASSETS_DIR, OUT_DIR / "assets")

    rows = []
    for post in posts:
        href = "posts/" + urllib.parse.quote(post["title"]) + "/"
        date = post["updated"].strftime(DATE_FORMAT)
        rows.append(
            f'  <li class="post-row">\n'
            f'    <a class="post-link" href="{href}">{html.escape(post["title"])}</a>\n'
            f'    <time class="post-date" datetime="{post["updated"].isoformat()}">{date}</time>\n'
            f'  </li>'
        )
    index_body = '<ul class="post-list">\n' + "\n".join(rows) + "\n</ul>"
    (OUT_DIR / "index.html").write_text(page(BLOG_TITLE, index_body, 0), encoding="utf-8")

    for post in posts:
        date = post["updated"].strftime(DATE_FORMAT)
        body = (
            f'<article class="post">\n'
            f'  <h1 class="post-title">{html.escape(post["title"])}</h1>\n'
            f'  <time class="post-date" datetime="{post["updated"].isoformat()}">{date}</time>\n'
            f'  <div class="post-body">\n{post["body"]}\n  </div>\n'
            f'</article>'
        )
        out = OUT_DIR / "posts" / post["title"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page(f'{post["title"]} - {BLOG_TITLE}', body, 2), encoding="utf-8")

    print(f"{len(posts)} 件の記事を {OUT_DIR} に生成しました")
    for post in posts:
        print(f"  - {post['title']} ({post['updated'].strftime('%Y-%m-%d')})")


if __name__ == "__main__":
    build()
