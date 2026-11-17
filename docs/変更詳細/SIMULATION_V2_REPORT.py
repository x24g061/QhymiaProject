"""測定済みJSONLだけを集計する。戦闘・DB操作は行わない。"""
import csv
import json
import os
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from apps.battle.simulation_v2 import summarize, wilson

BASE = Path(__file__).parent / "simulation_v2"
SOURCES = ["pilot_standard", "pilot_tactics", "pilot_ranges", "pilot_comparisons", "pilot_uses"]
JOBS = ["grappler", "warrior", "hunter", "wizard", "priest", "wanderer", "assassin"]
NAMES = ["拳闘士", "重戦士", "狩人", "ウィザード", "プリースト", "放浪人", "暗殺者"]


def read(name):
    return [json.loads(line) for line in (BASE / name / "runs.jsonl").read_text().splitlines()]


def percent(value):
    return "未測定" if value is None else f"{100*value:.1f}%"


def main():
    source_summaries = {name: json.loads((BASE/name/"summary.json").read_text()) for name in SOURCES}
    manifests = {name: json.loads((BASE/name/"manifest.json").read_text()) for name in SOURCES}
    raw = {name: read(name) for name in SOURCES}
    standard = raw["pilot_standard"]
    smoke = read("smoke_final")
    unique = {}
    for runs in raw.values():
        for run in runs:
            key = (run["case"], run["seed"])
            if key in unique and unique[key].get("digest") != run.get("digest"):
                raise ValueError("同じcase/seedの結果が不一致")
            unique[key] = run
    rows = list(unique.values())
    traces = read("traces")
    for run in traces:
        assert unique[(run["case"],run["seed"])]["digest"] == run["digest"]
    assert len({m["source_sha256"] for m in manifests.values()}) == 1
    conditions = {}
    for summary in source_summaries.values():
        for condition in summary["conditions"]:
            conditions[condition["case"]] = condition
    aggregate = summarize(rows)
    seconds = sum(r["elapsed_seconds"] for runs in raw.values() for r in runs)
    actual = sum(map(len, raw.values()))
    per_battle = seconds / actual
    job_summary = {j: summarize([r for r in rows if r["job"] == j]) for j in JOBS}
    result = {"commit": next(iter(manifests.values()))["commit"],
        "source_sha256": next(iter(manifests.values()))["source_sha256"],
        "smoke_battles": len(smoke), "detail_executions": len(traces), "pilot_executions": actual, "pilot_unique_case_seeds": len(rows),
        "duplicate_executions": actual-len(rows), "pooled": aggregate,
        "equal_job_mean": statistics.mean(job_summary[j]["win_rate"] for j in JOBS),
        "by_job": job_summary, "sources": {name: {k:v for k,v in s.items() if k != "conditions"} for name,s in source_summaries.items()},
        "conditions": list(conditions.values()), "seconds_per_battle": per_battle,
        "main_all_300_battles": 336*4*300, "main_all_300_estimated_hours": 336*4*300*per_battle/3600}
    (BASE/"overview.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    with (BASE/"overview.csv").open("w",newline="") as target:
        writer=csv.DictWriter(target,fieldnames=list(next(iter(conditions.values()))))
        writer.writeheader();writer.writerows(conditions.values())
    lines=["# ボス戦闘シミュレーションVer.2：スモーク・予備測定（2026-11-17）", "",
        f"Git起点 `{result['commit']}` / `feature/boss-simulation-v2`。測定器は未コミットのためソース指紋 `{result['source_sha256']}` も保存する。",
        "", "## 結論の範囲", "",
        "実BattleEngineによる測定環境を構築した。ボス・プレイヤー育成・スキル・AGI・報酬は変更していない。以下は固定した到達例と戦術に条件付けた予備勝率であり、全プレイヤーの平均勝率や最適戦術の確定ではない。",
        "",
        f"最終スモーク {len(smoke)}戦、予備測定 {actual:,}戦、詳細トレース{len(traces)}戦、計{len(smoke)+actual+len(traces):,}戦を実行。予備の重複case/seed {actual-len(rows)}戦を二重に標本数へ加えず、集計は{len(rows):,}戦へ統合。同条件seedの重複実行と詳細トレースはdigest一致を確認した。スモーク/詳細トレースは予備のseed系列と重なるため独立標本として足さない。",
        "測定済みは元の336構成のうち104構成と、弱強派生8構成の計112構成・重複除去後207条件。336構成すべての測定はまだ行っていない。",
        "既存481テストは成功。観測/DB隔離契約7件を追加して全488件が通常成功（92.666秒、並行負荷を含む）。Djangoシステムチェック・構文/差分チェックも正常。",
        "", "## 実行内訳", "", "|測定|条件|戦闘数|例外|上限終了|戦闘処理秒|", "|---|---:|---:|---:|---:|---:|"]
    for name,s in source_summaries.items():
        p=s["pooled"]
        lines.append(f"|{name}|{len(s['conditions'])}|{p['trials']}|{p['exceptions']}|{p['loop_limits']}|{s['seconds']:.1f}|")
    lines += ["", "pilot_standardは全12階×7職業、ヒューマン側の代表ビルド・標準Bを各30戦。pilot_tacticsは6/7/12階の全7職業・同ビルドでA/C/Dを各30戦。pilot_rangesは7/12階の重戦士/ウィザードについて2構成×下限/中央/上限×B/D。pilot_comparisonsは1/6階の同2職業の弱強派生×B。pilot_usesは7/12階の同2職業・中央ビルドのB/C/Dを使用回数3倍で比較する。", "",
        "以下の表はpilot_standardだけを使い、各セル30戦、例外があれば分母を別記する。職業は同じ重みで平均する。", "",
        "## 全階層・全職業の暫定勝率（標準B）", "",
        "|階|"+"|".join(NAMES)+"|7職業平均|", "|---|"+"---:|"*8]
    floor_stats=[]
    for floor in range(1,13):
        parts=[summarize([r for r in standard if r["floor"]==floor and r["job"]==j]) for j in JOBS]
        rates=[p["win_rate"] for p in parts]
        lines.append("|"+str(floor)+"|"+"|".join(percent(r) for r in rates)+"|"+percent(statistics.mean(rates))+"|")
        floor_stats.append(summarize([r for r in standard if r["floor"]==floor]))
    lines += ["", "## 標準Bの行動差と不確実性", "", "|階|勝/敗/分|Wilson95%（単純合算）|平均/中央値ループ|平均行動 プレイヤー/ボス|行動差|", "|---|---|---|---|---|---:|"]
    for f,s in enumerate(floor_stats,1):
        lo,hi=s["wilson95"]
        lines.append(f"|{f}|{s['wins']}/{s['losses']}/{s['draws']}|{percent(lo)}〜{percent(hi)}|{s['mean_loops']:.1f}/{s['median_loops']:.1f}|{s['player_mean_actions']:.1f}/{s['boss_mean_actions']:.1f}|{s['mean_action_difference']:.1f}|")
    lines += ["", "各セルは30戦。0/30でも真の勝率0%を証明しない（Wilson上限約11.4%）、30/30でも100%を証明しない（下限約88.6%）。職業合算Wilsonは参考値で、共通seedによる条件間相関・異質性を考慮した区間ではなく、職業均等平均の信頼区間でもない。判断は各条件のWilson区間を優先する（各出力のsummary.csv/JSON）。", "",
        f"全予備の7職業均等平均={percent(result['equal_job_mean'])}、全有効試行の単純合算={percent(aggregate['win_rate'])}。職業別の測定条件数が違うため、この2つは別の量であり、ボス全体の難易度判定には混ぜない。", "",
        "## 戦術比較（6/7/12階の代表構成）", "", "|階・職業|A 通常攻撃|B 標準|C 攻撃重視|D 補助重視|", "|---|---:|---:|---:|---:|"]
    for floor in [6,7,12]:
        for j,n in zip(JOBS,NAMES):
            values=[]
            for tactic in "ABCD":
                source=standard if tactic=="B" else raw["pilot_tactics"]
                values.append(summarize([r for r in source if r["floor"]==floor and r["job"]==j and r["tactic"]==tactic])["win_rate"])
            lines.append(f"|{floor}・{n}|"+"|".join(percent(v) for v in values)+"|")
    lines += ["", "Dは職業によって成立範囲が異なる。ウィザードには完成済み防御/回復がないため防御無視・低MPの代用、拳闘士はSTRバフ中心。未完成のフロストアーマー/浄化/リザレクはプレイヤー戦術から除外し、ボス側の現行構成は保持する。Cは最大化を志向する比較案で、最適化を証明していない。", "",
        "## 装備・能力配分・下限中央上限の比較", "", "|階・職業・構成|戦術|下限付近|中央|上限付近|", "|---|---|---:|---:|---:|"]
    rr=raw["pilot_ranges"]
    for floor in [7,12]:
        for job in ["warrior","wizard"]:
            for gear in ["unarmed","F+8"]:
                for tactic in "BD":
                    values=[summarize([r for r in rr if r["floor"]==floor and r["job"]==job and r["variant"]==pos+"-"+gear and r["tactic"]==tactic])["win_rate"] for pos in ["low","mid","high"]]
                    lines.append(f"|{floor}・{job}・{gear}|{tactic}|"+"|".join(percent(v) for v in values)+"|")
    lines += ["", "装備なし/F+8の構成は種族・育成seed・回帰・Lv・能力配分も違う。差を装備だけの因果効果とは断定できない。同戦闘力でもHP/MPと攻撃/速度/耐久への配分が違うことを含めたビルド差である。有限seedの順序逆転は即バグ/即調整とせず確認用seedと試行数を追加する。", "",
        "## 弱強・使用回数比較", "",
        "弱強派生は、基準の回帰回数・種族・育成seedを維持し、弱側をLv−10・装備なし、強側をLv＋10（上限100）・1階F+2/6階F+8にした別条件。6階の派生は戦闘力5,000を外れる比較条件であり、正式推奨を変更したものではない。全ケースの能力値・装備・使用回数はmanifest.jsonにある。", "",
        "|比較|case|勝/試行|勝率|平均行動差|", "|---|---|---:|---:|---:|"]
    for name in ["pilot_comparisons","pilot_uses"]:
        for s in source_summaries[name]["conditions"]:
            lines.append(f"|{name}|{s['case']}|{s['wins']}/{s['valid']}|{percent(s['win_rate'])}|{s['mean_action_difference']:.1f}|")
    lines += ["", "使用回数1倍と3倍の直接比較:", "", "|case（3倍）|1倍勝率|3倍勝率|同seedで勝敗が変化した戦闘数|", "|---|---:|---:|---:|"]
    for s in source_summaries["pilot_uses"]["conditions"]:
        key=s["case"].rsplit("-u",1)[0]+"-u1"
        base=conditions[key]
        paired=[r for r in raw["pilot_uses"] if r["case"]==s["case"]]
        differences=sum(r["winner"]!=unique[(key,r["seed"])]["winner"] for r in paired)
        lines.append(f"|{s['case']}|{percent(base['win_rate'])}|{percent(s['win_rate'])}|{differences}/30|")
    lines += ["", "## 現状評価と次に確認する原因", "",
        "- 全職業がおおむね10%という階は今回確認できていない。9/10/12階の職業平均は約10%でも、拳闘士等に勝利が偏り、0/30の職業が複数残る。平均だけで適正と判定しない。",
        "- 1階Bは209/210勝、8階Bは183/210勝。この有限条件では目標より易しい側にあり、強化検討の候補。ただし8階は通常攻撃のみAを測っておらず、現行スキルと有効AGI差の寄与を先に確認する。ボス値は変更しない。",
        "- 3/4/5/7階Bは目標を下回る。5階は全職業0/30、7階は全職業合計1/210。より強い装備・別育成seed・別戦術を未網羅なので、ボスが常に強すぎるという確定判断はしない。",
        "- 6階の重戦士はB=0/30からC=29/30、プリーストはB=0/30からC=26/30へ変化。単純な職業性能差だけでなく、順序・攻撃頻度・有限使用回数の戦術依存が大きい。高勝率のCをプレイヤーの工夫として区別し、直ちに弱体化しない。",
        "- 低AGI敗北の例: 2階ウィザードBは平均行動3.0回対ボス7.3回で0/30。7階Bはプレイヤー行動数が上回る職業でもスキル・毒によって敗北するため、行動差だけでは勝率を説明できない。",
        "- 8階はボスAGI180に対し当該育成例のAGIが高く、全職業平均47.0行動対ボス7.5行動。重戦士/ウィザード各30戦は全てST0まで到達。長期化と疲労を含む条件であり、HP/MPや素の戦闘力だけでは比較できない。",
        "- 同一seed・同一順序で使用予算を3倍にしても、多くの代表条件では勝率が改善しない。7階/12階で戦闘が枯渇前に決着するケースが多く、残MPがあるため単純なMP増加や回数増加を解決策としない。個別のMP不足・残使用回数はJSONLで確認する。",
        "- 弱強派生の1/6階・重戦士/ウィザードでは弱側0/30→強側30/30。少なくともこの比較では能力/装備を上げた改善を確認したが、全ビルドへの単調性保証ではない。",
        "- 本測定では強化候補の1/8階、難しい5/7階、戦術依存が大きい6階、平均に職業差が隠れる9/10/12階を優先する。今回ステータス調整案の適用は一切行わない。"]
    both_dead=sum(not r.get("exception") and r["final"]["player"]["hp"]==0 and r["final"]["boss"]["hp"]==0 for r in rows)
    lines += ["", "## 異常・計測上の注意", "",
        f"重複除去後: 例外{aggregate['exceptions']}件、1000ループ上限{aggregate['loop_limits']}件、両者HP0の終了{both_dead}件。例外は削除せずJSONLに残し、勝率の分母には正常終了だけを用い、例外数を併記する。", "",
        "観測は実HPの変化をCombatantの代入で取得する。与被ダメージはオーバーキルを除く実HP減少、raw_deltaは減算要求も記録。毒・反射・反撃・奇襲の自傷は別カテゴリ。回復は実増分。自傷を通常の対敵ダメージと合算して解釈しない。反撃/反射は追加のゲージ行動として数えない。", "",
        "状態異常はCombatantの付与/更新/解除を観測し、行動時の残状態とskipを記録。バフはスキル/行動終了等の境界で観測するため、同値の再付与や境界内で完結する全バフ変化の完全捕捉は保証しない。発動失敗・MP不足の理由だけは現エンジンが理由コードを返さないため定型ログも補助使用し、数値ダメージはログから推定しない。", "",
        "各戦闘はHP台帳、1ループ1行動、100消費・余剰持越し、ST消費を検査。ループ上限の引き分けと例外を分離する。このエンジンの通常drawは実質的に上限終了であり、別の引分ルールを創作しない。両者HP0のときは現行の敵全滅優先の判定を維持する。", "",
        "対象のボスはmainのmigrationから専用DBへ再現した値（summary.jsonのbosses）。通常DBで後から手調整した値は読み出していない。", "",
        "## 本測定の規模と推奨", "",
        f"今回の平均実測 {per_battle:.4f}秒/戦（DB初期化を除く、並行プロセスの待ち時間を含む）。336構成×4戦術=1,344条件。各300戦は403,200戦、単純換算約{result['main_all_300_estimated_hours']:.1f}時間。各1,000戦は1,344,000戦、約{1344000*per_battle/3600:.1f}時間。戦術や長期戦、マシン負荷で変わる概算。", "",
        "まず84代表ビルド×4戦術=336条件×300戦=100,800戦を候補とし、予備で極端な職業差・戦術差・上下逆転が出たケースを確認用の別seed系列で優先する。範囲/装備比較・MP/ST枯渇のケースは別層化し、良い勝率だけを選んで全体平均を作らない。必要な代表ケースだけ1,000戦へ拡大する。今回300戦以上の本測定・ボス調整は実行していない。", "",
        "本測定後に目標約10%と比較して原因分析する。5〜15%は暫定目安。高勝率でも戦術の工夫によるものは即弱体化の根拠にせず、通常攻撃でも高勝率か、全職業か、一部の種族/装備/スキルだけかを区別する。", "",
        "## 成果物", "",
        "各ディレクトリのmanifest.jsonにGitコミット・ソース指紋・育成構成・戦闘seed・スキル順序/回数・実行条件を保存。runs.jsonlとruns.csvに各戦闘、summary.json/CSVに条件別集計。overview.json/CSVは予備測定の重複case/seedを統合した集計。再集計は `venv/bin/python docs/変更詳細/SIMULATION_V2_REPORT.py`。", "",
        "測定器の実装・保護・コマンド・テスト・制限は `SIMULATION_V2_GUIDE.md`。旧smokeは観測器の調整前252戦として保持し、正式表にはsmoke_finalだけを使用。/tmpの単戦プローブ1戦を含む開発動作確認253戦は正式集計に含めない。", "",
        "通常DB・ボス・成長/戦闘式を変更していない。コミット・push・mainマージは行わず、本測定前にここで作業を区切る。"]
    (Path(__file__).parent/"SIMULATION_V2_RESULTS.md").write_text("\n".join(lines)+"\n")
    print(json.dumps({k:result[k] for k in ["smoke_battles","pilot_executions","pilot_unique_case_seeds","duplicate_executions","seconds_per_battle","main_all_300_estimated_hours"]},ensure_ascii=False))


if __name__=="__main__":
    main()
