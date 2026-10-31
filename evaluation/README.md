# 验证与真实模型评测

单元和集成测试验证软件状态与数据链路，不证明模型学科答案正确。

## 自动化回归

在 backend 目录运行：

```powershell
..\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
```

覆盖跨学科输入传递、完整作答、画像与反馈上下文、空答案、不完整题目、结构修复、模型错误、证据复核门槛、重复作答、并发写入、会话归属和持久化。

测试会隔离本机 `.env` 中的模型配置与数据库路径，使用临时数据库和模型替身。理解检查另有 `answer_to` 回归，验证新回答的题目范围在当前轮与历史中保持一致。

## 接入真实模型后的验收

每组至少使用两种不同画像，保存题目、原始作答、模型名、配置、返回内容及人工检查结果。不要只检查“HTTP 200”或“JSON 字段齐全”。

| 场景 | 必须检查 |
| --- | --- |
| 非预设任务：证明、实验设计、代码排错、材料比较、跨学科方案 | 不退化为口算/作文模板，讲解针对真实约束 |
| 单位、百分比、方程、多解、完整演算过程 | 评估完整语义，不截取首个数字 |
| 开放回答：优质/缺证据/偏题 | 同一题的不同作答产生有依据的差异 |
| 缺文章、缺图、缺实验数据 | 主动澄清，不补造材料 |
| 图文共同给条件 | 两种材料均被使用，不能忽略图或备注 |
| 学习节奏慢、兴趣不同、已有具体薄弱观察 | 步骤、例子和追问随画像改变，并说明依据 |
| 不懂反馈、多轮纠正 | 实际改变解释，保留题目上下文 |
| 迁移练习 | 题干自足、可解、有检查标准且不超出当前目标 |
| 新答案/相同答案重新讲解 | 新证据可入库，同一次作答不重复计数 |
| 错误参考解、模型故障、无效 JSON | 降级可见，不展示未经验证讲解或写入错误画像 |

人工记录四项：学科正确性、作答评估依据、画像使用是否合理、下一步是否可执行。涉及复杂学科材料时由熟悉该内容的人复核。

模型复核会发生相关错误。即使配置第二个模型，也不能把“复核通过”当成外部权威证明。

## 可重复运行的真实模型用例

2026-10-31 的实测、发现的问题与修复后对照见 [实测报告](live_model_report.md)。逐题原始返回保存在 `runs/`；没有用 HTTP 成功率代替讲解准确率。

在项目根目录运行以下命令，会使用 `backend/.env` 已配置的模型并产生真实 API 费用。每次指定一个新的空输出目录：

```powershell
.\.venv\Scripts\python.exe -B evaluation/live_model_eval.py --out evaluation/runs/my-run
```

也可以只测指定题目，最多同时请求两道题：

```powershell
.\.venv\Scripts\python.exe -B evaluation/live_model_eval.py --out evaluation/runs/my-pair --cases density_novice density_advanced --workers 2
```

负反馈与追问测试可从已完成的初学者记录恢复合成会话：

```powershell
.\.venv\Scripts\python.exe -B evaluation/live_model_eval.py --out evaluation/runs/my-followup --followup-from evaluation/runs/my-pair/density_novice.json
```

也可以重现已经被拦截的真实候选，只为修订与再次复核发起新的真实调用：

```powershell
.\.venv\Scripts\python.exe -B evaluation/live_model_eval.py --out evaluation/runs/my-revision --revise-from evaluation/runs/logic_final/history_sources.json
```

该模式明确记录 `replayed_stages`：最初的分析、讲解、复核来自指定的真实记录，不计作新的模型调用；`stages` 只记录本次真正调用的修订和再次复核。这用于确定性复现错误，不能冒充一次全新完整生成或把选到通过结果作为准确率。

脚本使用内存数据库与合成画像，不修改日常学生记录，不保存密钥或请求头。每个用例记录题干、作答、画像、预期核对点、实际响应、各阶段输入输出、耗时及模型调用次数；`provenance.json` 保存模型名和源文件哈希。后续运行还会保存阶段提示词与结构名称，便于追溯。已有目录拒绝覆盖。

默认包含数学增根、Python 引用与遍历删除、化学限量试剂、历史材料证据、英语语义改写、跨学科约束设计、密度的两种画像、完整正确作答以及材料缺失。用例只存在于评测脚本中，不参与应用题型路由。`pytest` 不会运行这些付费调用。

`completed` 仅表示应用流程完成。阅卷还应检查所有备选答案、家长提示、理解检查与练习评分，特别区分相容与等价、未证实与反驳；不要只核对第一条参考答案。历史记录可能包含已修复的错误，阅读时请结合实测报告标注的运行版本。

