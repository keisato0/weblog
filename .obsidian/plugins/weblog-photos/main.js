"use strict";

// Google フォトで選んだ写真を取り込み、編集中の原稿のカーソル位置に挿入する。
// 写真の取り込みそのものは vault のルートにある import_photos.py が行う。

const { MarkdownView, Notice, Plugin } = require("obsidian");
const { spawn } = require("child_process");
const { clipboard } = require("electron");
const fs = require("fs");
const path = require("path");

const LABEL = "Google フォトから写真を挿入";
// Obsidian から起動すると PATH に Homebrew が含まれないので、場所を直接探す
const PYTHON_CANDIDATES = [
  "/opt/homebrew/bin/python3",
  "/usr/local/bin/python3",
  "/usr/bin/python3",
];

function errorMessage(stderr) {
  const marker = stderr.lastIndexOf("エラー:");
  if (marker !== -1) return stderr.slice(marker).trim();
  const lines = stderr.trim().split("\n");
  return lines[lines.length - 1] || "写真を取り込めませんでした。";
}

module.exports = class WeblogPhotosPlugin extends Plugin {
  onload() {
    this.job = null;
    this.addRibbonIcon("image-plus", LABEL, () => this.toggle());
    this.addCommand({
      id: "insert-photos",
      name: LABEL,
      callback: () => this.toggle(),
    });
  }

  onunload() {
    this.cancel();
  }

  toggle() {
    if (this.job) {
      this.cancel();
      new Notice("写真の取り込みを中止しました。");
    } else {
      this.start();
    }
  }

  cancel() {
    if (!this.job) return;
    this.job.cancelled = true;
    // SIGINT なら import_photos.py が Google 側のセッションを片付けてから終わる
    this.job.child.kill("SIGINT");
  }

  editingView() {
    const view = this.app.workspace.getActiveViewOfType(MarkdownView);
    return view && view.getMode() === "source" ? view : null;
  }

  start() {
    const view = this.editingView();
    if (!view) {
      new Notice("原稿を編集モードで開いてから押してください。");
      return;
    }
    const python = PYTHON_CANDIDATES.find((candidate) => fs.existsSync(candidate));
    if (!python) {
      new Notice("Python 3 が見つかりません。", 10000);
      return;
    }

    const root = this.app.vault.adapter.getBasePath();
    const child = spawn(python, [path.join(root, "import_photos.py"), "--stdout"], {
      cwd: root,
      env: { ...process.env, PYTHONUTF8: "1" },
      stdio: ["ignore", "pipe", "pipe"],
    });
    const notice = new Notice("ブラウザで写真を選んでください。もう一度ボタンを押すと中止します。", 0);
    const job = { child, file: view.file, cancelled: false };
    this.job = job;

    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8").on("data", (chunk) => (stdout += chunk));
    child.stderr.setEncoding("utf8").on("data", (chunk) => (stderr += chunk));

    let finished = false;
    const finish = (code, spawnError) => {
      if (finished) return;
      finished = true;
      this.job = null;
      notice.hide();
      if (job.cancelled) return;
      if (spawnError) {
        new Notice(`取り込みを開始できませんでした: ${spawnError.message}`, 10000);
        return;
      }
      const markdown = stdout.trim();
      if (markdown) this.insert(job.file, markdown);
      if (code !== 0) {
        new Notice(markdown ? "一部の写真を取り込めませんでした。" : errorMessage(stderr), 10000);
      } else if (!markdown) {
        new Notice("取り込める写真はありませんでした。");
      }
    };
    child.on("error", (error) => finish(null, error));
    child.on("close", (code) => finish(code, null));
  }

  insert(file, markdown) {
    const view = this.editingView();
    if (!view || view.file !== file) {
      clipboard.writeText(markdown);
      new Notice("別の画面に移動していたため、クリップボードに入れました。原稿に貼り付けてください。", 10000);
      return;
    }
    const editor = view.editor;
    const cursor = editor.getCursor("to");
    const line = editor.getLine(cursor.line);
    const before = cursor.ch > 0 ? "\n" : "";
    const after = cursor.ch < line.length ? "\n" : "";
    editor.setCursor(cursor);
    editor.replaceSelection(before + markdown + after);
  }
};
