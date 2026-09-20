-- 「ウェブログを公開.app」の中身
-- tools/make-app.sh でこのファイルからアプリを作る（__REPO__ は実際のパスに置換される）

property repoPath : "__REPO__"
property siteURL : "https://keisato0.github.io/weblog/"

on run
	try
		set out to do shell script "/bin/sh " & quoted form of (repoPath & "/publish.sh") & " 2>&1"
		set r to display dialog "公開しました。" & return & return & out & return & return & "サイトへの反映まで1〜2分かかります。完了したら通知します。" with title "ウェブログ" buttons {"閉じる", "サイトを開く"} default button "サイトを開く" with icon note giving up after 60
		if button returned of r is "サイトを開く" then
			open location siteURL
		end if
	on error errMsg number errNum
		if errNum is 10 then
			display dialog "変更はありません。" & return & return & "Obsidian で原稿を書いて保存してから、もう一度実行してください。" with title "ウェブログ" buttons {"OK"} default button "OK" with icon note giving up after 30
		else if errNum is -128 then
			-- ユーザーが中断した場合は何もしない
		else
			display dialog "公開できませんでした。" & return & return & errMsg with title "ウェブログ" buttons {"OK"} default button "OK" with icon stop giving up after 180
		end if
	end try
end run
