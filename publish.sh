#!/bin/sh
# 原稿の変更をコミットして push し、サイトを更新する。
#
# 終了コード:
#   0  公開した
#   10 変更がなかった
#   1  エラー
#
# 「ウェブログを公開.app」から呼ばれる。手で実行してもよい。

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin:/opt/homebrew/bin"
GIT=/usr/bin/git
REPO=$(cd "$(dirname "$0")" && pwd)
SITE_URL="https://keisato0.github.io/weblog/"
cd "$REPO" || exit 1

notify() {
  /usr/bin/osascript -e "display notification \"$1\" with title \"ウェブログ\"" >/dev/null 2>&1
}

latest_run() {
  # 最新のビルドの「ID 状態 結果」を返す。gh がなければ何も返さない
  gh api "repos/keisato0/weblog/actions/runs?branch=main&per_page=1" \
    --jq '.workflow_runs[0] | "\(.id) \(.status) \(.conclusion // "-")"' 2>/dev/null
}

# --watch: push のあとにバックグラウンドで走り、ビルドの完了を通知する
if [ "$1" = "--watch" ]; then
  prev_id=$2
  i=0
  while [ $i -lt 60 ]; do
    sleep 10
    set -- $(latest_run)
    [ -z "$1" ] && exit 0            # gh が使えない場合は黙って終わる
    if [ "$1" != "$prev_id" ] && [ "$2" = "completed" ]; then
      if [ "$3" = "success" ]; then
        notify "サイトを更新しました"
      else
        notify "公開に失敗しました（GitHub の Actions を確認してください）"
      fi
      exit 0
    fi
    i=$((i + 1))
  done
  exit 0
fi

if [ -n "$($GIT status --porcelain 2>&1 >/dev/null)" ] || ! $GIT rev-parse --git-dir >/dev/null 2>&1; then
  echo "git リポジトリとして読めません: $REPO"
  exit 1
fi

if [ -z "$($GIT status --porcelain)" ]; then
  echo "変更はありません"
  exit 10
fi

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

$GIT add -A || exit 1
$GIT commit -q -m "$msg" || exit 1
$GIT push -q origin main || exit 1

if command -v gh >/dev/null 2>&1; then
  nohup /bin/sh "$0" --watch "$prev_id" >/dev/null 2>&1 &
fi

echo "$msg"
exit 0
