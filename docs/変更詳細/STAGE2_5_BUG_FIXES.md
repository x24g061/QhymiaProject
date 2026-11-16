# 第2.5段階：検出された4件の不具合修正（2026-11-16）

基準main: `f246afb`。作業ブランチ: `research/boss-balance-v2-baseline`。

## 修正内容とファイル

|対象|変更|理由|
|---|---|---|
|apps/chat/views.py|JSONデコード後のdict検証、messageのstr検証、UnicodeDecodeErrorの400応答|配列・数値・null等や文字列以外のmessage、不正UTF-8による例外を防ぐ|
|apps/sns/views.py:admin_delete_post|既存のconfig.views.is_admin_mode_activeを直接再利用|セッションだけでなくAdminModeAuthorizedUserの許可を必須にし、認可ロジックを重複させない|
|apps/sns/views.py:toggle_like / toggle_favorite|require_POST追加|GET/HEAD/PUT/PATCH/DELETEを405で拒否し、DBを変更しない|
|config/test_stage2_security.py|expectedFailureを4件解除、7件追加、既存テスト強化|4件を通常回帰テストへ昇格し、正常系と拒否時の不変性を検証する|

認可関数の内容は変更しない。config.viewsはSNSモデルを参照するがSNSビューはインポートしないため、循環インポートは発生しない。既存の管理者編集・認可テストも実行する。

正常な文字列のトリム・空文字拒否・200文字制限・投稿者決定・レスポンス形式、いいね/お気に入りのPOSTレスポンス、正規管理者の削除・監査ログは維持する。

## フロントエンド互換性

- templates/sns_page.htmlの通常SNSのいいね・お気に入りfetchは既にPOST＋X-CSRFToken。
- static/js/sns.jsのミニSNSもPOST＋X-CSRFToken。
- templates/mini_sns_posts.htmlは上記JSへdata-urlを渡すボタン。
- templates/admin_panel.htmlのSNS削除はPOSTフォーム＋csrf_token。

以上をコードで確認し、テンプレート・JSは変更しない。Django Client(enforce_csrf_checks=True)で有効なトークンによるPOSTの登録/解除とJSONレスポンスを確認する。実ブラウザのクリック・WebSocket接続は今回未実施。

## テスト

昇格した4件:

- test_chat_non_object_json_is_rejected_without_server_error
- test_sns_admin_requires_authorization_record_even_with_session
- test_like_get_must_not_mutate_database
- test_favorite_get_must_not_mutate_database

追加した7件:

- messageが非文字列のJSONオブジェクトを400で拒否。
- 不正UTF-8を400で拒否。
- 許可レコード＋有効セッションの正規管理者が削除・関連データ削除・監査ログ作成できる。
- 許可レコードがあってもモード無効なら403、投稿と履歴を変更しない。
- 正規管理者でもGET削除は405、投稿と履歴を変更しない。
- 既存Like/Favoriteを持つ場合も非POSTは405で拒否し、関連レコードを保持する。
- 正規CSRFトークン付きのPOSTがいいね/お気に入りの登録・解除を行い、既存JSON形式を返す。

既存テストも強化し、非オブジェクトJSON8型の拒否、未許可削除時のLike/Favorite保持、GETの405、トークンなしお気に入り・管理者削除のCSRF拒否を確認する。

対象テスト:

```bash
venv/bin/python manage.py test config.test_stage2_security config.test_admin_arena_edit config.tests --noinput
```

47件すべて通常成功（7.917秒）。expectedFailure・unexpected successなし。

全体テスト:

```bash
venv/bin/python manage.py test --noinput
```

481件すべて通常成功（67.006秒）。失敗0・エラー0・expectedFailure 0・unexpected success 0。元の474件を保持し、追加は上記7件のみ。

Djangoシステムチェック正常、git diff --check問題なし。テストはDjangoのテスト専用DBで実施する。

## 変更しない範囲・残る課題

- 本番DB、ボス値/スキル、育成/AGI/戦闘式、マイグレーションは変更しない。
- 第1段階のCSV/JSON/算出器、第2段階のテスト成果物、既存未追跡ファイル・バックアップは保持する。
- 未完成3スキル、表示主属性と戦闘得意属性の条件差、装備特殊能力確率のコメント/定数差、取引の同時競合、ボス勝率の測定は今回の修正範囲外で、引き続き未解決・未検証。
- コミット・push・mainへのマージは実施しない。

## 復元

戻す場合は、チャット/SNSビューの今回の差分だけを逆適用し、4件のテストを再び期待失敗へ戻す。ただし4件の不具合が再発するため、この復元は推奨しない。通常DBの移行・復元は不要。第1/第2段階の他の差分や未追跡ファイルを一括破棄しない。
