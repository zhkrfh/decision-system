# EVOS · 自我进化操作系统

> 建立：2026-10-10 ｜ 架构：`docs/自我进化操作系统架构_v1.0.md`
> 代码：`tools/evos.py`（CLI）+ `tools/evos_core.py`（引擎）

---

## 这是什么

一个**增量叠加层**，包裹现有的 dispatcher、内容状态机与 git 仓库，不侵入任何已有代码。

存在的理由：你现在的踩坑是**一次性收益**（解决了就不再犯，但没系统性变强）。EVOS 把它们变成**累积性资产**。

---

## 快速开始

```bash
cd 正典仓库

python tools/evos.py status        # 看板
python tools/evos.py verify        # 周度回验
python tools/evos.py scan          # 扫描到期预测
```

---

## 目录

```
EVOS/
  experience.jsonl    经验库（每行一条 JSON）
  skills/             已固化规则导出目录（待批准后写入）
  README.md           本文件
tools/
  evos.py             CLI 入口
  evos_core.py        四环引擎
```

---

## 四环

```
捕获 Capture ──→ 提炼 Distill ──→ 晋升 Promote ──→ 回验 Verify
    ↑                                                      │
    └──────────────────────────────────────────────────────┘
```

### 环 1 · 捕获（自动）

```bash
python tools/evos.py log bash_error "灌稿接口报错" "40007"
```

**捕获必须自动**。靠人写复盘的系统三个月后就死了。

### 环 2 · 提炼（AI）

```bash
python tools/evos.py distill EVOS-20261010-001 \
  "凭证与账号不匹配" "灌稿前先校验 AppID/Secret 配对"
```

**归因质量决定规则质量。** 例：微信返回 40007 的根因不是「接口报错」。

### 环 3 · 晋升（有门槛）

```bash
python tools/evos.py trial  EVOS-20261010-003    # 观察 → 试行
python tools/evos.py noted  EVOS-20261010-003 "实际用于发布，成功"
python tools/evos.py codify EVOS-20261010-003 clean
python tools/evos.py rollback EVOS-20261010-003 "固化后仍致同类错误"
```

| 阶段 | 进入条件 | 行为 |
|------|---------|------|
| observing | 首次记录 | 只记录，不影响行为 |
| trialing | observed_count ≥ 2 **且**根因已填 | 影响行为，**主动告知** |
| codified | 试行干净**或**观察 ≥3 次 | 永久规则 |
| rolled_back | 固化后仍致同类错误 | 自动降级并标记 |

**两条硬门槛（已实测生效）**：
- 未达观察次数 → 拒绝进入试行
- 未提炼根因 → 拒绝进入试行
- 固化必须显式指定 `clean` / `dirty`，不能省略

### 环 4 · 回验（决定生死）

```bash
python tools/evos.py verify
```

| 指标 | 定义 | 目标 |
|------|------|------|
| 复发率 | 近 90 天活跃条目占比 | 观察期应下降 |
| 固化规则有效率 | 固化后被实际触发过的比例 | > 70% |
| 净收益（代理） | 试行次数 − 2×回滚 | 持续为正 |

**淘汰机制**：
- 90 天未触发且未验证有效 → `archive`
- 固化后仍致 ≥2 次新错误 → `rollback`

> 只进不出的记忆库会无限膨胀，最终无法检索。**归档是维护，不是失败。**

---

## 记忆分层与隔离

| 层 | 位置 | 生命周期 | 谁能改 |
|----|------|---------|-------|
| L1 执行记忆 | `EVOS/experience.jsonl` | 日级滚动 | AI 自动 |
| L2 技能规则 | `EVOS/skills/` | 月级复审 | AI 建议 + 作者批准 |
| L3 项目规范 | `docs/` | 版本化 | 作者签署 |
| **L4 理论口径** | 冻结文档 | **作者独占** | **仅作者** |

**隔离已实装**：`guard_scope()` 会拒绝任何指向 L4/theory/formula/口径 的操作。

> 这是自我进化系统最大的危险：系统会为了省事，悄悄把未验证的理论「优化」掉。

---

## 捕获源

| 类型 | 触发 | 默认严重度 |
|------|------|-----------|
| `bash_error` | 命令非零退出 | medium |
| `user_correction` | 「不对」「重做」等语义信号 | high |
| `prediction_fail` | 战绩板验证到期未登记 | high |
| `platform_fault` | API 4xx/5xx、限流、验证码 | medium |
| `flip-flop` | 同操作连续 3 次结果不一致 | low |

### 预测到期扫描

```bash
python tools/evos.py scan
```

直读 `docs/战绩板.md`，输出每条预测的剩余天数。当前：**案例01 还有 25 天**（截止 2026-11-04）。

---

## 当前状态

**8 条经验**（从 72 次提交 + 灵犀会话 + 本机扫描回填）：

| 状态 | 数量 |
|------|------|
| codified | 1（EVOS-003 小红书弹层选择器） |
| observing | 6 |
| pending_verification | 1（案例01 预测） |

**已跑通完整闭环**：EVOS-003 从 observing → trialing → codified，全程门槛与人工确认均生效。

---

## 演化能力三级判据

| 级别 | 判据 | 状态 |
|------|------|------|
| L1 记录型 | 能记住发生过什么 | ✅ 已具备 |
| L2 调整型 | 能根据经验改变行为 | ✅ 已具备（经门槛晋升） |
| L3 演化型 | 自动发现「该改什么」并验证有效性 | ⚠️ 部分（晋升需人工确认） |

**目标：把「是否该改」的判断也自动化，但保留作者对固化的最终确认权。**

---

## 每周复盘仪式

固定**周日 20:00**（与既有数据回填任务合并）。

1. `python tools/evos.py verify` —— 看三个指标
2. `python tools/evos.py scan` —— 看有无到期预测
3. 处理 `eligible_for_trial`（进入试行）
4. 处理 `suggest_rollback` / `to_archive`
5. 回答：本周有无新经验该捕获？

---

## 防护机制

| 风险 | 防护 | 状态 |
|------|------|------|
| 记忆库膨胀 | 90 天归档 + 分层 | ✅ 已实装 |
| 错误规则固化 | 试行期 + 回滚通道 | ✅ 已实装 |
| 理论被污染 | L4 隔离 + 作者独占 | ✅ 已实装 |
| 进化噪声 | 晋升门槛（次数 + 根因） | ✅ 已实装 |
| 过度自动化 | 固化需显式确认 | ✅ 已实装 |

---

## 与既有系统的关系

| 既有 | 关系 |
|------|------|
| `dispatcher.py` 826 行 | **不动**。EVOS 在其外层包裹 |
| `content_index.csv` 状态机 | **不动** |
| 灵犀 `self-improvement` | 迁移为环 1 捕获器 |
| 灵犀 `skill-evolution-manager` | 迁移为环 3 晋升器 |
