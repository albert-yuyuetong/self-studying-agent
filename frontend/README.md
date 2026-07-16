# Parent Frontend MVP

这个目录现在包含一个移动端优先的家长端 Web MVP，核心路径是：

- 输入题目与孩子答案
- 调用 `POST /api/v1/diagnose`
- 展示题型判断、诊断结论、辅导卡片和练习建议

## 本地启动

在本目录执行：

```bash
npm install
npm run dev
```

默认会请求 `http://127.0.0.1:8000/api/v1/diagnose`。

如果后端地址不同，可在启动前设置环境变量：

```bash
set VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 页面说明

- 手机端优先布局
- 支持标准答案题与开放题两类结果展示
- 支持展示结构化辅导卡片、追问、练习建议和画像更新结果
