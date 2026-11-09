#!/bin/sh
# Google フォトで選んだ写真をブログに取り込む。
#
# Finder でこのファイルをダブルクリックすると、ターミナルが開いて実行される。
# 取り込みが終わると、原稿に貼り付ける文字列がクリップボードに入る。

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin:/opt/homebrew/bin"
cd "$(dirname "$0")" || exit 1

echo
echo "=== 写真を取り込む ==="
echo
python3 import_photos.py
status=$?
echo
exit $status
