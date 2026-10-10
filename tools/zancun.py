# -*- coding: utf-8 -*-
"""算仓交付工具：会前问卷生成 + 会后复算记录自动出稿

设计目标：把单次交付从 3 小时压到 1.5 小时内。
本机适配：纯文本处理 + 少量算术，3.9 GB 内存无压力。

用法:
  python tools/zancun.py questionnaire <客户ID>      # 生成会前问卷
  python tools/zancun.py record <客户ID>             # 生成会后复算记录骨架
  python tools/zancun.py check <json文件>            # 校验参数合理性
"""
import json
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENTS = ROOT / "data" / "zancun"
CLIENTS.mkdir(parents=True, exist_ok=True)

# 五参数定义：锚点表摘自《参数拆解_五参数计算方式》
PARAMS = {
    "p": {
        "name": "成功率",
        "question": "这条路被走通过吗？走通的人长什么样？",
        "anchors": [
            (9, 10, "路径可复制：同岗位前人普遍达成我想要的状态，机制清楚"),
            (7, 8, "有可查的成功样本，但需自己补齐若干条件（语言/资源/时机）"),
            (4, 6, "样本稀少或强路径依赖，有人成但说不清为什么成"),
            (1, 3, "无先例，或成功依赖运气事件"),
        ],
        "evidence": [
            "一手访谈：该岗位 3-8 年从业者，直接问'你后悔吗''和你入职时想的一样吗'",
            "半手数据：招聘网站该岗位的年限-职级要求（看 JD 里有没有'3-5年经验'的岗）",
            "公开履历：同岗位人员晋升轨迹抽样，看中位数而非幸存者",
        ],
        "pitfalls": [
            "用'行业平均薪资涨幅'代替'我个人达成目标状态的概率'",
            "用幸存者案例（某人做到了）代替中位数",
        ],
        "rule": "锚点分 ÷ 10 ÷ 1.2 = 修正后 p",
    },
    "G": {
        "name": "上行收益",
        "question": "如果 p 兑现，这个岗位让我多出哪些可带走的东西？",
        "anchors": [
            (10, 10, "三栏全满且离开平台仍保值"),
            (7, 8, "两栏实、一栏虚"),
            (4, 6, "只有履历背书（离开即折价）"),
            (1, 3, "收益主要是'在里面才有效'的头衔和福利"),
        ],
        "columns": ["履历背书（平台名头在下一个市场的兑换力）", "稀缺技能（离开后市场供给少的能力）", "先发身位（时间窗口红利）"],
        "discount": "兑现周期超 5 年按 ×0.7，超 8 年按 ×0.5",
        "pitfalls": ["把平台的能力当成自己的能力（背书≠技能）", "把'听起来体面'当成可兑换资产"],
    },
    "C": {
        "name": "下行成本",
        "question": "如果干砸或干得不顺，我损失什么？",
        "anchors": [
            (10, 10, "不可逆损失（健康、应届身份烧掉、债务）"),
            (7, 8, "烧掉一次性窗口 + 替代机会真实存在且不差"),
            (4, 6, "可恢复的时间与金钱损耗"),
            (1, 3, "试错成本可忽略"),
        ],
        "columns": ["明面成本（金钱/异地生活/健康）", "时间成本（年数 × 市场机会价值）", "机会成本（必填：放弃的最优替代）"],
        "pitfalls": ["只算苦不算替代（漏机会成本）", "把'反正现在也没别的offer'当成替代为零"],
        "note": "替代是'下一份能拿到的最好offer'，不是零",
    },
    "R": {
        "name": "可逆性",
        "question": "干砸了，能退吗？",
        "anchors": [
            (10, 10, "无摩擦无折价随时退出"),
            (7, 8, "有摩擦但履历保值"),
            (4, 6, "退出有实质折价"),
            (1, 3, "退出即行业/身份清零"),
        ],
        "questions": ["退出摩擦：随时可离职？还是有竞业/押金/档案/签证绑定？", "退出折价：这段经历在下一市场被正确定价吗？"],
        "extra": "消耗不可再生资源（应届身份/落户/年龄窗口）在锚点分上再降 1-2 分",
    },
    "L": {
        "name": "复利性",
        "question": "攒下的东西，离开后是会继续长，还是停在原地？",
        "anchors": [
            (10, 10, "核心产出本身就是资产（作品/客户/方法论）"),
            (7, 8, "资产型为主、消耗型为辅"),
            (4, 6, "两者相当"),
            (1, 3, "纯消耗型，越干越贬值"),
        ],
        "categories": ["资产型：客户网络、可迁移技能、稀缺资质、个人品牌", "消耗型：纯执行熟练度、仅限本平台的流程经验、不可迁移的头衔"],
        "pitfalls": ["把'忙碌'当'积累'——最忙的岗位常常最消耗", "把头衔当资产"],
    },
}


def _client_dir(cid):
    d = CLIENTS / cid
    d.mkdir(exist_ok=True)
    return d


def questionnaire(cid):
    """生成会前问卷：客户填写后 AI/人工核对，作为会中输入"""
    out = _client_dir(cid) / "01_会前问卷.md"
    today = datetime.date.today().isoformat()
    L = [f"# 算仓 · 会前问卷（{cid}）", "", f"> 填写日期：{today}　|　预计用时 15 分钟", "",
         "**说明**：不需要一次填对。填「大概」即可，60 分钟的通话会一起校准。", "",
         "---", "", "## 基础信息", "",
         "- 你正在纠结的具体决定是什么（一句话）：", "- 这个选项的下一步动作截止时间：",
         "- 如果什么都不做，三个月后会怎样：", "", "---", ""]

    for k in ["p", "G", "C", "R", "L"]:
        d = PARAMS[k]
        L += [f"## {k} · {d['name']}", "", f"**核心问题**：{d['question']}", ""]
        if "columns" in d:
            L += ["**请分栏填写**（每栏给一个 1-10 的粗略分即可）：", ""]
            for c in d["columns"]:
                L.append(f"- {c}：__ 分")
            L.append("")
        if "categories" in d:
            L += ["**请判断**（勾选或说明）：", ""]
            for c in d["categories"]:
                L.append(f"- {c}：__")
            L.append("")
        if "questions" in d:
            L += ["**请回答**：", ""]
            for q in d["questions"]:
                L.append(f"- {q}")
            L.append("")
        if "discount" in d:
            L += [f"**注意**：{d['discount']}", ""]
        if "extra" in d:
            L += [f"**注意**：{d['extra']}", ""]
        if "evidence" in d:
            L += ["**你可以用的证据**（有什么就填什么）：", ""]
            for e in d["evidence"]:
                L.append(f"- {e}")
            L.append("")
        L += ["**先自查这些坑**（诚实回答）：", ""]
        for pit in d.get("pitfalls", []):
            L.append(f"- [ ] 我可能犯：{pit}")
        L += ["", f"**你的初步值**：__ （1-10 粗估即可）", "", "---", ""]

    L += ["## 你最担心的一个问题", "",
          "（例如：万一算错了怎么办？我会不会被这套话术牵着走？）", "", ""]

    out.write_text("\n".join(L), encoding="utf-8")
    return out


def check(params_file):
    """校验参数合理性：p 口径、锚点区间、C 机会成本是否填、R×L 警戒"""
    p = json.loads(Path(params_file).read_text(encoding="utf-8"))
    warns = []
    raw_p = p.get("p_anchor")
    if raw_p is None:
        warns.append("缺 p 的锚点分（1-10 制），无法推出修正后 p")
    else:
        if not 1 <= raw_p <= 10:
            warns.append(f"p 锚点分 {raw_p} 超出 1-10 区间")
        expected = raw_p / 10 / 1.2
        got = p.get("p", 0)
        if abs(expected - got) > 0.005:
            warns.append(f"p 修正值不符：应为 {raw_p}/10/1.2 = {expected:.3f}，当前填 {got}")

    for k in ["G", "C"]:
        v = p.get(k)
        if v is None:
            warns.append(f"缺 {k}")
        elif not 0 <= v <= 10:
            warns.append(f"{k}={v} 超出 0-10 区间")

    if p.get("C") is not None and p.get("C_alternative") in (None, "", 0):
        warns.append("C 的机会成本未填——这是最常见的自欺来源（只算苦不算替代）")

    R, L = p.get("R"), p.get("L")
    if R is not None and L is not None:
        rl = R * L
        if rl < 10:
            warns.append(f"⚠ R×L = {rl:.1f} < 10，触发警戒线：最高轻仓 + 12 个月止损")

    if p.get("G") is not None and p.get("C") is not None and p.get("G") == p.get("C"):
        warns.append(f"G=C={p['G']}：零和情形，S 随 p 线性变化，请确认是否真的值得做")

    return warns


def record(cid, params, prediction="", verify_date="", notes=""):
    """生成会后复算记录（Markdown）+ facts.json

    参数顺序固定为 prediction, verify_date, notes，避免调用方错位。
    """
    warns = check_from_dict(params)
    p, G, C = params.get("p"), params.get("G"), params.get("C")
    S = p * G - (1 - p) * C if all(x is not None for x in (p, G, C)) else None
    R, L = params.get("R"), params.get("L")
    rl = R * L if all(x is not None for x in (R, L)) else None

    band = "不打" if S is not None and S < 0 else ("持有" if S is not None and S <= 2 else ("重仓" if S is not None else "?"))
    today = datetime.date.today().isoformat()

    L_ = [f"# 算仓复算记录 · {cid}", "", f"> 会话日期：{today}　|　模型：决策体系 v1.8.3", "",
          "## 参数", "", "| 参数 | 值 | 说明 |", "|---|---|---|"]
    for k, label in [("p", "成功率"), ("G", "上行收益"), ("C", "下行成本"), ("R", "可逆性"), ("L", "复利性")]:
        L_.append(f"| {k} | {params.get(k, '—')} | {label} |")
    L_ += ["", f"- p 锚点分：{params.get('p_anchor', '—')} → ÷10 ÷1.2 = {p}", ""]
    if S is not None:
        L_ += ["## 计算", "", "```", f"S = p×G − (1−p)×C", f"  = {p}×{G} − {1-p:.3f}×{C}",
               f"  = {p*G:.2f} − {(1-p)*C:.2f}", f"  = {S:.2f}", "```", ""]
    if rl is not None:
        L_ += [f"- R×L = {rl:.1f}" + ("　⚠ **低于警戒线 10：最高轻仓 + 12 个月止损**" if rl < 10 else "　高于警戒线"), ""]
    L_ += ["## 判定", "", f"- 得分 **{S:.2f}** → **{band}**" if S is not None else "- 得分待补", "",
           f"**预测**：{prediction}", "", f"**验证截止**：{verify_date}", ""]
    if notes:
        L_ += [f"**备注**：{notes}", ""]
    if warns:
        L_ += ["## 校验提示", ""] + [f"- ⚠ {w}" for w in warns] + [""]

    L_ += ["---", "", "## 会后行动清单", "",
           "- [ ] 五个参数已存档（含证据源）", "- [ ] 预测已写死口径，验证日期已定",
           "- [ ] 战绩板已登记", "- [ ] 是否授权公开案例（可匿名）：是 / 否", ""]

    out = _client_dir(cid) / "02_复算记录.md"
    out.write_text("\n".join(L_), encoding="utf-8")

    facts = {"date": today, "cid": cid, "p": p, "G": G, "C": C, "R": R, "L": L,
             "S": round(S, 2) if S is not None else None, "band": band,
             "prediction": prediction, "verify_date": verify_date,
             "warnings": warns, "notes": notes}
    (_client_dir(cid) / "facts.json").write_text(
        json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    return out, facts


def check_from_dict(p):
    tmp = ROOT / "data" / "_tmp_check.json"
    tmp.write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
    try:
        return check(tmp)
    finally:
        tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print(__doc__)
    elif sys.argv[1] == "questionnaire":
        print(questionsaire(sys.argv[2]) if False else questionnaire(sys.argv[2]))
    elif sys.argv[1] == "check":
        for w in check(sys.argv[2]):
            print("⚠", w)
    elif sys.argv[1] == "record":
        pf = Path(sys.argv[2])
        params = json.loads(pf.read_text(encoding="utf-8"))
        out, facts = record(params.get("cid", "C"), params,
                            params.get("prediction", ""), params.get("verify_date", ""),
                            params.get("notes", ""))
        print(f"已生成: {out}\nS={facts['S']} 判定={facts['band']}")
