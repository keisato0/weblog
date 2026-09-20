#!/bin/sh
# 「ウェブログを公開.app」を ~/Applications に作り直す。
# アプリを消してしまったときや、置き場所を変えたときに実行する。
set -e
REPO=$(cd "$(dirname "$0")/.." && pwd)
APP="$HOME/Applications/ウェブログを公開.app"
TMP=$(mktemp -t publish-app).applescript

sed "s|__REPO__|$REPO|" "$REPO/tools/publish-app.applescript" > "$TMP"
mkdir -p "$HOME/Applications"
rm -rf "$APP"
/usr/bin/osacompile -o "$APP" "$TMP"
rm -f "$TMP"

echo "作成しました: $APP"
