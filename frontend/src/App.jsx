import React, { useEffect, useRef, useState } from 'react'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const newId = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`
const splitList = (value) => value.split(/[,，、\n]/).map((item) => item.trim()).filter(Boolean)
const emptyForm = () => ({ subject: '', problem_text: '', student_answer: '', parent_goal: '', parent_note: '' })
const defaultProfile = () => ({ display_name: '', grade: '', textbook: '', learning_goal: '', language: '中文', preferred_explanation_modes: [], interests: [], pace: 'balanced', notes: '', skills: {} })
const profileDraft = (profile) => ({ ...defaultProfile(), ...profile, preferred_explanation_modes: (profile.preferred_explanation_modes || []).join('，'), interests: (profile.interests || []).join('，') })
const profilePayload = (draft) => ({ display_name: draft.display_name, grade: draft.grade, textbook: draft.textbook, learning_goal: draft.learning_goal, language: draft.language, preferred_explanation_modes: splitList(draft.preferred_explanation_modes), interests: splitList(draft.interests), pace: draft.pace, notes: draft.notes })
const statusLabels = { completed: '讲解已就绪', need_clarification: '需要补充信息', degraded: '暂时无法可靠讲解' }
const verdictLabels = { 'not-submitted': '先探索思路', supported: '已有依据支持', 'partially-supported': '部分内容有依据', 'needs-revision': '有待修正', uncertain: '暂无法判断' }
const profileLabels = { display_name: '称呼', grade: '学习阶段', textbook: '教材与课程', learning_goal: '学习目标', language: '讲解语言', preferred_explanation_modes: '讲解偏好', interests: '兴趣', pace: '讲解节奏', notes: '学习背景', skills: '学习观察', format_feedback: '之前的讲解反馈' }
const examples = [
  { label: '物理 · 实验设计', subject: '物理', problem_text: '小明想研究摆球质量是否影响单摆周期。现有细线、不同质量的摆球、铁架台、刻度尺和秒表。请设计实验，说明控制变量、测量方法，以及如何减少误差。', student_answer: '我会换三个不同质量的球，各摆一次，用秒表测时间，然后比较。', parent_goal: '帮我理解怎样把一个想法变成可靠的实验。', parent_note: '' },
  { label: '历史 · 材料论证', subject: '历史', problem_text: '阅读材料：“铁路的修建缩短了货物流通时间，沿线城镇逐渐兴起；部分传统驿站和运输行业则衰落。”请结合材料，从不同群体的角度评价铁路发展带来的影响，并说明这段材料还不能证明什么。', student_answer: '铁路使社会进步，所以所有人都受益了。', parent_goal: '练习用材料支持观点，也能看见材料的局限。', parent_note: '' },
  { label: '编程 · 排查问题', subject: '编程', problem_text: '下面的 Python 函数应删除列表中的所有负数，但运行后仍留下一些负数。请解释原因并修复，说明修复后怎样测试。\n\ndef remove_negatives(values):\n    for value in values:\n        if value < 0:\n            values.remove(value)\n    return values\n\n输入：[-1, -2, 3, -4, -5]', student_answer: '', parent_goal: '引导我自己定位问题，再想出验证方法。', parent_note: '' },
]

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...options.headers } })
  let data
  try { data = await response.json() } catch { throw new Error('服务返回了无法读取的内容，请稍后重试。') }
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : Array.isArray(data.detail) ? data.detail.map((item) => item.msg).join('；') : data.detail?.message
    throw new Error(detail || `请求失败（${response.status}），请稍后重试。`)
  }
  return data
}

function TextList({ items, className = '' }) {
  if (!items?.length) return null
  return <ul className={`text-list ${className}`}>{items.map((item, index) => <li key={index}>{item}</li>)}</ul>
}

function App() {
  const [studentId, setStudentId] = useState('stu-001')
  const [studentInput, setStudentInput] = useState('stu-001')
  const [profile, setProfile] = useState(null)
  const [draft, setDraft] = useState(() => profileDraft(defaultProfile()))
  const [profileLoading, setProfileLoading] = useState(true)
  const [profileError, setProfileError] = useState('')
  const [profileMessage, setProfileMessage] = useState('')
  const [profileReload, setProfileReload] = useState(0)
  const [form, setForm] = useState(emptyForm)
  const [attachments, setAttachments] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [turns, setTurns] = useState([])
  const [followUp, setFollowUp] = useState('')
  const [selectedCheck, setSelectedCheck] = useState(null)
  const [strategy, setStrategy] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [health, setHealth] = useState('checking')
  const [feedback, setFeedback] = useState({ useful: null, child_understood: '', comment: '' })
  const [feedbackMessage, setFeedbackMessage] = useState('')
  const [feedbackSent, setFeedbackSent] = useState(false)
  const [practiceAnswers, setPracticeAnswers] = useState({})
  const requestRef = useRef(null)
  const feedbackRef = useRef(null)
  const submittedFeedbackRef = useRef(new Map())
  const attemptRef = useRef(null)
  const checkAttemptRef = useRef(null)
  const retryModeRef = useRef(false)
  const epochRef = useRef(0)
  const studentRef = useRef(studentId)
  const resultRef = useRef(null)
  const problemRef = useRef(null)
  const operationRef = useRef(false)
  const result = turns.at(-1)?.result || null
  const verificationIssues = result?.verification?.issues || []
  const uniqueWarnings = [...new Set(result?.warnings || [])].filter((message) => !verificationIssues.includes(message))
  const locked = Boolean(busy) || profileLoading
  const dirty = profile && JSON.stringify(profilePayload(draft)) !== JSON.stringify(profilePayload(profileDraft(profile)))

  useEffect(() => {
    const controller = new AbortController()
    api('/api/v1/health', { signal: controller.signal }).then((data) => setHealth(data.model_configured ? 'ready' : 'unconfigured')).catch((err) => { if (err.name !== 'AbortError') setHealth('offline') })
    return () => controller.abort()
  }, [profileReload])

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setProfileLoading(true)
    setProfileError('')
    api(`/api/v1/profiles/${encodeURIComponent(studentId)}`, { signal: controller.signal }).then((data) => {
      if (!active) return
      setProfile(data)
      setDraft(profileDraft(data))
    }).catch((err) => { if (active && err.name !== 'AbortError') setProfileError(`画像加载失败：${err.message}`) }).finally(() => { if (active) setProfileLoading(false) })
    return () => { active = false; controller.abort() }
  }, [studentId, profileReload])

  function resetConversation() {
    epochRef.current += 1
    requestRef.current = null
    attemptRef.current = null
    checkAttemptRef.current = null
    retryModeRef.current = false
    feedbackRef.current = null
    submittedFeedbackRef.current.clear()
    setSessionId(null)
    setTurns([])
    setFollowUp('')
    setSelectedCheck(null)
    setStrategy('')
    setError('')
    setFeedback({ useful: null, child_understood: '', comment: '' })
    setFeedbackMessage('')
    setFeedbackSent(false)
    setPracticeAnswers({})
  }

  function startNewProblem(example) {
    if (locked) return
    resetConversation()
    setAttachments([])
    setForm(example ? { ...emptyForm(), ...example } : emptyForm())
    problemRef.current?.focus()
  }

  function switchStudent(event) {
    event.preventDefault()
    const next = studentInput.trim()
    if (!next || locked || next === studentId) return
    studentRef.current = next
    resetConversation()
    setForm(emptyForm())
    setAttachments([])
    setProfile(null)
    setProfileMessage('')
    setProfileLoading(true)
    setStudentId(next)
  }

  function updateForm(field, value) {
    requestRef.current = null
    if (field === 'problem_text' || field === 'subject') resetConversation()
    if (field === 'student_answer') attemptRef.current = null
    setForm((current) => ({ ...current, [field]: value }))
    setError('')
  }

  function updateDraft(field, value) {
    setDraft((current) => ({ ...current, [field]: value }))
    setProfileMessage('')
    requestRef.current = null
  }

  async function persistProfile() {
    const selected = studentId
    const payload = profilePayload(draft)
    if (payload.preferred_explanation_modes.length > 8) throw new Error('讲解偏好最多填写 8 项，请合并相近的偏好。')
    if (payload.interests.length > 12) throw new Error('兴趣最多填写 12 项，请保留最相关的内容。')
    const data = await api(`/api/v1/profiles/${encodeURIComponent(selected)}`, { method: 'PUT', body: JSON.stringify(payload) })
    if (studentRef.current === selected) {
      setProfile(data)
      setDraft(profileDraft(data))
      setProfileMessage('画像已保存，本次讲解会使用这些信息。')
      setProfileError('')
    }
    return data
  }

  async function saveProfile(event) {
    event.preventDefault()
    if (operationRef.current || locked) return
    operationRef.current = true
    setBusy('profile')
    setProfileError('')
    try { await persistProfile() } catch (err) { setProfileError(err.message) } finally { operationRef.current = false; setBusy('') }
  }

  async function addImages(event) {
    const files = Array.from(event.target.files || [])
    event.target.value = ''
    if (!files.length || locked || operationRef.current) return
    if (attachments.length + files.length > 4) { setError('每道题最多添加 4 张图片。'); return }
    if (files.some((file) => !['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024)) {
      setError('请使用 PNG、JPG 或 WebP 图片，每张不超过 5 MB。'); return
    }
    operationRef.current = true
    setBusy('images')
    try {
      const images = await Promise.all(files.map((file) => new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve({ id: newId(), name: file.name, url: reader.result })
        reader.onerror = () => reject(new Error('图片读取失败，请重新选择。'))
        reader.readAsDataURL(file)
      })))
      resetConversation()
      setAttachments((current) => [...current, ...images])
    } catch (err) { setError(err.message) } finally { operationRef.current = false; setBusy('') }
  }

  async function submitTutor(event, isFollowUp = false) {
    event.preventDefault()
    if (operationRef.current || locked || !profile) return
    if (!form.problem_text.trim() && !attachments.length) { setError('请写下题目，或添加清晰的题目图片。'); return }
    if (isFollowUp && !followUp.trim() && !strategy.trim()) { setError('请写下新的问题、补充内容，或希望调整的讲法。'); return }
    if (isFollowUp && selectedCheck && !followUp.trim()) { setError('请写下对当前理解检查的回答。'); return }
    const selected = studentId
    const epoch = epochRef.current
    operationRef.current = true
    setBusy('tutor')
    setError('')
    try {
      if (dirty) await persistProfile()
      const answer = isFollowUp ? selectedCheck ? followUp.trim() || null : null : form.student_answer.trim() || null
      let attemptId = null
      if (answer && isFollowUp) {
        const signature = JSON.stringify([selectedCheck, answer])
        if (checkAttemptRef.current?.signature !== signature) checkAttemptRef.current = { signature, id: newId() }
        attemptId = checkAttemptRef.current.id
      } else if (answer) {
        if (!attemptRef.current) attemptRef.current = newId()
        attemptId = attemptRef.current
      }
      const payload = {
        student_id: selected, session_id: sessionId, subject: form.subject.trim() || 'auto', problem_text: form.problem_text.trim(),
        student_answer: answer, answer_to: isFollowUp ? selectedCheck : null, parent_goal: form.parent_goal.trim(), parent_note: form.parent_note.trim(),
        attachments: attachments.map((item) => item.url), follow_up: isFollowUp && !selectedCheck ? followUp.trim() || null : null,
        requested_strategy: isFollowUp ? strategy.trim() || null : null, attempt_id: attemptId,
      }
      const signature = JSON.stringify(payload)
      if (requestRef.current?.signature !== signature) requestRef.current = { signature, id: newId() }
      retryModeRef.current = isFollowUp
      const data = await api('/api/v1/tutor', { method: 'POST', body: JSON.stringify({ ...payload, request_id: requestRef.current.id }) })
      if (studentRef.current !== selected || epochRef.current !== epoch) return
      if (data.status !== 'degraded') setSessionId(data.session_id)
      setTurns((current) => {
        if (current.some((item) => item.result.turn_id === data.turn_id)) return current
        const previous = current.at(-1)?.result.status === 'degraded' ? current.slice(0, -1) : current
        const question = isFollowUp ? selectedCheck ? `回答「${selectedCheck}」：${followUp.trim()}` : followUp.trim() || strategy.trim() : answer ? '根据我的作答开始讲解' : '一起探索这道题'
        return [...previous, { question, result: data }]
      })
      if (data.profile && data.turn_id !== result?.turn_id) { setProfile(data.profile); setDraft(profileDraft(data.profile)) }
      if (data.status !== 'degraded') {
        setFollowUp('')
        setSelectedCheck(null)
        setStrategy('')
        checkAttemptRef.current = null
      }
      if (data.turn_id !== result?.turn_id) {
        const savedFeedback = submittedFeedbackRef.current.get(data.turn_id)
        setFeedback(savedFeedback || { useful: null, child_understood: '', comment: '' })
        setFeedbackSent(Boolean(savedFeedback))
        setFeedbackMessage(savedFeedback ? '反馈已记录，会用于调整后续讲解。' : '')
        feedbackRef.current = null
        setPracticeAnswers({})
      }
      if (data.status === 'completed') setHealth('ready')
      resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    } catch (err) { if (studentRef.current === selected && epochRef.current === epoch) setError(err.message || '连接失败，请检查服务后重试。') }
    finally { operationRef.current = false; setBusy('') }
  }

  async function submitFeedback(event) {
    event.preventDefault()
    if (operationRef.current || locked || feedback.useful === null || result?.status !== 'completed' || !result.lesson || !result.strategy || feedbackSent) return
    operationRef.current = true
    setBusy('feedback')
    setFeedbackMessage('')
    const selected = studentId
    const epoch = epochRef.current
    const payload = { student_id: selected, session_id: sessionId, turn_id: result.turn_id, useful: feedback.useful, child_understood: feedback.child_understood === '' ? null : feedback.child_understood === 'yes', comment: feedback.comment.trim() }
    const signature = JSON.stringify(payload)
    if (feedbackRef.current?.signature !== signature) feedbackRef.current = { signature, id: newId() }
    try {
      const data = await api('/api/v1/feedback', { method: 'POST', body: JSON.stringify({ ...payload, feedback_id: feedbackRef.current.id }) })
      if (studentRef.current !== selected || epochRef.current !== epoch) return
      if (data.profile) { setProfile(data.profile); if (!dirty) setDraft(profileDraft(data.profile)) }
      submittedFeedbackRef.current.set(result.turn_id, { ...feedback })
      setFeedbackSent(true)
      setFeedbackMessage('反馈已记录，会用于调整后续讲解。')
    } catch (err) { setFeedbackMessage(`反馈未保存：${err.message}`) } finally { operationRef.current = false; setBusy('') }
  }

  function usePractice(practice) {
    const answer = practiceAnswers[practice.id] || ''
    const subject = result?.analysis?.subject || form.subject
    startNewProblem({ subject, problem_text: practice.prompt, student_answer: answer, parent_goal: practice.purpose || '检验能否独立应用刚才学到的思路。', parent_note: '' })
  }

  function answerCheck(question) {
    if (locked) return
    if (question.length > 4000) { setError('这个检查问题太长，请在下方追问中要求将问题拆小后再作答。'); return }
    requestRef.current = null
    checkAttemptRef.current = null
    setSelectedCheck(question)
    setFollowUp('')
    document.getElementById('follow-up')?.focus()
  }

  function cancelCheck() {
    requestRef.current = null
    checkAttemptRef.current = null
    setSelectedCheck(null)
    setFollowUp('')
    document.getElementById('follow-up')?.focus()
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#"><span className="brand-icon" aria-hidden="true">知</span><span>知伴 <small>学习，从理解开始</small></span></a>
        <span className={`connection ${health}`}><span aria-hidden="true" />{health === 'ready' ? '家教已连接' : health === 'unconfigured' ? '等待配置模型' : health === 'offline' ? '服务暂未连接' : '正在连接'}</span>
      </header>
      <section className="intro"><p className="eyebrow">你的题目，你的学习方式</p><h1>让讲解，跟得上你的思路。</h1><p>带来一道题、一段材料，或一个还没想明白的问题。结合你的学习背景，一步一步理解，再试着独立解决。</p></section>
      {health === 'unconfigured' && <div className="notice page-notice">当前还未连接讲解模型。你可以先保存学习画像、准备题目；模型配置完成后再开始讲解。</div>}
      {health === 'offline' && <div className="notice page-notice">暂时无法连接家教服务。请确认后端已启动，然后重试加载画像。</div>}

      <main className="workspace">
        <aside className="profile-column">
          <section className="panel profile-panel">
            <div className="section-heading"><div><p className="eyebrow">01 / 认识你</p><h2>学习画像</h2></div><span className="avatar" aria-hidden="true">{(profile?.display_name || '你').slice(0, 1)}</span></div>
            <form className="student-switch" onSubmit={switchStudent}><label className="field"><span>学生编号</span><input aria-label="学生编号" maxLength={100} value={studentInput} onChange={(e) => setStudentInput(e.target.value)} disabled={locked} placeholder="例如 stu-001" /></label><button className="button button-quiet" type="submit" disabled={locked || !studentInput.trim() || studentInput.trim() === studentId}>切换</button></form>
            <p className="hint">当前：{profile?.display_name || studentId}。每个学生独立记录学习证据。</p>
            {profileLoading && <p className="muted" role="status">正在读取画像…</p>}
            {profileError && <div className="notice" role="alert">{profileError}{!profile && <button className="text-button" onClick={() => setProfileReload((current) => current + 1)} disabled={locked}>重新加载</button>}</div>}
            <form onSubmit={saveProfile}><fieldset disabled={locked || !profile} className="profile-fields">
              <div className="field-pair"><label className="field"><span>怎么称呼你</span><input maxLength={80} value={draft.display_name} onChange={(e) => updateDraft('display_name', e.target.value)} placeholder="名字或昵称" /></label><label className="field"><span>年级 / 学习阶段</span><input maxLength={80} value={draft.grade} onChange={(e) => updateDraft('grade', e.target.value)} placeholder="初二 / 大学 / 自学" /></label></div>
              <label className="field"><span>当前学习目标</span><textarea rows={2} maxLength={1000} value={draft.learning_goal} onChange={(e) => updateDraft('learning_goal', e.target.value)} placeholder="例如：能自己说明推理依据" /></label>
              <label className="field"><span>喜欢怎样讲</span><input maxLength={500} value={draft.preferred_explanation_modes} onChange={(e) => updateDraft('preferred_explanation_modes', e.target.value)} placeholder="先举例，边提问边讲，图示…" /><small>可自由描述，多项用逗号分隔。</small></label>
              <label className="field"><span>讲解节奏</span><select value={draft.pace} onChange={(e) => updateDraft('pace', e.target.value)}><option value="step-by-step">慢一些，每步确认</option><option value="balanced">适中，重点展开</option><option value="fast">快一些，直接切入重点</option></select></label>
              <details className="profile-details"><summary>更多背景与偏好</summary><div className="details-body">
                <label className="field"><span>教材 / 课程</span><input maxLength={200} value={draft.textbook} onChange={(e) => updateDraft('textbook', e.target.value)} placeholder="版本、课程或正在读的书" /></label>
                <label className="field"><span>兴趣</span><input maxLength={500} value={draft.interests} onChange={(e) => updateDraft('interests', e.target.value)} placeholder="篮球，音乐，机器人…" /></label>
                <label className="field"><span>讲解语言</span><input maxLength={80} value={draft.language} onChange={(e) => updateDraft('language', e.target.value)} placeholder="中文" /></label>
                <label className="field"><span>其他学习背景</span><textarea rows={3} maxLength={2000} value={draft.notes} onChange={(e) => updateDraft('notes', e.target.value)} placeholder="已学过的内容、需要的支持或家长观察" /></label>
              </div></details>
              <button className="button button-secondary full-width" type="submit" disabled={!dirty}>{busy === 'profile' ? '正在保存…' : dirty ? '保存学习画像' : '画像已保存'}</button>
            </fieldset></form>
            {profileMessage && <p className="success-text" role="status">{profileMessage}</p>}
          </section>
          <section className="panel evidence-panel"><p className="eyebrow">在学习中认识你</p><h2>已观察到的学习证据</h2><p className="hint">记录具体作答中的表现，作为调整讲解的参考。</p>
            {Object.keys(profile?.skills || {}).length ? <div className="evidence-list">{Object.entries(profile.skills).map(([id, skill]) => <details key={id} className="evidence-item"><summary><span>{skill.name || id}<small>{skill.subject}</small></span><span className="evidence-count">展现 {skill.demonstrated_count || 0} · 待支持 {skill.needs_support_count || 0}</span></summary><p className="prose">{skill.last_evidence || '暂无具体记录'}</p>{skill.last_seen && <p className="hint">最近记录：{new Date(skill.last_seen).toLocaleString('zh-CN')}</p>}</details>)}</div> : <div className="quiet-empty">还没有作答证据。完成讲解与练习后，可靠的观察会记录在这里。</div>}
          </section>
        </aside>

        <div className="learning-column">
          <section className="panel question-panel">
            <div className="section-heading"><div><p className="eyebrow">02 / 带来一个问题</p><h2>{sessionId ? '当前正在学习的题目' : '今天，想弄明白什么？'}</h2></div><button className="button button-quiet" type="button" disabled={locked} onClick={() => startNewProblem()}>＋ 开始新题</button></div>
            <div className="example-row"><span>试一试</span>{examples.map((example) => <button key={example.label} type="button" disabled={locked} onClick={() => startNewProblem(example)}>{example.label}</button>)}</div>
            <form onSubmit={(event) => submitTutor(event)}><fieldset disabled={locked || !profile} className="question-fields">
              <label className="field"><span>题目 / 想解决的问题</span><textarea ref={problemRef} className="problem-input" rows={5} maxLength={24000} value={form.problem_text} onChange={(e) => updateForm('problem_text', e.target.value)} placeholder="粘贴完整题目、材料、代码或任务要求。包含条件、图表说明和你想解决的问题。" /></label>
              <div className="question-tools"><label className="upload-button">＋ 添加题目图片<input type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={addImages} disabled={locked || attachments.length >= 4} /></label><span className="hint">最多 4 张 · 每张 5 MB</span><label className="subject-field"><span>学科</span><input aria-label="学科，留空自动识别" maxLength={100} value={form.subject} onChange={(e) => updateForm('subject', e.target.value)} placeholder="自动识别 / 自由填写" /></label></div>
              {attachments.length > 0 && <div className="attachments">{attachments.map((item) => <div className="attachment" key={item.id}><img src={item.url} alt={`题目图片：${item.name}`} /><button type="button" aria-label={`移除 ${item.name}`} onClick={() => { resetConversation(); setAttachments((current) => current.filter((entry) => entry.id !== item.id)) }}>×</button><span title={item.name}>{item.name}</span></div>)}</div>}
              <label className="field"><span>你的答案与思考过程 <em>选填</em></span><textarea rows={3} maxLength={24000} value={form.student_answer} onChange={(e) => updateForm('student_answer', e.target.value)} placeholder="无论完成到哪一步，都可以写下答案、推理过程或不确定的地方。还没开始也没关系。" /></label>
              <div className="field-pair"><label className="field"><span>这次希望得到什么帮助</span><input maxLength={2000} value={form.parent_goal} onChange={(e) => updateForm('parent_goal', e.target.value)} placeholder="例如：先给提示，让我自己想" /></label><label className="field"><span>补充背景 <em>选填</em></span><input maxLength={4000} value={form.parent_note} onChange={(e) => updateForm('parent_note', e.target.value)} placeholder="例如：这个概念是第一次接触" /></label></div>
              <div className="submit-row"><p className="hint">{dirty ? '开始时会先保存你刚修改的画像。' : sessionId ? '继续这道题可以在下方追问；修改题干会开始新会话。' : '根据完整题意与学习画像，选择合适的讲解方式。'}</p><button className="button button-primary" type="submit" disabled={!form.problem_text.trim() && !attachments.length}>{busy === 'tutor' ? '正在理解题目与学习背景…' : sessionId ? '讲解当前作答 →' : '开始一起学 →'}</button></div>
            </fieldset></form>
          </section>
          {error && <div className="notice" role="alert">{error}<span className="hint">内容未丢失，可再次点击原操作重试。</span></div>}

          <section ref={resultRef} className="lesson-region" aria-busy={busy === 'tutor'}>
            <div className="section-heading result-heading"><div><p className="eyebrow">03 / 把思路走通</p><h2>你的专属讲解</h2></div>{turns.length > 0 && <span className="pill">第 {turns.length} 轮</span>}</div>
            {busy === 'tutor' && <div className="loading-card" role="status"><span className="loading-dot" /><div><strong>正在结合画像组织讲解</strong><p>理解题意、检查作答依据，再选择适合你的引导方式。</p></div></div>}
            {!result && busy !== 'tutor' && <div className="empty-lesson"><span className="empty-symbol" aria-hidden="true">↗</span><h3>从你现在会的地方出发</h3><p>提交后，这里会呈现分步讲解、理解检查和练习。遇到缺少的条件，会先请你补充。</p><div className="learning-path"><span>理解问题</span><i>→</i><span>找到思路</span><i>→</i><span>独立尝试</span></div></div>}
            {turns.length > 1 && <details className="panel history-panel"><summary>查看前 {turns.length - 1} 轮讲解</summary><div className="history-list">{turns.slice(0, -1).map((turn, index) => <details key={turn.result.turn_id}><summary>第 {index + 1} 轮 · {turn.question}</summary><div className="details-body">{turn.result.lesson?.steps?.map((step, stepIndex) => <div key={stepIndex}><strong>{step.title}</strong><p className="prose">{step.explanation}</p>{step.question && <p className="question-callout">{step.question}</p>}</div>)}<TextList items={turn.result.clarifying_questions} /><p className="prose">{turn.result.lesson?.recap}</p></div></details>)}</div></details>}
            {result && <div className="result-stack">
              <div className="result-meta"><span className={`pill status-${result.status}`}>{statusLabels[result.status] || result.status}</span>{result.analysis?.subject && <span className="pill">{result.analysis.subject}</span>}{result.analysis?.task_type && <span className="pill">{result.analysis.task_type}</span>}</div>
              {uniqueWarnings.length > 0 && <div className="notice"><TextList items={uniqueWarnings} /></div>}
              {result.verification && !result.verification.reliable && <div className="notice"><strong>这份分析还有不确定之处</strong><TextList items={result.verification.issues} /></div>}
              {result.status === 'degraded' && <button className="button button-secondary" type="button" disabled={locked} onClick={(event) => submitTutor(event, retryModeRef.current)}>保留本次内容，重新尝试</button>}
              {result.clarifying_questions?.length > 0 && <section className="panel clarification-panel"><p className="eyebrow">先把条件补充完整</p><h3>继续之前，请补充这些信息</h3><TextList items={result.clarifying_questions} /><p className="hint">在下方「继续聊这道题」中回复即可。</p></section>}
              {result.analysis && <section className="panel analysis-panel"><p className="eyebrow">我们正在解决</p><h3>{result.analysis.task_summary}</h3>{result.analysis.learning_objectives?.length > 0 && <div className="objective-tags">{result.analysis.learning_objectives.map((item, index) => <span key={index}>{item}</span>)}</div>}
                {result.analysis.assessment && <div className="assessment"><span className="assessment-label">{verdictLabels[result.analysis.assessment.verdict] || '作答分析'}</span><p className="prose">{result.analysis.assessment.summary}</p><TextList items={result.analysis.assessment.evidence} />{result.analysis.assessment.verdict === 'uncertain' && <p className="hint">先澄清依据，再判断理解情况。</p>}</div>}
                {result.analysis.missing_information?.length > 0 && <details><summary>仍缺少的信息</summary><TextList items={result.analysis.missing_information} /></details>}
                {result.analysis.reference_solution?.length > 0 && <details className="reference-details"><summary>查看参考解答</summary><div className="details-body"><TextList items={result.analysis.reference_solution} className="prose" /></div></details>}
              </section>}
              {result.strategy && <details className="panel strategy-panel" open><summary>为什么这样讲给你听</summary><div className="details-body"><h3>{result.strategy.approach}</h3><TextList items={result.strategy.rationale} />{result.strategy.profile_used?.length > 0 && <div className="profile-used"><span className="hint">使用了这些画像信息</span><TextList items={result.strategy.profile_used.map((field) => profileLabels[field] || field)} /></div>}</div></details>}
              {result.lesson && <section className="panel lesson-panel"><p className="eyebrow">一步一步来</p><h2>{result.lesson.title}</h2><p className="lesson-goal prose">{result.lesson.goal}</p><ol className="lesson-steps">{(result.lesson.steps || []).map((step, index) => <li key={index}><span className="step-number">{String(index + 1).padStart(2, '0')}</span><div><h3>{step.title}</h3><p className="prose">{step.explanation}</p>{step.question && <div className="question-callout"><span>停下来想一想</span><p className="prose">{step.question}</p><button type="button" className="text-button" disabled={locked} onClick={() => answerCheck(step.question)}>回答这个问题 ↗</button></div>}{step.checkpoint && <details className="checkpoint"><summary>家长检查要点（作答后查看）</summary><p className="prose">{step.checkpoint}</p></details>}</div></li>)}</ol>{result.lesson.recap && <div className="recap"><strong>带走这个思路</strong><p className="prose">{result.lesson.recap}</p></div>}</section>}
              {result.lesson?.understanding_checks?.length > 0 && <section className="panel"><p className="eyebrow">试着自己说一遍</p><h3>理解检查</h3><ul className="text-list check-list">{result.lesson.understanding_checks.map((question, index) => <li key={index}><span className="prose">{question}</span><button className="text-button" type="button" disabled={locked} onClick={() => answerCheck(question)}>回答这道检查题 ↗</button></li>)}</ul><p className="hint">选择一个问题提交作答，家教会根据这份回答检查理解。</p></section>}
              {result.lesson?.parent_tips?.length > 0 && <details className="panel"><summary>给陪伴学习的家长</summary><div className="details-body"><TextList items={result.lesson.parent_tips} /></div></details>}
              {result.lesson?.practice?.length > 0 && <section className="panel practice-panel"><p className="eyebrow">从看懂，到会用</p><h3>独立试一题</h3><div className="practice-list">{result.lesson.practice.map((practice, index) => <article className="practice-card" key={practice.id || index}><p className="practice-purpose">练习 {index + 1} · {practice.purpose}</p><p className="prose">{practice.prompt}</p>{practice.hints?.length > 0 && <details><summary>需要一点提示</summary><TextList items={practice.hints} /></details>}{practice.success_criteria?.length > 0 && <details><summary>怎样检查自己做到了</summary><TextList items={practice.success_criteria} /></details>}<label className="field"><span>练习答案与过程</span><textarea rows={3} maxLength={24000} disabled={locked} value={practiceAnswers[practice.id] || ''} onChange={(e) => setPracticeAnswers((current) => ({ ...current, [practice.id]: e.target.value }))} placeholder="先独立尝试，再带着作答开始这道练习。" /></label><button className="button button-secondary" type="button" disabled={locked} onClick={() => usePractice(practice)}>将练习与作答带入新题 →</button><p className="hint">会更换上方题目并开启新会话，点击「开始一起学」获得反馈。</p></article>)}</div></section>}
              {result.profile_updates?.length > 0 && <div className="profile-update"><strong>本次学习记录</strong><TextList items={result.profile_updates} /></div>}
              <section className="panel followup-panel">
                <p className="eyebrow">一起往下想</p><h3>{selectedCheck ? '提交理解检查' : '继续聊这道题'}</h3>
                <form onSubmit={(event) => submitTutor(event, true)}><fieldset disabled={locked}>
                  {selectedCheck && <div className="question-callout selected-check"><span>你正在回答这个问题</span><p className="prose">{selectedCheck}</p><button className="text-button" type="button" onClick={cancelCheck}>取消作答，改为追问</button></div>}
                  <label className="field"><span>{selectedCheck ? '你的回答与依据' : '追问或补充信息'}</span><textarea id="follow-up" rows={3} maxLength={selectedCheck ? 24000 : 4000} value={followUp} onChange={(e) => { requestRef.current = null; setFollowUp(e.target.value) }} placeholder={selectedCheck ? '针对上面的问题，写下你的回答与思考过程。' : '补充题目条件，或告诉我哪一步还不理解。'} /></label>
                  <label className="field"><span>希望怎样调整讲法 <em>选填</em></span><input maxLength={300} value={strategy} onChange={(e) => { requestRef.current = null; setStrategy(e.target.value) }} placeholder="例如：用我熟悉的篮球举例；这一点再拆小一些" /></label>
                  <div className="submit-row"><p className="hint">{selectedCheck ? '这份回答会作为新的作答，评估依据充分时才记入学习观察。' : '追问用于继续讲解，不会直接作为新的作答证据。'}</p><button className="button button-primary" type="submit" disabled={selectedCheck ? !followUp.trim() : !followUp.trim() && !strategy.trim()}>{selectedCheck ? '提交这份作答 →' : '继续讨论 →'}</button></div>
                </fieldset></form>
              </section>
              {result.lesson && <section className="panel feedback-panel"><h3>这次的讲法适合你吗？</h3><p className="hint">你的反馈帮助调整后续讲解方式。</p><form onSubmit={submitFeedback}><fieldset disabled={locked || feedbackSent}><div className="feedback-options" role="group" aria-label="讲解是否有帮助"><button className={`button button-quiet ${feedback.useful === true ? 'selected' : ''}`} type="button" aria-pressed={feedback.useful === true} onClick={() => setFeedback((current) => ({ ...current, useful: true }))}>有帮助</button><button className={`button button-quiet ${feedback.useful === false ? 'selected' : ''}`} type="button" aria-pressed={feedback.useful === false} onClick={() => setFeedback((current) => ({ ...current, useful: false }))}>还需要调整</button></div><div className="field-pair"><label className="field"><span>现在理解了吗？</span><select value={feedback.child_understood} onChange={(e) => setFeedback((current) => ({ ...current, child_understood: e.target.value }))}><option value="">还不确定</option><option value="yes">能够理解了</option><option value="no">还有不明白的地方</option></select></label><label className="field"><span>具体反馈 <em>选填</em></span><input maxLength={4000} value={feedback.comment} onChange={(e) => setFeedback((current) => ({ ...current, comment: e.target.value }))} placeholder="哪一步有帮助，哪里还卡住？" /></label></div><button className="button button-secondary" type="submit" disabled={feedback.useful === null}>{feedbackSent ? '反馈已记录' : '记录反馈'}</button></fieldset></form>{feedbackMessage && <p className={feedbackSent ? 'success-text' : 'error-text'} role="status">{feedbackMessage}</p>}</section>}
            </div>}
          </section>
        </div>
      </main>
      <footer>知伴 · 让每一次思考，都成为下一次进步的起点。</footer>
    </div>
  )
}

export default App
