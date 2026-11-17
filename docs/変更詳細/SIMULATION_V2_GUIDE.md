# ボス戦闘シミュレーションVer.2 実装・実行手順（2026-11-17）

起点main `f155022`（第1〜2.5段階を統合済み）、ブランチ `feature/boss-simulation-v2`。
本測定・ボス調整前にスモークと予備測定までを実施する。

## 追加ファイル

- `apps/battle/simulation_v2.py`: 336構成の実データ再現、戦術A〜D、実BattleEngineの観測、SQL書込み防止、Wilson区間・集計。
- `apps/battle/management/commands/simulate_boss_v2.py`: 専用テストDBの作成/破棄、有限件数の実行、条件絞込み、JSONLチェックポイント、CSV/JSON出力、再開。
- 上記managementディレクトリの `__init__.py` 2件。
- `apps/battle/test_simulation_v2.py`: 小数の契約7テスト。大量測定や勝率目標を通常テストへ入れない。
- `docs/変更詳細/SIMULATION_V2_REPORT.py`: 測定済みファイルのみを再集計し、Markdown・CSV・JSON報告書を生成。
- `docs/変更詳細/simulation_v2/`: 条件manifest、各戦闘結果、各条件の集計と詳細トレース。

既存の測定器・seeded_random・実BattleEngine・育成算出器・表示戦闘力の式・既存マスターを再利用する。Ver.1は互換性のため保持し、別の簡易戦闘モデルを作らない。HP等を素値から設定し、エンジンに職業/種族/装備補正を一度だけ適用させ、記録済みcombat_startと照合する。

## 安全性

実行は `--isolated-test-db` 必須。通常DB名では測定器・データ準備とも拒否する。許可名はランナーが新規に作る `test_qhymia_simv2_<uuid>` の一時許可リストと一致する必要がある。

1. PostgreSQLのみ許可し、UUID名が既存DBと衝突しないことを管理接続で確認する。
2. DjangoのテストDB作成処理でmigrationを適用する。通常DBのCharacter/Enemy/装備/スキルにはアクセスしない。
3. 許可中の専用DBに測定用キャラクター・装備・スキル枠を作成する。ボスはmigrationの値を読むだけ。
4. 各戦闘はSELECT以外のSQLを実行前に拒否する。
5. 終了時は作成した専用DBを破棄し、接続設定を復元する。

DB作成/破棄は隔離した測定用DBだけ。契約テストでは通常のDjangoテストDB接続を確認してからDB名ガードをテスト用に置き換える。通常DBではこの契約テストも実行できない。

DB準備完了後のエラーはfinallyで破棄する。DB作成/移行途中の失敗、プロセスの強制終了、OS障害では一時DBが残る可能性がある。既存DBを自動探索・一括削除する機能は設けていない。通常開発用runserver・XAMPPの起動/設定は変更しない。

## 実行コマンド

まず規模だけ確認する（DB作成なし）。

```bash
venv/bin/python manage.py simulate_boss_v2 --isolated-test-db --output /tmp/v2-plan --smoke --trials 30 --tactics B --plan --seconds-per-battle 0.15
```

全12階×7職業の代表ビルドで3戦ずつ:

```bash
venv/bin/python manage.py simulate_boss_v2 --isolated-test-db --output docs/変更詳細/simulation_v2/smoke_final --smoke --trials 3 --tactics B
```

既存出力は上書きしない。同じ設定・同じソースで続行する場合:

```bash
venv/bin/python manage.py simulate_boss_v2 --isolated-test-db --output docs/変更詳細/simulation_v2/smoke_final --smoke --trials 3 --tactics B --resume
```

実測した予備測定:

```bash
venv/bin/python manage.py simulate_boss_v2 --isolated-test-db --output docs/変更詳細/simulation_v2/pilot_standard --smoke --trials 30 --tactics B
venv/bin/python manage.py simulate_boss_v2 --isolated-test-db --output docs/変更詳細/simulation_v2/pilot_tactics --smoke --floors 6 7 12 --tactics A C D --trials 30
venv/bin/python manage.py simulate_boss_v2 --isolated-test-db --output docs/変更詳細/simulation_v2/pilot_ranges --floors 7 12 --jobs warrior wizard --tactics B D --trials 30
venv/bin/python manage.py simulate_boss_v2 --isolated-test-db --output docs/変更詳細/simulation_v2/pilot_comparisons --comparisons only --floors 1 6 --jobs warrior wizard --tactics B --trials 30
venv/bin/python manage.py simulate_boss_v2 --isolated-test-db --output docs/変更詳細/simulation_v2/pilot_uses --profiles p055 p070 p151 p166 --tactics B C D --use-scales 3 --trials 30
venv/bin/python manage.py simulate_boss_v2 --isolated-test-db --output docs/変更詳細/simulation_v2/traces --profiles p070 p103 p149 p310 --tactics D --trials 5 --detail
```

`--floors` / `--jobs` / `--profiles` / `--variants` / `--tactics` / `--use-scales` で対象を絞る。`--comparisons include/only` は1〜6階の弱強派生を含める。派生は元の336構成を上書きしない。

`--trials` は1〜100000、`--max-battles` は既定20000。超過は実行せず拒否する。本測定は `--plan` で見積もりを提示して承認後に行う。Aは使用回数を持たないためscale=1のみを実行し、不要な重複条件を作らない。

## 戦術

Aはスキル枠なし。B標準、C攻撃重視、D補助/耐久重視の比較案を `simulation_v2.TACTICS` で定義する。全職業の全スロット順・回数は各manifestのcases[].slotsに保存する。

- 回数は2〜10回程度を中心とする有限予算。パッシブは1で保持し、scaleではアクティブのみを増やす。
- ウィッチのMP2倍、発動失敗/MP不足で現枠に留まる処理、ステルス中シャドウステップ100%等は実エンジンの処理を保持する。
- Dが職業固有の耐久戦術として成立しない場合（ウィザード/拳闘士）は代用であることを明記する。放浪人の蜃気楼はボス1体戦では全体化の利点がないため比較戦術に採用していない。
- フロストアーマー・浄化・リザレクの未完成効果はプレイヤー戦術に仮定しない。ボスの既存技能は変更せず、その未完成部分も現行のまま。

## 取得する観測値

- 勝敗、ループ数、終了理由（撃破/上限引分/例外）、1000ループ到達。
- 両者のゲージ行動回数、差、通常攻撃回数、スキル別成功回数、発動失敗、MP不足、skip。
- 開始HP/MP/ST・終了HP/MP/ST・残使用回数、MP0/ST0の有無。
- 実HPの減少/増加を分類した通常攻撃・スキル・毒・反射・反撃・自傷・回復。
- 状態異常の付与/解除/変化/同値更新、行動時に有効な状態の回数。バフ・デバフ・回避補正の状態も観測する。
- --detailでは各行動の前後資源、ゲージ前/増分/100消費後、HPイベントのraw_delta・実減少、状態遷移を保存。

観測は元のメソッドを同じ順序で1回だけ呼ぶラッパーとCombatantの代入監視。追加の乱数呼出しはない。seeded_randomで乱数状態を保持する。代表の観測あり/なしのログ・timeline・残資源・残回数digest一致と、同じseedでの詳細記録完全一致をテストする。

各戦闘で1ループ1行動、ゲージ消費、HP台帳、ST消費をassertする。HPのオーバーキルをクリップした実減少と減算要求値を区別する。発動失敗/MP不足の理由だけは元エンジンが理由コードを持たないため定型ログを補助利用する。ダメージ量はログから推定しない。

## 出力・再現・中断

- manifest.json: Gitコミット、ソース指紋、336構成データのhash、実戦略と育成seed、戦闘seed起点、試行数、使用エンジン。
- runs.jsonl: 1戦ごとのチェックポイント。完了ごとにflushする。
- runs.csv: 1戦ごとの主要値（両者の内訳はJSONセル）。
- summary.json / summary.csv: 条件別・階層/職業/戦術/構成/回数別、Wilson95%、平均/中央値ループ、行動差。
- summary.jsonにはmigrationから再現した12ボスの全能力・技能・属性も保存。

再開はソース/条件が完全一致したときだけ許可し、完了case/seedは再実行しない。JSONLの重複や不完全行は黙って捨てず拒否する。強制終了で行が壊れた場合は元ファイルを保持し、別の出力先で同じ条件を再実行できる。試行数を増やす場合は別出力先を使い、統計集計では同じcase/seedを二重に数えない。

未コミットの測定器もあるためGitコミットIDだけでコードを特定できない。ソースhashと実行時ファイル一式を保持すること。今後コードが変われば安全のため再開を拒否する。

## 検証・制限

既存481件はmain統合後も成功（70.473秒）。契約7件を追加し全488件成功（92.666秒、測定プロセスと並行したため負荷を含む）。期待失敗なし。

SQLiteへの切替・本番DB操作・新規migration・戦闘計算変更・ボス調整はない。統計は観測条件に条件付けた勝率で、育成seed分布全体の評価ではない。完全な全イベントAPIを追加したものではなく、バフの同値再付与/境界内完結・外部障害・マルチスレッド内の計測は網羅しない。

## 復元

今回の追加モジュール/コマンド/契約テストと測定資料の追加分だけを取り除けば、ゲーム本体は従来のまま。通常DBを変更していないためDB復元不要。既存資料・バックアップ・他の未追跡ファイルを一括削除しない。削除はユーザー承認がある場合に限定する。コミット・push・mainマージは未実施。
