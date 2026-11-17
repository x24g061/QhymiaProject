# ステップ5-A補修：購入テスト・並行回帰の独立性

2026-11-17 JST、`feature/boss-balance-final`、開始HEAD `c69fd98`。

## 修正範囲

アプリ本体の変更はない。変更したテストは次の2ファイル。テスト件数を増減せず、skip/expectedFailureも追加しない。

- `apps/shop/test_stage2_transactions.py`
- `apps/accounts/test_skill_inheritance.py`

ステップ5-Aの未コミット実装、シミュレーション条件、全測定結果、旧報告・検証結果JSONは保持する。この報告とAGENTS/コンテキストの追記で、過去の失敗記録と補修後を区別する。

## ショップ：数量指定の正式仕様へテスト入力を合わせる

最新の仕様変更コミット`1702e9d`、現在の`buy_market_listing`、`MarketListing`、`templates/shop.html`を照合した。

- 通常品は購入数量を指定して部分購入でき、未指定は1個。
- 価格は単価×購入数量。部分購入後は出品在庫を減らし、残量があれば出品を継続する。
- 装備は1個だけ購入可能。

旧3テストはquantityを送らず、3個×20Q＝60Qの全量購入を期待していた。現行処理の不具合ではなく、購入数量を選べる仕様追加後のテスト入力の不一致だった。ビュー・モデル・画面の購入仕様は変更しない。

テストの購入ヘルパーへ任意のquantityを渡せるようにし、未指定の場合は引き続きquantityを送信しない。

|テスト|修正と維持・追加した検証|
|---|---|
|`test_material_sale_conserves_quantity_and_money`|未指定で1個購入して20Q移転・残出品2個を確認し、指定2個を追加購入。最終的な購入3個・60Q移転・売主在庫7個・残出品0・SOLD・購入者を検証。売却通知は正常購入2回に対応する2件|
|`test_repeat_purchase_is_not_charged_or_granted_twice`|quantity=3の同じPOSTを2回送る。最初だけ成立し、移転60Q・購入3個・売主在庫7個・残出品0・SOLD・通知1件を検証|
|`test_insufficient_money_does_not_mutate_listing`|所持59Qでquantity=3（60Q）を指定。在庫・出品数量・両者のQ・出品状態を保持し、購入者/購入品/売却通知が発生しないことを検証|

未指定1個の購入や部分購入は正常な取引として区別する。同じPOSTでも在庫が残る場合の別購入を禁止する新仕様は設けていない。従来の「売切れ後に再購入しても二重取得・二重課金しない」という検証を保持した。

## 並行回帰：flush後に必要なマスターを自分で準備

`battle.0002_add_initial_skills`がスキル35種、`battle.0011_arenabattlehistory_arenafloor_arenastate`がフロア1〜100をデータmigrationで作る。一方、`TransactionTestCase`の終了後のflushはこれらの行を消すが、データmigrationを再適用しない。

`ConcurrentReincarnationTests`にはfixtures/setUpによるマスター準備がなかった。そのため単独実行ではテストDB作成時のマスターを利用できたが、先に別のTransactionTestCaseが実行された組合せではフロア1がなくなり、回帰時に作るArenaStateのFKで失敗した。フロアだけ補うと、スキル消失によって「永久習得1件」の期待も成立しない。

このクラスの`setUp()`で次を毎回準備する。

1. 回帰後ArenaStateが参照するフロア1を`get_or_create`する。
2. 既存の初期スキルデータ作成関数を再利用し、実カタログ35種を`update_or_create`で用意する。

これはテストDBへのfixture準備であり、migrationの適用やアプリの回帰処理の変更ではない。数値やスキル定義をテスト側に別コピーせず、既存の初期データ関数を使う。全DBのserialized rollbackや他のテストの復元処理には依存しない。

実際のPostgreSQL行ロックと独立した2セッションの同時POSTはそのまま実行する。回帰回数1・永久習得1件に加え、習得元が回帰前のウィザードであること、回帰後がLv1/放浪人であること、1階のArenaStateとHP/MP全回復も確認する。

## 検証

影響範囲→単独→組合せ→逆順→最後に全体の順で、新しいテストDBを使用して実行する。

```bash
venv/bin/python manage.py test apps.shop.test_stage2_transactions apps.accounts.test_skill_inheritance.ConcurrentReincarnationTests --noinput
venv/bin/python manage.py test apps.accounts.test_skill_inheritance.ConcurrentReincarnationTests --noinput
venv/bin/python manage.py test apps.battle.test_arena_concurrency apps.accounts.test_skill_inheritance.ConcurrentReincarnationTests --noinput
venv/bin/python manage.py test apps.battle.test_arena_concurrency apps.accounts.test_skill_inheritance.ConcurrentReincarnationTests --reverse --noinput
venv/bin/python manage.py test --noinput
```

組合せ実行では別のTransactionTestCaseのflushを挟み、migrationデータが残っていない場合も検証する。先行4実行は29件（1.275秒）、単独1件（0.635秒）、通常順3件（2.844秒）、逆順3件（2.878秒）が成功した。

最後の全体実行は**526件すべて成功（72.890秒）**。失敗・エラー・skip・期待失敗なし。Djangoシステムチェック正常。全テスト本体の累計は80.522秒で、5分以内。`git diff --check`と変更した2ファイルの構文検査も成功した。今回の対象に未解決事項はない。

## 保護・復元

購入ビュー/モデル・回帰処理・闘技場処理・ボス値・戦闘/成長/強化式に変更なし。通常DB/本番DBへの書込み、migration適用、データ削除は行わない。Gitのcommit/push/mergeも行わない。

開始時にステップ3・5-Aの成果物と未コミット測定コードなど99ファイルのSHA256を保存し、補修後も同一であることを照合する。旧失敗を記録した`balance_stage5a/validation_results.json`や元報告も上書きしない。

戻す場合は今回のテスト2ファイルの差分と補修資料/追記だけを対象とする。ステップ5-Aの未コミット変更や未追跡ファイルをHEADで一括上書きしない。通常DB復元は不要。
