# 戦闘ログの圧縮保存

runs.jsonl は容量削減のため runs.jsonl.gz として保存しています。

再集計や検証を行う前に、リポジトリのルートで以下を実行してください。

    gzip -dk docs/変更詳細/balance_stage6c/screen/runs.jsonl.gz

既存の元ファイルがある場合は展開不要です。
圧縮前後のデータが完全一致することを確認済みです。
