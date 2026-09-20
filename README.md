# ウェブログ

Obsidian の vault がそのままブログのソースになっている。

## 記事を書く

`原稿/` の中に `.md` ファイルを作る。ファイル1つが記事1つ。

- 記事タイトル = ファイル名（frontmatter に `title:` があればそちらが優先）
- 更新日時 = そのファイルの最終コミット日時（frontmatter に `updated: 2026-09-20` と書けば上書きできる）
- 記事のURL = `/posts/<記事タイトル>/`

## 公開する

`main` に push すると GitHub Actions が `build.py` を実行し、GitHub Pages に反映される。

```
git add -A && git commit -m "記事を追加" && git push
```

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
