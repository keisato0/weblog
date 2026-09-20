#!/bin/sh
# ローカルでサイトを生成する。初回は .venv を作って markdown を入れる。
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r requirements.txt
fi
.venv/bin/python build.py
echo
echo "プレビュー: python3 -m http.server --directory _site 8000  →  http://localhost:8000/"
