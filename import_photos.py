#!/usr/bin/env python3
"""Google フォトで選んだ写真を assets/images/ に取り込む。

ブラウザで写真を選ぶと assets/images/ に保存し、原稿に貼り付ける Markdown を
クリップボードに入れる。使うのは Google Photos Picker API で、標準ライブラリのみで動く。

--stdout を付けると、Markdown だけを標準出力に書く（Obsidian プラグイン用）。
進捗とエラーは標準エラー出力に書く。

認証情報はリポジトリの外（~/.config/weblog-google-photos/）に置く。
「ウェブログを公開.command」は git add -A するので、リポジトリ内に置くと公開されてしまう。
"""

import base64
import contextlib
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMAGES_DIR = ROOT / "assets" / "images"
CONFIG_DIR = Path.home() / ".config" / "weblog-google-photos"
CLIENT_PATH = CONFIG_DIR / "client_secret.json"
TOKEN_PATH = CONFIG_DIR / "token.json"
DOWNLOADS_DIR = Path.home() / "Downloads"

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://photospicker.googleapis.com/v1"
SCOPE = "https://www.googleapis.com/auth/photospicker.mediaitems.readonly"

MAX_IMAGE_SIZE = 2048  # 保存する画像の長辺の上限（ピクセル）
REQUEST_TIMEOUT = 60  # 秒
AUTH_TIMEOUT = 300  # 秒
DEFAULT_POLL_INTERVAL = 5.0  # 秒
DEFAULT_PICK_TIMEOUT = 1800.0  # 秒
TOKEN_MARGIN = 300  # アクセストークンの期限が残りこの秒数を切ったら更新する
JST = timezone(timedelta(hours=9))
EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

SETUP_MESSAGE = f"""Google の OAuth クライアントのファイルが見つかりません。

README.md の「Google フォトの写真を使う」にある初回設定を行い、
ダウンロードした client_secret_*.json を次のどちらかに置いてください。
  - {DOWNLOADS_DIR}（次回の実行時に自動で移動します）
  - {CLIENT_PATH}"""


class PhotoImportError(Exception):
    """利用者に内容を伝えて終了するエラー。"""


class ApiError(PhotoImportError):
    def __init__(self, status, detail):
        super().__init__(f"Google からエラーが返りました（HTTP {status}）: {detail}")
        self.status = status


def http_request(url, *, method="GET", token=None, form=None, payload=None):
    """HTTP リクエストを送り、(本文, Content-Type) を返す。"""
    headers = {}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return response.read(), response.headers.get_content_type()
    except urllib.error.HTTPError as error:
        raise ApiError(error.code, error.read().decode("utf-8", "replace")) from error
    except urllib.error.URLError as error:
        raise PhotoImportError(f"通信に失敗しました: {error.reason}") from error


def write_private_json(path, data):
    """本人だけが読めるファイルとして JSON を保存する。"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        json.dump(data, file)


def installed_client(path):
    """client_secret ファイルからデスクトップアプリの設定を読む。該当しなければ None。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    client = data.get("installed") if isinstance(data, dict) else None
    return client if isinstance(client, dict) and client.get("client_id") else None


def load_client():
    if CLIENT_PATH.exists():
        client = installed_client(CLIENT_PATH)
        if client is None:
            raise PhotoImportError(
                f"{CLIENT_PATH} を読み取れません。"
                "種類が「デスクトップ アプリ」の OAuth クライアントのファイルに置き換えてください。"
            )
        return client

    downloaded = sorted(
        DOWNLOADS_DIR.glob("client_secret_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in downloaded:
        client = installed_client(path)
        if client is not None:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.move(str(path), str(CLIENT_PATH))
            CLIENT_PATH.chmod(0o600)
            print(f"OAuth クライアントのファイルを {CLIENT_PATH} に移動しました。")
            return client
    raise PhotoImportError(SETUP_MESSAGE)


class CallbackHandler(BaseHTTPRequestHandler):
    """Google の認可画面からのリダイレクトを受け取る。"""

    timeout = 5  # ブラウザが先読みで開くだけの接続で待ち続けないようにする

    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if query.get("state", [None])[0] == self.server.expected_state:
            self.server.callback_query = query
        body = "認可の処理が終わりました。このタブは閉じてください。".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


class GoogleAuth:
    """OAuth 2.0 のアクセストークンを管理する。"""

    def __init__(self, client):
        self.client = client
        self.tokens = self._read_saved_tokens()

    @staticmethod
    def _read_saved_tokens():
        try:
            tokens = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return tokens if isinstance(tokens, dict) else {}

    def _client_form(self):
        form = {"client_id": self.client["client_id"]}
        if self.client.get("client_secret"):
            form["client_secret"] = self.client["client_secret"]
        return form

    def _store(self, response):
        tokens = dict(self.tokens)
        tokens.update(response)
        tokens["expires_at"] = time.time() + float(response.get("expires_in", 3600))
        self.tokens = tokens
        write_private_json(TOKEN_PATH, tokens)

    def _refresh(self):
        form = self._client_form()
        form.update(grant_type="refresh_token", refresh_token=self.tokens["refresh_token"])
        body, _ = http_request(TOKEN_URL, method="POST", form=form)
        self._store(json.loads(body))

    def _authorize(self):
        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        state = secrets.token_urlsafe(24)

        server = HTTPServer(("127.0.0.1", 0), CallbackHandler)
        server.timeout = 1
        server.expected_state = state
        server.callback_query = None
        redirect_uri = f"http://127.0.0.1:{server.server_port}"
        url = AUTH_URL + "?" + urllib.parse.urlencode({
            "client_id": self.client["client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        })

        print("ブラウザで Google アカウントの認可を行ってください。")
        webbrowser.open(url)
        deadline = time.monotonic() + AUTH_TIMEOUT
        try:
            while server.callback_query is None and time.monotonic() < deadline:
                server.handle_request()
        finally:
            server.server_close()

        query = server.callback_query
        if query is None:
            raise PhotoImportError("認可が時間内に完了しませんでした。もう一度実行してください。")
        if "code" not in query:
            reason = query.get("error", ["不明"])[0]
            raise PhotoImportError(f"認可が完了しませんでした（{reason}）。")

        form = self._client_form()
        form.update(
            grant_type="authorization_code",
            code=query["code"][0],
            code_verifier=verifier,
            redirect_uri=redirect_uri,
        )
        body, _ = http_request(TOKEN_URL, method="POST", form=form)
        self.tokens = {}
        self._store(json.loads(body))

    def access_token(self):
        if self.tokens.get("access_token") and (
            time.time() < float(self.tokens.get("expires_at", 0)) - TOKEN_MARGIN
        ):
            return self.tokens["access_token"]
        if self.tokens.get("refresh_token"):
            try:
                self._refresh()
                return self.tokens["access_token"]
            except ApiError as error:
                if error.status not in (400, 401):
                    raise
                print("Google の認可の期限が切れているため、認可をやり直します。")
        self._authorize()
        return self.tokens["access_token"]


def api_json(auth, method, path, *, params=None, payload=None):
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    body, _ = http_request(url, method=method, token=auth.access_token(), payload=payload)
    return json.loads(body) if body else {}


def seconds(value, default):
    """API の期間表記（例: "5s"）を秒数にする。"""
    try:
        return float(str(value).rstrip("s"))
    except ValueError:
        return default


def wait_for_selection(auth, session):
    """写真の選択が終わるまで待つ。"""
    current = session
    print("ブラウザで写真を選び、「完了」を押してください。", end="", flush=True)
    while not current.get("mediaItemsSet"):
        polling = current.get("pollingConfig") or {}
        if seconds(polling.get("timeoutIn", DEFAULT_PICK_TIMEOUT), DEFAULT_PICK_TIMEOUT) <= 0:
            print()
            raise PhotoImportError("写真の選択が時間切れになりました。もう一度実行してください。")
        time.sleep(seconds(polling.get("pollInterval", DEFAULT_POLL_INTERVAL), DEFAULT_POLL_INTERVAL))
        print(".", end="", flush=True)
        current = api_json(auth, "GET", f"/sessions/{session['id']}")
    print()


def list_picked_items(auth, session_id):
    items = []
    params = {"sessionId": session_id, "pageSize": 100}
    while True:
        page = api_json(auth, "GET", "/mediaItems", params=params)
        items.extend(page.get("mediaItems", []))
        if not page.get("nextPageToken"):
            return items
        params["pageToken"] = page["nextPageToken"]


def image_stem(item):
    """撮影日時と ID から、同じ写真なら毎回同じになるファイル名を作る。"""
    suffix = hashlib.sha1(item["id"].encode()).hexdigest()[:6]
    try:
        created = datetime.strptime(item.get("createTime", "")[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return f"photo-{suffix}"
    return f"{created.replace(tzinfo=timezone.utc).astimezone(JST):%Y%m%d-%H%M%S}-{suffix}"


def download_image(auth, item):
    """写真を保存し、保存先のパスを返す。"""
    url = f"{item['mediaFile']['baseUrl']}=w{MAX_IMAGE_SIZE}-h{MAX_IMAGE_SIZE}"
    body, content_type = http_request(url, token=auth.access_token())
    extension = EXTENSIONS.get(content_type)
    if extension is None:
        raise PhotoImportError(f"ブラウザで表示できない形式です: {content_type}")
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    path = IMAGES_DIR / (image_stem(item) + extension)
    path.write_bytes(body)
    return path


def copy_to_clipboard(text):
    try:
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def import_photos():
    auth = GoogleAuth(load_client())
    print("Google フォトの選択画面を開きます。")
    session = api_json(auth, "POST", "/sessions", payload={})
    saved = []
    failures = 0
    try:
        webbrowser.open(session["pickerUri"].rstrip("/") + "/autoclose")
        wait_for_selection(auth, session)
        for item in list_picked_items(auth, session["id"]):
            filename = item.get("mediaFile", {}).get("filename", item.get("id", "不明"))
            if item.get("type") == "VIDEO":
                print(f"  動画のためスキップしました: {filename}")
                continue
            try:
                path = download_image(auth, item)
            except PhotoImportError as error:
                failures += 1
                print(f"  保存できませんでした: {filename}（{error}）")
                continue
            saved.append(path)
            print(f"  保存しました: {path.relative_to(ROOT)}")
    finally:
        # セッションの作成数には上限があるので、終わったものは消しておく
        try:
            api_json(auth, "DELETE", f"/sessions/{session['id']}")
        except PhotoImportError:
            pass

    return saved, failures


def to_markdown(paths):
    """Obsidian で表示できる、vault のルートからのパスで書く（公開時は build.py が変換する）。"""
    return "\n".join(f"![](assets/images/{path.name})" for path in paths)


def report_to_terminal(saved, failures):
    if saved:
        markdown = to_markdown(saved)
        print()
        if copy_to_clipboard(markdown):
            print(f"{len(saved)} 枚を取り込みました。原稿に Cmd+V で貼り付けてください。")
        else:
            print(f"{len(saved)} 枚を取り込みました。次の行を原稿に貼り付けてください。")
            print(markdown)
    elif not failures:
        print("取り込める写真はありませんでした。")


def main():
    try:
        if "--stdout" in sys.argv[1:]:
            with contextlib.redirect_stdout(sys.stderr):
                saved, failures = import_photos()
            if saved:
                print(to_markdown(saved))
        else:
            saved, failures = import_photos()
            report_to_terminal(saved, failures)
        return 1 if failures else 0
    except PhotoImportError as error:
        print(f"\nエラー: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n中止しました。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
