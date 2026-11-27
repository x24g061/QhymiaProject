# 背景画像の配信修正

2026-11-27、`fix/background-media-serving` 上で修正。

## 配信の動作

- `/media/user_backgrounds/<ファイル名>` は `DEBUG=False` でも利用できる。ログイン中のユーザーの `UserSettings.background_image.name` とパスが一致する場合に限り、設定済みのストレージからファイルを開く。
- 許可形式はJPEG・PNG・WebP。Pillowが判定した形式を `Content-Type` に設定して `FileResponse` で返す。レスポンスに `X-Content-Type-Options: nosniff` と `Cache-Control: private, no-store` などを設定する。
- 未ログイン時はログイン画面へリダイレクトする。設定との不一致、ファイルの欠落、不正なパス、許可形式として読み取れない内容は404を返す。
- 開発時の公開メディア配信は既存のSNS画像用ディレクトリに限定する。背景画像は開発時も同じ認証経路を通る。
- ホームの探索画面、戦闘結果、手相占い、設定プレビューでは既存の画像URLを使う。設定画面から変更や削除をすると旧URLは404になる。

## 変更ファイル

- `apps/accounts/views.py` に認証付き配信ビューを追加し、アップロードと配信で同じMIMEタイプ一覧を使う。
- `config/urls.py` に既存URLを処理するルートを追加し、開発用公開メディア配信の範囲を絞る。
- `apps/accounts/test_background_media.py` に配信と設定操作の回帰テストを追加する。
- `AGENTS.md` に今回の変更を記録する。

## 検証結果

- 背景画像の回帰テスト7件を含むDjango全体638件が成功。最終実行は103.703秒。通常DBから分離したPostgreSQLとテスト用の一時画像保存先を使用した。
- JPEG・PNG・WebPの配信、保存名と権限の照合、パストラバーサルの拒否、HTML・SVG・GIFと不正なPNGの拒否、アップロード・変更・削除、ホーム・戦闘結果・手相占い・設定の背景画像URLを確認した。
- `DEBUG=False` でDjangoシステムチェックが成功。既存の `garukura.jpg` を読み取り専用で検証し、`image/jpeg` の200応答と配信サイズを確認した。開発モードでは背景画像の専用ルートとSNS画像用ルートの解決を確認した。
- XAMPPやDaphneの起動プロセスを経由したHTTPアクセスは未検証。

## 復元

以前のコードに戻す場合は、今回の配信ビューとURL設定の差分を元に戻す。DB移行や既存画像の復元作業は不要。
