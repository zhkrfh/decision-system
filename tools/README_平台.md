# OPC 能力平台

> 建立：2026-10-10
> 目标：把分散的工具聚合成一条命令，按本机约束（4 核 / 3.9 GB）设计

---

## 一条命令

```bash
python tools/opc.py <子命令>
```

---

## 子命令

| 命令 | 作用 | 底层模块 |
|---|---|---|
| `doctor` | **环境快速诊断**（先跑这个） | 全部 |
| `all` | 全量只读检查（5 项） | 全部 |
| `health` | 本机健康快照 | capability |
| `evos ...` | 经验系统 | evos |
| `content ...` | 内容中心 | dispatcher / content |
| `publish ...` | 发布分发 | dispatcher / wx_api |
| `zancun ...` | 算仓交付 | zancun |
| `cap ...` | 能力层（LLM/转写） | capability |
| `git ...` | 仓库操作 | git |

---

## 设计约束

### 为什么这样设计

本机 4 核 / 3.9 GB 内存 / 无 GPU 算力。由此确定三条纪律：

1. **无常驻进程** —— 所有子命令都是一次性执行，跑完即退
2. **重计算走云端** —— `capability.py` 封装 API 调用，本机只做 IO 等待
3. **解释器自动选择** —— `run_tool()` 优先用带 requests 的 venv，回退到当前解释器

### 已装环境

```
Python 3.13.12      C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\
requests 2.34.2     ...\envs\default\        （dispatcher 依赖）
Git / Node          系统自带
```

---

## doctor 输出示例

```
==========================================================
 OPC 平台诊断
==========================================================

[本机]
  系统     Windows-10-10.0.19045-SP0
  内存     0.2/3.9 GB (占用 95%)
  C: 盘     可用 12.1/70.0 GB
  E: 盘     可用 145.8/168.5 GB

[工具链]
  ✓ Python  C:\...\python.exe
  ✓ Git
  ✓ Node
  ✓ requests 2.34.2 @ envs(2.34.2)

[项目模块]
  17 个模块: capability, content, dispatcher, evos, ...

[关键能力]
  ○ 大模型
  ○ 语音转写
  ✓ 公众号
  ✓ GitHub
  ✓ 知乎

  提示：大模型 API 未配置 → 本机无法本地推理

[EVOS]
  经验 10 条: {'observing': 8, 'pending_verification': 1, 'codified': 1}
  预测 #1 25天
```

**当前唯一缺口：大模型 API。** 其余三项已配置。

---

## 17 个模块分工

| 模块 | 行数 | 职责 |
|---|---|---|
| `evos_core.py` | 382 | 四环引擎（捕获/提炼/晋升/回验） |
| `capability.py` | 276 | 能力层：LLM 调用、语音转写、健康快照 |
| `zancun.py` | 258 | 算仓交付：问卷生成、参数校验、复算记录 |
| `evos_hook.py` | 152 | 自动捕获钩子（包裹式） |
| `evos.py` | 125 | EVOS CLI |
| `flows.py` | 122 | 分发流程 |
| `prep_xhs_dp.py` | 103 | 小红书自动预填 |
| `md2html.py` | — | Markdown 转 HTML |
| `mp_adapt.py` | — | 多平台适配 |
| `xhs_cards.py` | — | 小红书卡片图 |
| `wx_api.py` | — | 公众号 API |
| `zhihu_api.py` | — | 知乎 API |
| `store.py` | — | CSV 读写 |
| `content.py` | — | 内容状态机 |
| `prep.py` | — | 平台预填 |
| `dispatcher.py` | — | 统一入口（v0.6 模块化） |
| `opc.py` | — | **本平台入口** |

---

## 常用工作流

### 每天开工
```bash
python tools/opc.py all        # 一眼看清状态
```

### 内容生产
```bash
python tools/opc.py content plan          # 看今日待办
python tools/opc.py publish wx-check      # 灌稿前校验
python tools/opc.py publish prep xhs      # 小红书预填
```

### 交付客户
```bash
python tools/opc.py zancun questionnaire C-001   # 发问卷
python tools/opc.py zancun record params.json    # 出复算记录
```

### 每周复盘
```bash
python tools/opc.py evos verify      # 三个指标
python tools/opc.py evos scan        # 到期预测
python tools/opc.py all              # 全量
```

---

## 待补能力

| 能力 | 阻塞原因 | 优先级 |
|------|---------|--------|
| **大模型 API** | 未配置 | P0 |
| **语音转写 API** | 未配置 | P1（家史服务前提） |
| Windows Defender | 服务通道被沙箱阻断，需用户手动修复 | P0（安全） |

---

## 相关文档

| 文档 | 内容 |
|------|------|
| `docs/自我进化操作系统架构_v1.0.md` | EVOS 四环设计 |
| `docs/能力拓宽清单_待开通API.md` | 待开通接口清单 |
| `docs/OPC价值最大化方案_硬件适配.md` | 硬件约束下的业务取舍 |
| `EVOS/README.md` | EVOS 使用说明 |
