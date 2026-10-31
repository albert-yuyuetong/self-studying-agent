# Self-Studying Agent

一个利用学习画像组织讲解的通用家教 Agent。面向家长辅导，也支持与学习者一起逐步理解题目。

它不按“口算 / 作文 / 阅读”等预设题型路由。模型从题目、图片、完整作答和会话上下文中描述当前任务、学习目标、所需技能和证据，再结合画像生成具体讲解。是否适合某道陌生题，取决于材料完整程度和所配置模型的能力；输入开放不代表所有学科的答案都能被保证正确。

## 一轮辅导如何工作

1. **理解任务**：读取完整题目、材料、学生作答、画像及近期对话，识别任务要求、缺失材料、学习目标和作答证据。
2. **选择策略**：使用家长明确设置的偏好、学习节奏、目标、兴趣和已有观察，说明本轮为什么这样讲。用户本轮的讲法要求优先。
3. **生成讲解**：返回渐进步骤、每步追问和检查点、家长建议、理解检查，以及有完整题干的迁移练习。
4. **独立复核**：另一轮模型调用检查参考解、学生评估、讲解和练习是否依据充分。发现具体问题时最多修订一次并再次复核，仍不通过则拦截。可配置另一个模型复核。
5. **记录与反馈**：只记录有明确作答来源、通过复核且达到置信度门槛的技能观察。反馈回到下一轮上下文。

题目不完整时返回澄清问题。模型未配置、调用失败、结构无效或复核不通过时，返回明确的降级状态，不用固定模板伪装成已完成的辅导。

## 画像与会话

- 可编辑：称呼、年级、教材、学习目标、语言、表达偏好、兴趣、节奏、补充说明。
- 可追溯：每个技能的“展示理解 / 需要支持”观察次数、最近证据及时间。
- 可校准：讲法是否有用、孩子是否理解、仍困惑的具体内容。
- 不把“喜欢图示”当作永久认知类型，不把“讲解有用”当成掌握知识。
- 不再根据一次对错输出未经校准的掌握概率。
- 相同请求返回原结果；同会话的同一份作答重新讲解不重复计入学习记录。
- SQLite 事务持久化画像、会话、反馈和去重记录。保存画像表单不会覆盖学习观察。

## 运行

需要 Python 3.12+ 与 Node.js 18+。以下命令在项目根目录执行。

### 后端

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
```

编辑 `backend/.env`：

```dotenv
LLM_ENABLED=true
LLM_BASE_URL=https://your-provider.example/v1
LLM_API_KEY=your-api-key
LLM_MODEL=your-model-name
LLM_VERIFY_MODEL=
LLM_VISION_ENABLED=false
LLM_TIMEOUT_SECONDS=90
```

- 服务须支持 Chat Completions、JSON 对象输出；输出内容按 Pydantic Schema 严格校验。
- 图片题需要配置支持图片输入的模型，并启用 `LLM_VISION_ENABLED=true`。若使用单独复核模型，它也需要能读图。
- `LLM_VERIFY_MODEL` 留空时用同一个模型发起独立复核调用。这不能排除同一模型重复犯错。
- 一个完成的辅导通常包含三次模型调用；有具体复核问题时，一次内容修订与再次复核会增加两次调用。结构修复最多为每次调用增加一次请求。
- 默认数据库在 `backend/data/tutor.sqlite3`，可通过 `DATABASE_PATH` 指定。
- `.env` 自动加载，不会覆盖已设置的进程环境变量。密钥只在后端使用。

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

API 文档：[本地 Swagger](http://127.0.0.1:8000/docs)。

### 前端

```powershell
cd frontend
npm install
npm run dev
```

打开 [本地前端](http://127.0.0.1:5173)。可在 `frontend/.env` 中设置 `VITE_API_BASE_URL`，默认后端为 `http://127.0.0.1:8000`。

使用方式：设置学习画像 → 输入任意学科题目或上传图片 → 可选粘贴完整作答 → 查看讲解及策略依据 → 继续追问或提交练习 → 反馈效果。参考解默认折叠。

## API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/health` | 服务状态及模型是否配置 |
| GET / PUT | `/api/v1/profiles/{student_id}` | 读取 / 保存基本画像 |
| POST | `/api/v1/tutor` | 开始辅导或继续当前会话 |
| POST | `/api/v1/feedback` | 对一轮有效讲解提交反馈 |
| GET | `/api/v1/sessions/{session_id}?student_id=...` | 读取会话结果 |
| POST | `/api/v1/diagnose` | 兼容旧 URL，使用新请求与响应契约 |

`/diagnose` 不再返回旧的固定题型卡片。旧客户端需要迁移至新响应结构；旧规则模块和 BKT 更新已移除。

请求示例：

```json
{
  "request_id": "request-001",
  "student_id": "learner-001",
  "subject": "实验设计",
  "problem_text": "设计实验比较两种肥料对幼苗生长的影响，说明变量和测量方法。",
  "student_answer": "把两组幼苗放到不同窗台，再分别施两种肥料。",
  "parent_goal": "帮助孩子自己发现实验设计中的问题"
}
```

保留返回的 `session_id` 继续追问，使用新的 `request_id`；原题图片应随每轮保留发送。网络重试使用同一请求 ID 与同一请求体。练习作答使用练习自己的完整题干开始新会话。画像和会话接口的字段定义见 Swagger 和 `backend/app/schemas/`。

普通追问通过 `follow_up` 提交，`student_answer` 留空。回答讲解中的理解检查时，同时提交 `answer_to`（检查问题原文）与 `student_answer`（这次的新回答）；系统只评估对应检查，不因未重新作答整道原题而判错。页面提供独立的“回答这个问题”入口。

## 验证

```powershell
cd backend
..\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
cd ../frontend
npm run build
```

自动化测试覆盖输入传递、动态学科任务、空答案、缺失材料、严格模型输出校验、复核拦截、作答去重、并发持久化、反馈与会话归属。测试用受控模型替身验证软件行为，不能代替真实模型的学科质量评测。人工评测流程见 [evaluation/README.md](evaluation/README.md)。

已使用项目配置的真实模型完成跨学科、同题不同画像、反馈续问和错误内容修订评测，结果与限制见 [真实模型实测报告](evaluation/live_model_report.md)。

## 当前范围

这是本地单机应用，默认只监听回环地址。学生 ID 是本机档案选择标识，**不是身份认证**；虽然会话会检查学生归属，尚未提供家庭账号认证、多租户授权或公网部署方案。数据库保存题干、作答和反馈文本，未实现静态加密或自动删除；不要把这版服务直接暴露到公网。

图片原始数据不写入 SQLite，会话保存图片引用的指纹和模型识别结果。系统尚未接入教材检索、外部计算验证器、代码执行沙箱或权威知识库，因此“内容复核”属于模型复核，教材字段是指导约束而非教材一致性认证。

代码结构与状态规则见 [docs/architecture.md](docs/architecture.md)。

