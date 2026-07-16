# Self-Studying Agent

一个面向家长的 AI 家教助手 Agent，核心不是给孩子直接抄答案，而是帮助家长更懂孩子、更会辅导孩子。

## 一句话定位

> 以动态四维用户画像为神经中枢，驱动一个面向家长的、多风格、可解释的 AI 辅导引擎。

## 产品目标

很多家教产品最终会退化成“答案机”。本项目的定位是 **家长的辅导工具**，不是孩子的直接作业助手。

核心价值：

- 帮家长判断孩子是“不会”，还是“粗心”
- 帮家长选择更适合孩子的讲解方式
- 帮家长生成适合当前能力和认知风格的讲解与练习

## 核心使用场景

### 1. 学情诊断

- 判断孩子的错误属于概念不懂、计算失误还是审题问题
- 定位薄弱知识点及其前置依赖
- 追踪同一知识点的反复出错情况

### 2. 辅导策略推荐

- 根据孩子画像选择讲解方式
- 生成“给家长看的讲解卡片”
- 提供关键提问、道具建议、易错点提醒

### 3. 内容生成与匹配

- 生成适合当前水平的讲解
- 生成针对薄弱点的跟进练习
- 根据兴趣主题和认知偏好改写题目表达

## 系统架构

```text
┌──────────────────────────────────────────┐
│              家长端交互层                 │
│  拍照/语音输入 → 诊断结果 + 辅导方案      │
└──────────────────┬───────────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│           Agent 核心编排层               │
│  - 意图识别：批改 / 讲解 / 出题 / 诊断    │
│  - 多轮对话管理                           │
│  - 工具调用：计算 / 检索 / 画图           │
│  - 输出策略选择：基于用户画像             │
└──────────────────┬───────────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│             领域服务层                    │
│  - 题目解析                               │
│  - 批改引擎                               │
│  - 知识图谱追踪器                         │
│  - 讲解生成                               │
│  - 风格适配                               │
│  - 错题管理                               │
│  - 练习生成                               │
│  - 画像更新                               │
└──────────────────┬───────────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│            数据与画像层                   │
│  - 静态画像：年龄 / 年级 / 教材版本       │
│  - 动态认知画像：知识点掌握概率           │
│  - 行为风格画像：学习风格 / 注意力曲线    │
│  - 情感动机画像：挫败感 / 兴趣领域        │
└──────────────────────────────────────────┘
```

## 各层职责说明

### 家长端交互层

输入形式：

- 拍照上传作业
- 家长语音提问
- 点选反馈：有用 / 没用 / 孩子还是不懂

输出形式：

- 面向家长的错误诊断
- 可执行的讲解建议
- 适合当前阶段的练习推荐

### Agent 核心编排层

负责协调所有能力：

- 识别当前意图：批改、讲解、诊断、出题
- 查询该孩子已有画像
- 按画像选择输出风格
- 编排多轮辅导过程

典型调用链：

1. 家长问“这道题怎么讲孩子才能懂”
2. Agent 查询画像
3. 调用知识点识别与错误分类
4. 调用讲解风格适配器
5. 生成给家长的讲解卡片

### 领域服务层

这是可复用的教学能力集合：

- **题目解析**：识别题干、答案、知识点
- **批改引擎**：判断正误并解释原因
- **知识图谱追踪器**：维护知识点掌握度
- **讲解生成器**：输出符合年级和教材范围的讲解
- **风格适配器**：按视觉型/听觉型/动手型调整内容
- **错题管理器**：组织复习闭环
- **练习生成器**：生成针对薄弱点的变式题
- **画像更新器**：根据交互结果更新用户画像

### 数据与画像层

画像不是静态标签，而是持续演化的模型，是整个系统的核心资产。

## 四维动态用户画像

### 1. 认知画像（核心）

- **知识点掌握概率**：例如“分数加法 0.82、分数减法 0.45”
- **错误类型标签**：概念错误、计算失误、审题不清、步骤遗漏
- **能力维度评估**：计算能力、逻辑推理、空间想象、应用题转化

推荐做法：

- 使用贝叶斯知识追踪(BKT)维护每个细粒度知识点的掌握概率
- 将每次答题结果映射到知识图谱节点与错误标签

落地建议：

- MVP 阶段可按“题目结果 + 知识点标签”作为 BKT 输入，输出每个知识点的掌握概率更新
- BKT 适合早期冷启动，计算成本低、解释性强，便于向家长说明“为什么系统认为这个知识点仍需练习”
- 相比 DKT、IRT 等方法，BKT 更适合作为首版方案，因为它对样本规模和工程复杂度要求更低，更容易快速验证画像驱动的辅导闭环
- 知识点粒度建议下沉到“可教学、可诊断、可练习”的最小单元，例如“分数”继续拆成“同分母加法”“异分母减法”“通分”而不是只停留在章节级标签
- 例如一道“异分母分数减法”题答错且被标记为“通分错误”时，系统先降低“异分母减法”和“通分”两个节点的掌握概率，再把错误标签写入错因记录，供后续讲解策略选择使用

### 2. 学习风格画像

- 输入偏好：视觉型、听觉型、读写型、动手型
- 思维速度：冲动型 / 沉思型
- 讲解反馈：哪种讲法更容易“听懂”

### 3. 行为与情感画像

- 注意力曲线：连续练习时准确率与时长变化
- 挫败点：哪些题型一错就容易放弃
- 兴趣领域：如恐龙、汽车、太空、公主等

### 4. 基础档案

- 年龄
- 年级
- 地区
- 教材版本
- 家长辅导能力自评

## 最小数据闭环

1. 家长拍照上传一道错题
2. 系统识别题目并完成批改
3. 系统判断错误类型与所属知识点
4. 家长点选反馈，例如“孩子不懂这个概念”
5. 系统生成更适合的讲解方式
6. 孩子完成一题跟进练习
7. 系统更新知识点掌握度与风格偏好

这个闭环不依赖额外长问卷，而是从自然辅导交互中沉淀画像。

## 画像如何驱动 Agent 行为

| 决策点 | 通用方案 | 画像驱动方案 |
| ----- | -------- | ------------ |
| 讲题方式 | 给出标准解析 | 根据认知风格选择图示、比喻、实物操作 |
| 推荐练习 | 随机同类题 | 优先覆盖薄弱知识点及其前序依赖 |
| 激励策略 | 泛化鼓励 | 调用孩子过往成功经验进行鼓励 |
| 家长指引 | “请耐心辅导” | 提供具体操作、节奏与提问建议 |
| 输出对象 | 直接给孩子看 | 生成给家长看的辅导卡片 |

### 示例

如果孩子画像显示：

- 偏视觉型
- 对恐龙主题有兴趣
- 在“追击问题”上反复出错

系统输出给家长的建议应类似：

> 不要先列方程。拿出两个恐龙玩具，一个跑得快，一个跑得慢，让孩子用尺子量一量不同时间下的距离变化。关键提问是：“快的那只每分钟比慢的多走几步？”

## 输出原则

系统默认输出对象是家长，而非孩子。每次讲解都应优先生成：

- 这道题错在哪里
- 你可以怎么讲
- 你应该问孩子什么
- 需要准备什么道具或图示
- 如果孩子还不懂，下一步怎么做

## 技术方案建议

### 大模型层

- GPT / Claude 等大模型主要负责
  - 意图理解
  - 讲解生成
  - 家长辅导脚本生成

### 检索增强层

- 基于知识图谱的 RAG
- 保证讲解不超纲、不误导、符合教材体系

### 知识追踪层

- 初期可用 Python 实现轻量 BKT
- 中期可演进到更细粒度的动态知识追踪模型

### 数据与服务层

- **后端**: FastAPI + PostgreSQL + Redis
- **前端**: 微信小程序（家长端）

选型理由：

- FastAPI 适合快速搭建 Agent 编排、画像服务和推理接口，类型提示与接口文档能力更适合早期迭代
- PostgreSQL 适合承载用户档案、知识点记录、错题与反馈等结构化数据
- Redis 适合缓存会话上下文、短期任务状态和高频画像读取结果

## 分阶段实施路径

### MVP (1-2 个月)

时间预估默认前提：

- 1 名有相关经验的开发者约需 2 个月；2 名开发者并行推进可压缩到约 1 个月
- MVP 范围仅覆盖“拍照错题 → 诊断归因 → 给家长的讲解卡片”单一闭环

聚焦单一闭环：**错题诊断 + 针对性讲解**

流程：

1. 家长拍照上传
2. 系统识别、批改、归因
3. 系统生成给家长的讲解指南

MVP 画像只保留两个维度：

- 知识点掌握情况
- 学习风格偏好

学习风格的获取方式可先简化为讲解后的“有用/没用”反馈。

### 第二阶段

- 加入动态练习推荐
- 引入更完整的知识图谱
- 开始预测潜在薄弱点

### 第三阶段

- 开放给孩子有限交互
- 增加跟读、动手操作、AR 引导等能力
- 引入行为与情感信号，持续修正画像

## 必须坚持的产品原则

### 1. 不做答案机

- 优先输出辅导策略而非最终答案
- 可设置家长验证或激活环节
- 强调理解过程而不是直接结果

### 2. 隐私与安全优先

未成年学习数据高度敏感，必须：

- 在分析、展示和导出场景中按需做去标识化或数据掩码
- 在传输链路中使用 TLS 1.3
- 在持久化存储中使用 AES-256 等级加密，并通过受控密钥管理机制维护密钥
- 明确告知家长收集哪些数据、如何使用
- 提供数据导出与删除能力

### 3. 避免负面标签化

不要输出“孩子逻辑差”这类标签，应使用成长性表达，例如：

> 孩子在从具体到抽象的过渡阶段，还需要更多实物操作和图形辅助。

### 4. 画像持续校准

- 家长可以手动纠正讲解风格
- 系统将纠正行为作为反馈信号
- 接受画像初期不准，并持续迭代

## 当前仓库建议方向

本仓库后续可以按以下模块逐步落地：

- `docs/`：产品方案、画像设计、知识图谱设计
- `backend/`：Agent 编排、画像服务、题目处理服务
- `frontend/`：家长端小程序或 Web 端
- `evaluation/`：讲解效果与画像更新效果评估

## 成功标准

该 Agent 的成功不应只看“答对率”，还应关注：

- 家长是否更容易上手辅导
- 孩子是否更快理解薄弱知识点
- 讲解是否更贴合个体差异
- 用户画像是否随着使用越来越准确

## 当前已落地的工程骨架

```text
self-studying-agent/
├─ docs/
│  └─ architecture.md
├─ backend/
│  ├─ app/
│  │  ├─ api/v1/routes.py
│  │  ├─ orchestration/tutor_orchestrator.py
│  │  ├─ services/
│  │  │  ├─ problem_parser.py
│  │  │  ├─ grading_service.py
│  │  │  ├─ style_adapter.py
│  │  │  ├─ explanation_generator.py
│  │  │  └─ practice_generator.py
│  │  ├─ profile/bkt.py
│  │  ├─ repositories/profile_repository.py
│  │  ├─ schemas/
│  │  │  ├─ diagnosis.py
│  │  │  └─ profile.py
│  │  └─ main.py
│  ├─ tests/test_api.py
│  ├─ requirements.txt
│  └─ .env.example
├─ frontend/
│  └─ README.md
└─ evaluation/
   └─ README.md
```

### 已打通 MVP 请求链路

1. `POST /api/v1/diagnose`
2. 解析题目与知识点
3. 判断正误并给出错误类型
4. 基于画像与反馈选择讲解风格
5. 使用轻量 BKT 更新知识点掌握度
6. 返回给家长的讲解卡片、关键提问和跟进练习建议

## 本地启动

在 `backend/` 目录执行：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

启动后可访问：

- `GET /api/v1/health`
- `POST /api/v1/diagnose`

## 建议版后端接口契约

下面这版不是当前代码中已经全部实现的最终接口，而是基于“家长输入 → 诊断 → 辅导卡片 → 反馈回流”施工图纸反推出来的建议版契约。

设计目标：

- 让一次请求同时承载输入归一化结果、诊断上下文和家长期望
- 让响应结果不仅返回文本，还返回可渲染、可评估、可回流的结构化卡片
- 让反馈成为画像更新和风格切换的正式输入，而不是松散备注

### 接口定义

- `POST /api/v1/diagnose`
- 请求体：`DiagnoseRequest`
- 响应体：`DiagnoseResponse`

### DiagnoseRequest

| 字段 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| `request_id` | `str` | 否 | 请求唯一标识，便于日志追踪与幂等控制 |
| `session_id` | `str` | 否 | 当前辅导会话 ID，用于串联多轮上下文 |
| `parent_id` | `str` | 否 | 家长 ID，用于关联家长侧反馈和权限 |
| `student_id` | `str` | 是 | 学生唯一标识 |
| `subject` | `str` | 是 | 学科，如 `math`、`chinese` |
| `grade` | `str` | 否 | 年级，如 `grade-4` |
| `textbook_version` | `str` | 否 | 教材版本，用于控制讲解不超纲 |
| `input_mode` | `str` | 是 | 输入方式，如 `text`、`photo`、`voice`、`mixed` |
| `problem_text` | `str` | 是 | 归一化后的题干文本 |
| `student_answer` | `str \| None` | 否 | 学生当前作答内容，没有时允许为空 |
| `knowledge_points` | `list[str]` | 否 | 家长或系统已知的知识点标签 |
| `parent_goal` | `str` | 否 | 家长本轮目标，如“判断错因”“告诉我怎么讲” |
| `parent_note` | `str \| None` | 否 | 家长补充描述，如“孩子总是在通分这步卡住” |
| `attachments` | `list[str]` | 否 | 图片或音频资源引用，可先存文件 ID 或 URL |
| `feedback_context` | `FeedbackSchema \| None` | 否 | 上一轮辅导后的反馈，用作风格切换和画像更新输入 |

建议约束：

- `problem_text` 必须存在，否则不进入诊断主链路
- `student_answer` 对标准答案题是错因分析的必要输入；开放题可以没有学生答案，先生成引导型辅导卡片
- 标准答案题的 `reference_answer` 不由家长传入，而是由 LLM 在前置分析阶段生成
- `parent_goal` 为空时，默认按 `diagnose-and-coach` 处理

### DiagnoseResponse

| 字段 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| `request_id` | `str` | 是 | 回传请求 ID，便于链路追踪 |
| `session_id` | `str \| None` | 否 | 当前辅导会话 ID |
| `student_id` | `str` | 是 | 学生唯一标识 |
| `intent` | `str` | 是 | 系统判定的处理意图，如 `diagnose-and-coach` |
| `status` | `str` | 是 | 处理结果，如 `completed`、`need_clarification`、`degraded` |
| `confidence` | `str` | 是 | 结果置信度分档，如 `high`、`medium`、`low` |
| `diagnosis` | `str` | 是 | 面向家长的简要诊断结论 |
| `question_type` | `str` | 是 | 题目类型，只分 `standard-answer` 和 `open-ended` |
| `answer_analysis` | `AnswerAnalysisSchema \| None` | 否 | LLM 产出的题目前置分析，包括参考答案、解题概要或评分关注点 |
| `reference_answer_source` | `str \| None` | 否 | 参考答案来源，当前标准答案题固定为 `llm-derived` 或为空 |
| `error_type` | `str \| None` | 否 | 错因类型，如 `concept`、`process`、`calculation` |
| `knowledge_points` | `list[str]` | 是 | 本次诊断关联到的知识点 |
| `card` | `CardSchema` | 是 | 结构化辅导卡片 |
| `practice_suggestion` | `str` | 否 | 跟进练习建议的简要摘要 |
| `suggested_questions` | `list[str]` | 是 | 从卡片中提取给前端快速展示的关键追问 |
| `updated_mastery` | `dict[str, float]` | 否 | 更新后的知识点掌握度 |
| `next_action` | `str \| None` | 否 | 建议前端下一步动作，如 `ask_clarifying_question` |
| `clarifying_question` | `str \| None` | 否 | 当信息不足时，返回给家长的单个澄清问题 |

### CardSchema

| 字段 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| `card_title` | `str` | 是 | 卡片标题，如“先补通分，再回到异分母相加” |
| `diagnosis_summary` | `str` | 是 | 对本题问题的浓缩判断 |
| `likely_cause` | `str` | 是 | 更可能的原因，避免直接给孩子贴负面标签 |
| `coaching_steps` | `list[str]` | 是 | 家长可执行的讲解步骤，建议 2 到 4 步 |
| `suggested_questions` | `list[str]` | 是 | 建议家长先问孩子的问题 |
| `materials_needed` | `list[str]` | 否 | 推荐使用的道具或图示 |
| `do_not_say` | `list[str]` | 否 | 不建议家长直接说的话或做法 |
| `red_flags` | `list[str]` | 否 | 需要警惕的信号，如连续两次同类错误 |
| `fallback_plan` | `str` | 否 | 如果孩子仍不懂，下一步如何退回前置知识点 |
| `tone` | `str` | 否 | 建议语气，如 `encouraging`、`calm` |
| `style` | `str` | 否 | 讲解风格，如 `visual`、`hands-on`、`story` |

说明：

- `CardSchema` 是家长端真正要渲染的核心对象
- `suggested_questions` 在 `CardSchema` 与 `DiagnoseResponse` 中可重复保留，便于前端快速读取
- `fallback_plan` 是施工图纸里非常关键的保守回退节点，用于避免“一讲不懂就重复原话”

### FeedbackSchema

| 字段 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| `useful` | `bool` | 是 | 家长主观判断这轮建议是否有用 |
| `child_understood` | `bool \| None` | 否 | 孩子是否真正听懂 |
| `follow_up_needed` | `bool` | 否 | 是否需要继续追问或再生成一版卡片 |
| `selected_style` | `str \| None` | 否 | 本轮实际采用的讲解风格 |
| `most_useful_step` | `str \| None` | 否 | 哪一步最有效，用于后续风格强化 |
| `still_confusing_point` | `str \| None` | 否 | 孩子仍卡住的点 |
| `parent_note` | `str \| None` | 否 | 家长自由备注 |

说明：

- `FeedbackSchema` 既可作为下一轮 `DiagnoseRequest.feedback_context` 的输入，也可单独沉淀到反馈表
- `useful=false` 时，不应只改措辞，应该驱动风格切换或粒度调整

### 建议版 Pydantic 定义

```python
from pydantic import BaseModel, Field


class FeedbackSchema(BaseModel):
    useful: bool
    child_understood: bool | None = None
    follow_up_needed: bool = False
    selected_style: str | None = None
    most_useful_step: str | None = None
    still_confusing_point: str | None = None
    parent_note: str | None = None


class CardSchema(BaseModel):
    card_title: str
    diagnosis_summary: str
    likely_cause: str
    coaching_steps: list[str]
    suggested_questions: list[str]
    materials_needed: list[str] = Field(default_factory=list)
    do_not_say: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    fallback_plan: str | None = None
    tone: str | None = None
    style: str | None = None


  class AnswerAnalysisSchema(BaseModel):
    normalized_problem: str | None = None
    reference_answer: str | None = None
    solution_outline: list[str] = Field(default_factory=list)
    evaluation_focus: list[str] = Field(default_factory=list)
    summary: str
    confidence: float | None = None


class DiagnoseRequest(BaseModel):
    request_id: str | None = None
    session_id: str | None = None
    parent_id: str | None = None
    student_id: str
    subject: str
    grade: str | None = None
    textbook_version: str | None = None
    input_mode: str
    problem_text: str
    student_answer: str | None = None
    knowledge_points: list[str] = Field(default_factory=list)
    parent_goal: str = "diagnose-and-coach"
    parent_note: str | None = None
    attachments: list[str] = Field(default_factory=list)
    feedback_context: FeedbackSchema | None = None


class DiagnoseResponse(BaseModel):
    request_id: str
    session_id: str | None = None
    student_id: str
    intent: str
    status: str
    confidence: str
    diagnosis: str
    question_type: str
    answer_analysis: AnswerAnalysisSchema | None = None
    reference_answer_source: str | None = None
    error_type: str | None = None
    knowledge_points: list[str]
    card: CardSchema
    practice_suggestion: str | None = None
    suggested_questions: list[str] = Field(default_factory=list)
    updated_mastery: dict[str, float] = Field(default_factory=dict)
    next_action: str | None = None
    clarifying_question: str | None = None
```

### 诊断接口示例请求

```json
{
  "request_id": "req-001",
  "session_id": "sess-001",
  "parent_id": "par-001",
  "student_id": "stu-001",
  "subject": "math",
  "grade": "grade-4",
  "textbook_version": "pep",
  "input_mode": "photo",
  "problem_text": "1/2 + 1/3 = ?",
  "student_answer": "2/5",
  "knowledge_points": ["fraction-addition-unlike-denominator"],
  "parent_goal": "判断错因并告诉我怎么讲",
  "parent_note": "孩子做分数题时经常跳过通分",
  "attachments": ["image-upload-001"],
  "feedback_context": {
    "useful": false,
    "child_understood": false,
    "follow_up_needed": true,
    "selected_style": "visual",
    "still_confusing_point": "通分为什么要做",
    "parent_note": "上一轮画图还是没听懂"
  }
}
```

### 诊断接口示例响应

```json
{
  "request_id": "req-001",
  "session_id": "sess-001",
  "student_id": "stu-001",
  "intent": "diagnose-and-coach",
  "status": "completed",
  "confidence": "medium",
  "diagnosis": "更可能是异分母分数相加中的通分步骤不稳定，而不是单纯计算失误。",
  "question_type": "standard-answer",
  "answer_analysis": {
    "normalized_problem": "1/2 + 1/3 = ?",
    "reference_answer": "5/6",
    "solution_outline": [
      "先把二分之一和三分之一通分成六分之三和六分之二。",
      "再把同单位的分数相加，得到六分之五。"
    ],
    "evaluation_focus": [
      "答案是否正确",
      "是否先通分"
    ],
    "summary": "这题属于有标准答案的分数计算题，可以先用通分得到参考答案，再判断孩子是否在关键步骤上出错。",
    "confidence": 0.91
  },
  "reference_answer_source": "llm-derived",
  "error_type": "process",
  "knowledge_points": ["fraction-addition-unlike-denominator", "common-denominator"],
  "card": {
    "card_title": "先补通分，再回到异分母相加",
    "diagnosis_summary": "孩子可能知道要把分数相加，但还不稳定地理解为什么必须先通分。",
    "likely_cause": "更像是步骤理解不稳，而不是粗心。",
    "coaching_steps": [
      "先画两个同样大小的长条，一个分成 2 份，一个分成 3 份。",
      "引导孩子观察两种分法下每一份大小不同，所以不能直接相加。",
      "再把两个长条都改成 6 份，说明这时每一份的单位一致。"
    ],
    "suggested_questions": [
      "为什么二分之一和三分之一不能直接相加？",
      "如果都变成六分之一，原来每一份发生了什么变化？"
    ],
    "materials_needed": ["纸条", "彩笔"],
    "do_not_say": ["你怎么又算错了", "直接背公式就行"],
    "red_flags": ["同类题连续两次卡在通分步骤"],
    "fallback_plan": "如果还是不懂，先退回到同分母分数相加做一题，再回到当前题。",
    "tone": "encouraging",
    "style": "hands-on"
  },
  "practice_suggestion": "先做 1 题带提示的通分练习，再做 1 题独立完成的异分母分数相加。",
  "suggested_questions": [
    "为什么二分之一和三分之一不能直接相加？",
    "如果都变成六分之一，原来每一份发生了什么变化？"
  ],
  "updated_mastery": {
    "fraction-addition-unlike-denominator": 0.42,
    "common-denominator": 0.39
  },
  "next_action": "show_card_and_collect_feedback",
  "clarifying_question": null
}
```

### 内容能力现状

当前后端已经补上三块核心能力：

- 题目理解：对常见四则运算、分数加减和简单应用题做规则解析，自动补齐部分知识点标签
- 错因诊断：区分答对、步骤错误、计算错误、审题偏差、未作答等高频情况
- 讲解生成：默认输出中文家长辅导卡片，包含讲解步骤、关键追问和道具建议

当前标准答案题的参考答案来源也已经固定：

- 家长不需要提供标准答案
- 系统先通过 LLM 做题目前置分析
- 如果 LLM 产出 `reference_answer`，再进入错因分析
- 如果 LLM 没产出可靠参考答案，系统降级为保守辅导，不硬判对错

### 可选 LLM 增强

系统默认不依赖外部模型 API，未配置时会直接使用本地规则生成内容。

如果你希望在现有规则上增加更自然的辅导表达，可以在 [backend/.env.example](backend/.env.example) 对应的环境变量中配置：

- `LLM_ENABLED=true`
- `LLM_API_KEY=你的密钥`
- `LLM_BASE_URL=兼容 OpenAI chat completions 的接口地址`
- `LLM_MODEL=要调用的模型名`
- `LLM_TIMEOUT_SECONDS=超时时间`

当前接入方式是“可选增强”而不是“强依赖替换”：

- 调用成功时，用模型补强家长卡片文本、追问和讲解步骤
- 未配置或调用失败时，自动回退到本地规则，不影响接口可用性

但对于 `standard-answer` 题，模型还有一个额外职责：

- 在前置分析阶段尽量产出 `reference_answer`
- 只有拿到 `reference_answer` 后，系统才进入错因分析和画像驱动讲解
