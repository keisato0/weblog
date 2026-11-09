# ウェブログ

Obsidian の vault がそのままブログのソースになっている。

## 記事を書く

`原稿/` の中に `.md` ファイルを作る。ファイル1つが記事1つ。

- 記事タイトル = ファイル名（frontmatter に `title:` があればそちらが優先）
- 更新日時 = そのファイルの最終コミット日時（frontmatter に `updated: 2026-09-20` と書けば上書きできる）
- 記事のURL = `/posts/<記事タイトル>/`

## 公開する

Finder で **`ウェブログを公開・編集.command`** をダブルクリックするだけ。
変更をコミットして push し、GitHub Actions が `build.py` を実行して GitHub Pages に反映する。
ターミナルの画面に進捗が出て、反映が終わるとデスクトップにも通知が出る。

## Google フォトの写真を使う

Obsidian で原稿を編集中に、左端のリボンの **写真ボタン**（またはコマンドパレットの「Google フォトから写真を挿入」）を押し、ブラウザで写真を選んで「完了」を押す。
写真は長辺 350px に縮小され、撮影日時や位置情報などのメタデータを取り除いて `assets/images/` に保存され、カーソル位置に `![](assets/images/...)` が挿入される。写真を選ぶ前にもう一度ボタンを押すと中止する。

Finder で **`写真を取り込む.command`** をダブルクリックしても取り込める。この場合は挿入する文字列がクリップボードに入るので、原稿に `Cmd+V` で貼り付ける。

`assets/images/` の写真は、原稿で使っていなくても公開するとサイトに載る。

### 初回設定

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作る。
2. 「Google Photos Picker API」を有効にする。
3. Google Auth Platform で対象を「外部」にして、自分の Google アカウントをテストユーザーに追加する。
4. 種類を「デスクトップ アプリ」にして OAuth クライアントを作り、JSON をダウンロードする。
5. `写真を取り込む.command` を実行して、ブラウザで認可する。
6. Obsidian の「設定 → コミュニティプラグイン」で制限モードをオフにし、「Weblog Photos」を有効にする。

`~/Downloads` の `client_secret_*.json` は `~/.config/weblog-google-photos/` に自動で移動する。公開時にコミットされないよう、認証情報はリポジトリの外に置いている。
公開ステータスが「テスト」のままだと認可は7日で切れ、切れた後の実行時にブラウザの認可画面がもう一度開く。

## 手元で確認する

```
./build.sh
python3 -m http.server --directory _site 8000
```

`http://localhost:8000/` を開く。初回の `./build.sh` は `.venv` を作って markdown を入れる（数秒かかる）。

## ファイル

| パス | 役割 |
| --- | --- |
| `原稿/` | 記事の原稿（Obsidian で編集する） |
| `build.py` | `原稿/*.md` → `_site/` のHTMLを生成 |
| `assets/style.css` | サイトの見た目 |
| `.github/workflows/deploy.yml` | push 時の自動公開 |
| `ウェブログを公開・編集.command` | ダブルクリックで公開する |
| `.obsidian/plugins/weblog-photos/` | Obsidian の写真ボタン |
| `写真を取り込む.command` | ダブルクリックで Google フォトの写真を取り込む |
| `import_photos.py` | 写真の取り込みの本体 |
| `assets/images/` | 取り込んだ写真 |
