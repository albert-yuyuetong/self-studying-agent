import React, { useState } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

const starterExamples = {
  standard: {
    subject: 'math',
    problem_text: '1/2 + 1/3 = ?',
    student_answer: '2/5',
    parent_note: '孩子做分数题时经常跳过通分。',
  },
  open: {
    subject: 'chinese',
    problem_text: '请结合文章内容谈谈你对主人公做法的看法。',
    student_answer: '我觉得主人公很勇敢，因为他在困难面前没有退缩。',
    parent_note: '我更想知道怎么追问，帮孩子把依据说完整。',
  },
}

const initialForm = {
  student_id: 'stu-001',
  subject: 'math',
  grade: 'grade-4',
  input_mode: 'text',
  problem_text: '',
  student_answer: '',
  parent_note: '',
}

function App() {
  const [form, setForm] = useState(initialForm)
  const [result, setResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function fillExample(kind) {
    setForm((current) => ({
      ...current,
      ...starterExamples[kind],
    }))
    setResult(null)
    setError('')
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setIsLoading(true)
    setError('')
    setResult(null)

    const payload = {
      ...form,
      problem_text: form.problem_text.trim(),
      student_answer: form.student_answer.trim() || null,
      parent_note: form.parent_note.trim() || null,
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/diagnose`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail?.[0]?.msg || '请求失败，请检查后端是否启动。')
      }

      setResult(data)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : '请求失败，请稍后重试。')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="shell">
      <div className="backdrop backdrop-left" />
      <div className="backdrop backdrop-right" />

      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">家长端辅导 MVP</p>
          <h1>先判断题型，再给家长一张真正能用的辅导卡片</h1>
          <p className="hero-text">
            这不是答案机。它会先判断题目是标准答案题还是开放题，再决定是做错因分析，还是直接输出引导型辅导卡片。
          </p>
        </div>

        <div className="hero-panel">
          <span className="hero-chip">手机端优先</span>
          <span className="hero-chip">结构化卡片</span>
          <span className="hero-chip">支持开放题</span>
        </div>
      </header>

      <main className="layout">
        <section className="panel panel-form">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">输入题目</p>
              <h2>家长发来一题，系统返回一张辅导卡片</h2>
            </div>
            <div className="quick-fill">
              <button type="button" className="ghost-button" onClick={() => fillExample('standard')}>
                填充标准题
              </button>
              <button type="button" className="ghost-button" onClick={() => fillExample('open')}>
                填充开放题
              </button>
            </div>
          </div>

          <form className="form-grid" onSubmit={handleSubmit}>
            <label className="field field-half">
              <span>学生 ID</span>
              <input
                value={form.student_id}
                onChange={(event) => updateField('student_id', event.target.value)}
                placeholder="例如 stu-001"
              />
            </label>

            <label className="field field-half">
              <span>学科</span>
              <select value={form.subject} onChange={(event) => updateField('subject', event.target.value)}>
                <option value="math">数学</option>
                <option value="chinese">语文</option>
                <option value="english">英语</option>
              </select>
            </label>

            <label className="field field-half">
              <span>年级</span>
              <input
                value={form.grade}
                onChange={(event) => updateField('grade', event.target.value)}
                placeholder="例如 grade-4"
              />
            </label>

            <label className="field field-half">
              <span>输入方式</span>
              <select value={form.input_mode} onChange={(event) => updateField('input_mode', event.target.value)}>
                <option value="text">文本</option>
                <option value="photo">图片识别后补文字</option>
                <option value="mixed">混合输入</option>
              </select>
            </label>

            <label className="field field-full">
              <span>题目内容</span>
              <textarea
                rows="5"
                value={form.problem_text}
                onChange={(event) => updateField('problem_text', event.target.value)}
                placeholder="把题目文字粘贴在这里。标准答案题和开放题都可以。"
              />
            </label>

            <label className="field field-full">
              <span>孩子当前回答</span>
              <textarea
                rows="4"
                value={form.student_answer}
                onChange={(event) => updateField('student_answer', event.target.value)}
                placeholder="如果孩子已经回答或作答，把内容贴在这里。"
              />
            </label>

            <label className="field field-full">
              <span>家长补充说明</span>
              <textarea
                rows="3"
                value={form.parent_note}
                onChange={(event) => updateField('parent_note', event.target.value)}
                placeholder="例如：孩子总说不清理由、分数题总跳步、作文内容空。"
              />
            </label>

            <div className="submit-row">
              <button type="submit" className="primary-button" disabled={isLoading}>
                {isLoading ? '正在生成辅导卡片...' : '生成辅导卡片'}
              </button>
              <p className="submit-hint">默认请求 {API_BASE_URL}/api/v1/diagnose</p>
            </div>
          </form>

          {error ? <div className="inline-alert">{error}</div> : null}
        </section>

        <section className="panel panel-result">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">诊断结果</p>
              <h2>家长看到的不是答案，而是下一步怎么辅导</h2>
            </div>
          </div>

          {!result ? (
            <div className="empty-state">
              <p>提交题目后，这里会显示题型判断、参考解析、辅导卡片、追问和练习建议。</p>
            </div>
          ) : (
            <div className="result-stack">
              <section className="result-topline">
                <span className={`badge badge-${result.status}`}>{result.status}</span>
                <span className="badge badge-soft">{result.question_type}</span>
                <span className="badge badge-soft">置信度 {result.confidence}</span>
              </section>

              <section className="card-block accent-block">
                <p className="block-label">诊断判断</p>
                <h3>{result.card?.card_title || '辅导卡片'}</h3>
                <p className="diagnosis-text">{result.diagnosis}</p>
                <p className="cause-text">{result.card?.likely_cause}</p>
              </section>

              {result.answer_analysis ? (
                <section className="card-block">
                  <p className="block-label">前置分析</p>
                  <div className="meta-grid">
                    <div>
                      <span className="meta-label">题型</span>
                      <strong>{result.question_type}</strong>
                    </div>
                    <div>
                      <span className="meta-label">参考答案来源</span>
                      <strong>{result.reference_answer_source || '无'}</strong>
                    </div>
                  </div>
                  <p className="analysis-summary">{result.answer_analysis.summary}</p>
                  {result.answer_analysis.reference_answer ? (
                    <div className="highlight-inline">
                      <span className="meta-label">LLM 参考答案</span>
                      <strong>{result.answer_analysis.reference_answer}</strong>
                    </div>
                  ) : null}
                  {result.answer_analysis.solution_outline?.length ? (
                    <div>
                      <p className="mini-title">解析步骤</p>
                      <ul className="bullet-list">
                        {result.answer_analysis.solution_outline.map((step) => (
                          <li key={step}>{step}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </section>
              ) : null}

              <section className="card-block">
                <p className="block-label">家长怎么讲</p>
                <ul className="step-list">
                  {result.card?.coaching_steps?.map((step, index) => (
                    <li key={`${index}-${step}`}>
                      <span className="step-index">{index + 1}</span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ul>
              </section>

              <section className="card-columns">
                <div className="card-block compact-block">
                  <p className="block-label">建议追问</p>
                  <ul className="bullet-list">
                    {result.suggested_questions?.map((question) => (
                      <li key={question}>{question}</li>
                    ))}
                  </ul>
                </div>

                <div className="card-block compact-block">
                  <p className="block-label">道具与提醒</p>
                  <ul className="bullet-list">
                    {(result.card?.materials_needed?.length
                      ? result.card.materials_needed
                      : ['当前不需要额外道具']).map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                  {result.card?.fallback_plan ? <p className="fallback-note">{result.card.fallback_plan}</p> : null}
                </div>
              </section>

              {result.practice_suggestion ? (
                <section className="card-block">
                  <p className="block-label">跟进练习</p>
                  <p>{result.practice_suggestion}</p>
                </section>
              ) : null}

              {result.updated_mastery && Object.keys(result.updated_mastery).length ? (
                <section className="card-block">
                  <p className="block-label">画像更新</p>
                  <div className="mastery-grid">
                    {Object.entries(result.updated_mastery).map(([key, value]) => (
                      <div key={key} className="mastery-item">
                        <span>{key}</span>
                        <strong>{Number(value).toFixed(2)}</strong>
                      </div>
                    ))}
                  </div>
                </section>
              ) : null}

              {result.clarifying_question ? (
                <section className="card-block warning-block">
                  <p className="block-label">需要补充</p>
                  <p>{result.clarifying_question}</p>
                </section>
              ) : null}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

export default App