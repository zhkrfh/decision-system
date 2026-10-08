# 学习日志 #3：Hindsight——Agent 记忆系统（vectorize-io/hindsight）

> 2026-10-08 每日学习任务
> 来源：GitHub Trending 周榜；已核对 README、官方发布博文与对比评测（Mem0/GSupermemory/GBrain）

## 项目定位

- **是什么**：开源（MIT）的 agent 记忆系统，主打"会学习的记忆"而非"会回忆的记忆"。LongMemEval 长时记忆基准 SOTA，优于 Mem0/Supermemory 及全上下文基线。
- **与竞品的差异**：Mem0/Supermemory 做的是"结构化检索层"；Hindsight 把记忆当作推理的一等基础（first-class substrate），强调证据与推断分离、时间锚定、信念可更新。
- **形态**：REST API（retain/recall/reflect 三操作）、bank 隔离、MCP server、Python/Go/TS 客户端，60+ 集成，可 Docker/嵌入式部署。

## 关键机制

1. **四层记忆网络**：facts（事实）/ experiences（经验）/ observations（多条记忆合并、有证据支持的信念）/ opinions（心智模型）。核心设计原则：**证据与推断分离**——observations 必须能追溯到 facts。
2. **三操作闭环**：
   - retain：从交互中提取事实、实体、关系与时间数据；
   - recall：并行跑语义、关键词、图谱、时间四条检索通道，融合排序，在 token 预算内返回；
   - reflect：基于记忆推理回答问题，并更新信念（新连接）。
3. **bank 隔离 + PII/机密模式扫描**：多租户、路径 `/v1/{tenant}/banks/{bank}/`，写入时做防御性扫描。
4. **工程取舍**：混合 Postgres 检索（非纯向量库），MCP 化暴露（对应上篇日志 TryPost 的 MCP 趋势，再次印证）。

## 对本项目可借鉴之处

1. **案例库的"证据/推断分层"（直接可用）**：正典仓库 5 个案例（案例01–05）天然就是两层——具体数字与事实（−7.5 不打、1.12 岗位 S 值）是 facts，"因此结论/警惕"段落是 observations。目前素材/案例混排，可借鉴 Hindsight 的分层给检索与改稿带来精度。
2. **四通道检索思路**：语义 + 关键词 + 实体 + 时间并行召回再融合，比单一路径健壮。我们的选题侦察（选题侦察_20261007.md）和 dispatcher 素材检索都是单通道。
3. **bank 隔离模型**：对应我们的"决策课程 / 小说 / 求职 / 一人公司"四条线，记忆与素材互不污染。
4. **MCP 化再次得到印证**：Hindsight、TryPost、GBrain 全部提供 MCP server——分发台 MCP 化（上篇日志 P2 待办）方向正确。

## 是否值得迁移进决策课程的工具或管线

- **值得小规模迁移**：案例分层（facts/observations）可立即用于算分表素材与公众号改稿——写 observation 时强制注明 fact 依据，与"不打无证据的分"的课程精神同构。
- **不值得整体迁移**：Hindsight 本身是重基础设施（Postgres + API + 控制面），我们量级（5 案例 + 灵犀自带记忆系统）不需要自建记忆服务。

## 小规模验证（当日完成）

- 用 Python 对 5 个案例 md 做了迷你 retain（启发式拆 facts/observations）+ recall（关键词融合、fact 层加权）。
- 结果："裸辞 收益 风险" 查询正确召回案例03 的核心 fact（−7.5 深度负值、不打）并排在首位，验证分层检索对案例问答有效。
- 改进点：中文整词分词在无分词库时召回率低，需改用双字滑窗（验证因内存不足暂停，结论：粗粒度关键词不够，要滑窗或 jieba）。
- 验证环境当日内存紧张（总 4GB、可用 146MB），仅完成单查询演示；结论方向可信，规模验证待内存恢复后补跑。

## 待办更新

- P3（新）：给案例01–05 建 facts/observations 分层索引（纯 md 元数据或简易 json），供算分表与公众号改稿引用时溯源。
- 维持 P2：dispatcher MCP 化（本项目再次印证趋势）。
