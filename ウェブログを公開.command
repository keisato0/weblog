#!/bin/sh
# ウェブログを公開する。
#
# Finder でこのファイルをダブルクリックすると、ターミナルが開いて実行される。
# 原稿の変更をコミットして push し、GitHub Pages への反映まで見届ける。
# ターミナルから ./ウェブログを公開.command と打っても同じ。

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin:/opt/homebrew/bin"
GIT=/usr/bin/git
SITE_URL="https://keisato0.github.io/weblog/"
REPO=$(cd "$(dirname "$0")" && pwd)
cd "$REPO" || exit 1

notify() {
  /usr/bin/osascript -e "display notification \"$1\" with title \"ウェブログ\"" >/dev/null 2>&1
}

latest_run() {
  # 最新のビルドの「ID 状態 結果」を返す。gh がなければ何も返さない
  gh api "repos/keisato0/weblog/actions/runs?branch=main&per_page=1" \
    --jq '.workflow_runs[0] | "\(.id) \(.status) \(.conclusion // "-")"' 2>/dev/null
}

echo
echo "=== ウェブログを公開 ==="
echo

if ! $GIT rev-parse --git-dir >/dev/null 2>&1; then
  echo "エラー: git リポジトリとして読めません（$REPO）"
  exit 1
fi

if [ -z "$($GIT status --porcelain)" ]; then
  echo "変更はありません。"
  echo "Obsidian で原稿を書いて保存してから、もう一度実行してください。"
  echo
  exit 0
fi

echo "次の変更を公開します:"
$GIT -c core.quotepath=false status --short | sed 's/^/  /'
echo

# コミットメッセージは変更された原稿のファイル名から作る
titles=$($GIT -c core.quotepath=false status --porcelain \
  | cut -c4- \
  | sed -n 's|^原稿/\(.*\)\.md$|\1|p' \
  | head -3 \
  | paste -sd '、' -)
if [ -n "$titles" ]; then
  msg="更新: $titles"
else
  msg="サイトの設定を更新"
fi

prev_id=$(latest_run | cut -d' ' -f1)

echo "コミットしています（$msg）..."
$GIT add -A || exit 1
$GIT commit -q -m "$msg" || exit 1

echo "GitHub に送っています..."
if ! $GIT push -q origin main; then
  echo
  echo "エラー: push に失敗しました。ネットワークや GitHub の状態を確認してください。"
  notify "公開に失敗しました"
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo
  echo "送信しました。1〜2分でサイトに反映されます。"
  echo "$SITE_URL"
  echo
  exit 0
fi

printf "サイトを組み立てています"
i=0
while [ $i -lt 60 ]; do
  sleep 10
  printf "."
  set -- $(latest_run)
  if [ -n "$1" ] && [ "$1" != "$prev_id" ] && [ "$2" = "completed" ]; then
    echo
    echo
    if [ "$3" = "success" ]; then
      echo "公開しました 🎉"
      echo "$SITE_URL"
      notify "サイトを更新しました"
    else
      echo "ビルドに失敗しました。次のページで原因を確認してください:"
      echo "https://github.com/keisato0/weblog/actions"
      notify "公開に失敗しました"
    fi
    echo
    exit 0
  fi
  i=$((i + 1))
done

echo
echo
echo "送信は終わりましたが、反映の確認が時間切れになりました。次のページで状況を確認してください:"
echo "https://github.com/keisato0/weblog/actions"
echo
exit 0
