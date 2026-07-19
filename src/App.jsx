import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, ArrowRight, Bell, BrainCircuit, Check, CheckCircle2, ChevronDown, ClipboardCheck,
  CircleDollarSign, Clock3, Copy, Download, Eye, FileCheck2, Gauge, LayoutDashboard,
  Flag, LoaderCircle, LockKeyhole, LogOut, Menu, MessageSquareText, Moon, Search, Send, Settings as SettingsIcon,
  Shield, ShieldAlert, ShieldCheck, Sparkles, Sun, TrendingUp, TriangleAlert, UserRound,
  UsersRound, WalletCards, X, XCircle,
} from 'lucide-react'
import { api, getLedgerWithTransactions, session } from './lib/api'

const AuthContext = createContext(null)
const naira = new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN', maximumFractionDigits: 0 })
const compactNaira = new Intl.NumberFormat('en-NG', { notation: 'compact', style: 'currency', currency: 'NGN' })
const statusMap = {
  approved: { label: 'Approved', tone: 'safe' },
  flagged: { label: 'Flagged', tone: 'warning' },
  awaiting_review: { label: 'Security hold', tone: 'warning' },
  review_approved: { label: 'Review approved', tone: 'safe' },
  blocked: { label: 'Blocked', tone: 'danger' },
  confirmed: { label: 'Override', tone: 'warning' },
  cancelled: { label: 'Cancelled', tone: 'danger' },
  pending: { label: 'Pending', tone: 'neutral' },
}

function useAuth() { return useContext(AuthContext) }

function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(session.access))

  useEffect(() => {
    if (!session.access) return
    api.me().then(setUser).catch(() => session.clear()).finally(() => setLoading(false))
  }, [])

  const value = useMemo(() => ({
    user, loading,
    login: async (details) => setUser(await api.login(details)),
    register: async (details) => setUser(await api.register(details)),
    logout: () => { session.clear(); setUser(null) },
  }), [user, loading])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

function Brand({ compact = false }) {
  return <div className="brand">
    <span className="brand-mark"><ShieldCheck size={21} /></span>
    {!compact && <span><b>Eso</b><small>Financial Oversight</small></span>}
  </div>
}

function AuthPage() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ username: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const update = (key) => (event) => setForm((value) => ({ ...value, [key]: event.target.value }))
  const submit = async (event) => {
    event.preventDefault(); setError(''); setBusy(true)
    try {
      if (mode === 'login') await login({ username: form.username, password: form.password })
      else await register(form)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return <main className="auth-page">
    <div className="auth-art" aria-hidden="true">
      <div className="auth-orb orb-one" /><div className="auth-orb orb-two" />
      <Brand />
      <div className="auth-copy">
        <span className="eyebrow"><Sparkles size={14} /> AI-powered protection</span>
        <h1>Your money moves.<br /><em>Eso watches.</em></h1>
        <p>A calm, intelligent layer of protection that learns your habits and only steps in when something feels wrong.</p>
        <div className="protection-proof"><ShieldCheck /><span><b>Every transfer analysed</b><small>before money leaves your account</small></span></div>
      </div>
    </div>
    <section className="auth-panel">
      <div className="auth-mobile-brand"><Brand /></div>
      <div className="auth-form-wrap">
        <span className="eyebrow muted">WELCOME TO ESO</span>
        <h2>{mode === 'login' ? 'Welcome back' : 'Create your guardian profile'}</h2>
        <p>{mode === 'login' ? 'Sign in to manage your protected transactions.' : 'Start building a safer financial behaviour profile.'}</p>
        <div className="segmented" aria-label="Account action">
          <button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>Sign in</button>
          <button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>Create account</button>
        </div>
        <form onSubmit={submit}>
          <label>Username<input required value={form.username} onChange={update('username')} placeholder="e.g. alexmercer" autoComplete="username" /></label>
          {mode === 'register' && <label>Email address<input required type="email" value={form.email} onChange={update('email')} placeholder="alex@example.com" autoComplete="email" /></label>}
          <label>Password<input required minLength={8} type="password" value={form.password} onChange={update('password')} placeholder="At least 8 characters" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /></label>
          {error && <div className="form-error"><TriangleAlert size={16} />{error}</div>}
          <button className="button primary full" disabled={busy}>{busy ? <LoaderCircle className="spin" size={18} /> : null}{mode === 'login' ? 'Sign in securely' : 'Create account'}<ArrowRight size={18} /></button>
        </form>
        <small className="auth-note"><LockKeyhole size={13} /> Your session is protected with secure access tokens.</small>
      </div>
    </section>
  </main>
}

const navItems = [
  ['/', 'Dashboard', LayoutDashboard], ['/send', 'Send Money', Send],
  ['/ledger', 'Transparency Ledger', WalletCards], ['/reviews', 'Security Reviews', ClipboardCheck], ['/settings', 'Settings', SettingsIcon],
]

function Shell({ children }) {
  const location = useLocation(); const { user, logout } = useAuth(); const [open, setOpen] = useState(false)
  return <div className="app-shell">
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="side-head"><Brand /><button className="icon-button mobile-only" onClick={() => setOpen(false)}><X /></button></div>
      <nav>{navItems.filter(([path]) => path !== '/reviews' || user?.is_staff).map(([path, label, Icon]) => <Link key={path} to={path} className={location.pathname === path ? 'active' : ''} onClick={() => setOpen(false)}><Icon size={20} />{label}</Link>)}</nav>
      <div className="sidebar-user"><span className="avatar">{user?.username?.[0]?.toUpperCase()}</span><span><b>{user?.username}</b><small>Guardian active</small></span><button title="Sign out" onClick={logout}><LogOut size={17} /></button></div>
    </aside>
    {open && <button className="sidebar-scrim" aria-label="Close menu" onClick={() => setOpen(false)} />}
    <div className="main-column">
      <header className="topbar"><button className="icon-button mobile-only" onClick={() => setOpen(true)}><Menu /></button><div className="top-search"><Search size={17} /><span>Search transactions...</span></div><button className="icon-button"><Bell size={20} /></button><span className="avatar small">{user?.username?.[0]?.toUpperCase()}</span></header>
      <main className="page">{children}</main>
    </div>
  </div>
}

function Protected({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="splash"><Brand /><LoaderCircle className="spin" /></div>
  return user ? children : <Navigate to="/login" replace />
}

function PageHeading({ eyebrow, title, copy, action }) {
  return <div className="page-heading"><div>{eyebrow && <span className="eyebrow muted">{eyebrow}</span>}<h1>{title}</h1>{copy && <p>{copy}</p>}</div>{action}</div>
}

function RiskRing({ value = 0, tone = 'blue', size = 'large', label = 'risk score' }) {
  const score = Math.round(Number(value) * (Number(value) <= 1 ? 100 : 1))
  return <div className={`risk-ring ${tone} ${size}`} style={{ '--score': `${score * 3.6}deg` }}><div><b>{score}<sup>%</sup></b><span>{label}</span></div></div>
}

function Dashboard() {
  const { user } = useAuth(); const [items, setItems] = useState([]); const [loading, setLoading] = useState(true)
  useEffect(() => { getLedgerWithTransactions().then(setItems).catch(() => {}).finally(() => setLoading(false)) }, [])
  const unique = [...new Map(items.map((item) => [item.transaction, item.transactionDetail])).values()].filter(Boolean)
  const avg = unique.length ? unique.reduce((sum, t) => sum + Number(t.risk_score || 0), 0) / unique.length : 0
  const approved = unique.filter((t) => ['approved', 'review_approved'].includes(t.status)).length
  const trust = Math.max(0, Math.round((1 - avg) * 100))
  const hour = new Date().getHours(); const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  return <>
    <PageHeading eyebrow="OVERVIEW" title={`${greeting}, ${user.username}`} copy="Here’s how Eso has been protecting your transfers." action={<a className="button primary" href="/send"><Send size={17} />Send money</a>} />
    <section className="hero-card"><div><span className="status-dot safe">LIVE PROTECTION</span><h2>Your transactions are protected.</h2><p>Eso quietly watches every transfer and only steps in when something looks unusual.</p></div><RiskRing value={trust} label="trust score" /></section>
    <section className="stats-grid">
      <Stat icon={Gauge} label="Transactions analysed" value={loading ? '—' : unique.length} note="All-time" />
      <Stat icon={ShieldCheck} label="Protected transfers" value={loading ? '—' : approved} note="Approved safely" tone="green" />
      <Stat icon={TriangleAlert} label="Average risk score" value={loading ? '—' : `${Math.round(avg * 100)}%`} note="Across activity" tone="amber" />
      <Stat icon={UsersRound} label="Known recipients" value={loading ? '—' : new Set(unique.filter((t) => t.status === 'approved').map((t) => t.recipient)).size} note="Behaviour profile" />
    </section>
    <section className="dashboard-grid">
      <div className="card activity-card"><div className="card-title"><div><span className="eyebrow muted">LATEST</span><h2>Recent activity</h2></div><a href="/ledger">View all <ArrowRight size={15} /></a></div>
        {loading ? <LoadingRows /> : unique.length ? <div className="activity-list">{unique.slice(0, 4).map((t) => <ActivityRow key={t.id} transaction={t} />)}</div> : <EmptyState icon={FileCheck2} title="No transfers yet" copy="Your analysed transactions will appear here." action="Make your first transfer" href="/send" />}
      </div>
      <div className="card how-card"><span className="eyebrow muted">QUIETLY WORKING</span><h2>How Eso protects you</h2>
        {[['01', Eye, 'Observe', 'Learns your normal transaction patterns.'], ['02', BrainCircuit, 'Analyse', 'Scores behaviour and fraud signals in real time.'], ['03', Shield, 'Protect', 'Pauses only unusual transfers for your review.']].map(([n, Icon, title, copy]) => <div className="protect-step" key={n}><span><Icon size={19} /></span><div><small>{n}</small><b>{title}</b><p>{copy}</p></div></div>)}
      </div>
    </section>
  </>
}

function Stat({ icon: Icon, label, value, note, tone = '' }) { return <div className="stat-card"><div className={`stat-icon ${tone}`}><Icon size={20} /></div><span>{label}</span><b>{value}</b><small>{note}</small></div> }
function LoadingRows() { return <div className="loading-rows">{[1,2,3].map((n) => <div key={n}><i /><span /></div>)}</div> }
function ActivityRow({ transaction: t }) { const meta = statusMap[t.status] || statusMap.pending; return <div className="activity-row"><span className={`activity-icon ${meta.tone}`}>{meta.tone === 'safe' ? <Check size={17} /> : meta.tone === 'danger' ? <X size={17} /> : <TriangleAlert size={17} />}</span><div><b>{t.recipient}</b><small>{Math.round((t.risk_score || 0) * 100)}% risk · {new Date(t.created_at).toLocaleString('en-NG', { dateStyle: 'medium', timeStyle: 'short' })}</small></div><span className="activity-amount">{naira.format(t.amount)}<StatusPill status={t.status} /></span></div> }
function EmptyState({ icon: Icon, title, copy, action, href }) { return <div className="empty"><span><Icon /></span><h3>{title}</h3><p>{copy}</p>{action && <a className="button secondary" href={href}>{action}</a>}</div> }
function StatusPill({ status }) { const meta = statusMap[status] || statusMap.pending; return <span className={`pill ${meta.tone}`}>{meta.label}</span> }

const banks = ['Access Bank', 'First Bank of Nigeria', 'Guaranty Trust Bank', 'Kuda Bank', 'Opay', 'PalmPay', 'United Bank for Africa', 'Zenith Bank']

const DEMO_SCENARIOS = [
  {
    id: 'routine',
    label: 'Routine family support',
    tag: 'Usually approved',
    tone: 'safe',
    recipient: 'Ada Okafor',
    bank: 'Guaranty Trust Bank',
    account: '0123456789',
    amount: '85000',
    description: 'Monthly support — sister in Lagos',
  },
  {
    id: 'community-reported',
    label: 'Community-reported account',
    tag: '3 prior reports',
    tone: 'warning',
    recipient: 'Unknown beneficiary',
    bank: 'Opay',
    account: '8091234567',
    amount: '85000',
    description: 'First payment to a new supplier',
  },
  {
    id: 'late-night',
    label: 'Late-night large wire',
    tag: 'High risk',
    tone: 'warning',
    recipient: 'Chidi Eze',
    bank: 'Access Bank',
    account: '0987654321',
    amount: '1500000',
    description: 'WhatsApp investment contact — send tonight',
  },
]

function formatRecipient(bank, name) {
  return bank ? `${bank} - ${name}` : name
}

function csvEscape(value) {
  const str = String(value ?? '')
  return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str
}

function SendMoney() {
  const navigate = useNavigate(); const [stage, setStage] = useState('form'); const [transaction, setTransaction] = useState(null)
  const [form, setForm] = useState({ recipient: '', bank: '', account: '', amount: '', description: '', paymentPin: '' }); const [error, setError] = useState(''); const [progress, setProgress] = useState(0)
  const [pinStatus, setPinStatus] = useState(null)
  useEffect(() => { api.paymentPinStatus().then(setPinStatus).catch(() => {}) }, [])
  const update = (key) => (event) => setForm((value) => ({ ...value, [key]: event.target.value }))
  const applyScenario = (scenario) => {
    setForm({
      recipient: scenario.recipient,
      bank: scenario.bank,
      account: scenario.account,
      amount: scenario.amount,
      description: scenario.description,
      paymentPin: '',
    })
    setError('')
  }
  const submit = async (event) => {
    event.preventDefault(); setError(''); setStage('analysing'); setProgress(12)
    const timer = window.setInterval(() => setProgress((p) => Math.min(p + 17, 89)), 280)
    try {
      const result = await api.createTransaction({
        recipient: formatRecipient(form.bank, form.recipient),
        recipient_account_id: form.account,
        recipient_bank: form.bank,
        amount: Number(form.amount),
        description: form.description,
        payment_pin: form.paymentPin,
        device_id: navigator.userAgent.slice(0, 150),
      })
      setTransaction(result); setProgress(100); await new Promise((resolve) => setTimeout(resolve, 450)); setStage(result.status === 'flagged' ? 'flagged' : 'approved')
    } catch (err) { setError(err.message); setStage('form') } finally { clearInterval(timer) }
  }
  const decide = async (decision) => {
    setStage('analysing'); setProgress(92)
    try { const result = await api.decideTransaction(transaction.id, decision); setTransaction(result); setStage(decision === 'confirm' ? 'confirmed' : 'cancelled') }
    catch (err) { setError(err.message); setStage('flagged') }
  }
  const requestReview = async () => {
    setError(''); setStage('analysing'); setProgress(94)
    try { const result = await api.requestSecurityReview(transaction.id); setTransaction(result); setStage('review') }
    catch (err) { setError(err.message); setStage('flagged') }
  }
  const reset = () => { setTransaction(null); setForm({ recipient: '', bank: '', account: '', amount: '', description: '', paymentPin: '' }); setStage('form'); setProgress(0) }
  if (stage === 'analysing') return <Analysis progress={progress} cancel={() => setStage(transaction ? 'flagged' : 'form')} />
  if (stage === 'flagged') return <Intervention transaction={transaction} onTransaction={setTransaction} onConfirm={() => decide('confirm')} onCancel={() => decide('cancel')} onRequestReview={requestReview} error={error} />
  if (stage === 'review') return <ReviewHold transaction={transaction} onCancel={() => decide('cancel')} onLedger={() => navigate('/ledger')} />
  if (['approved', 'confirmed', 'cancelled'].includes(stage)) return <TransferResult type={stage} transaction={transaction} onReset={reset} onLedger={() => navigate('/ledger')} />
  return <>
    <PageHeading eyebrow="NEW TRANSFER" title="Send money" copy="Eso analyses each transfer in real time before it leaves your account. Amounts are in Nigerian Naira (₦)." />
    <section className="transfer-layout">
      <form className="card transfer-form" onSubmit={submit}>
        <div className="demo-scenarios">
          <span className="eyebrow muted">NIGERIAN DEMO SCENARIOS</span>
          <p>Try a routine transfer first, then a fraud pattern to see Eso intervene.</p>
          <div className="demo-scenario-grid">
            {DEMO_SCENARIOS.map((scenario) => (
              <button key={scenario.id} type="button" className={`demo-scenario ${scenario.tone}`} onClick={() => applyScenario(scenario)}>
                <span className={`pill ${scenario.tone}`}>{scenario.tag}</span>
                <b>{scenario.label}</b>
                <small>{formatRecipient(scenario.bank, scenario.recipient)} · {naira.format(Number(scenario.amount))}</small>
              </button>
            ))}
          </div>
        </div>
        <div className="form-step"><span>1</span><div><b>Recipient details</b><small>Who are you sending money to?</small></div></div>
        <div className="form-grid">
          <label className="span-2">Recipient name<input required value={form.recipient} onChange={update('recipient')} placeholder="e.g. Ada Okafor" /></label>
          <label>Bank<select required value={form.bank} onChange={update('bank')}><option value="">Select bank</option>{banks.map((bank) => <option key={bank}>{bank}</option>)}</select></label>
          <label>Account number<input required inputMode="numeric" pattern="[0-9]{10}" maxLength="10" value={form.account} onChange={update('account')} placeholder="0123456789" /></label>
        </div>
        <hr />
        <div className="form-step"><span>2</span><div><b>Transfer details</b><small>How much would you like to send?</small></div></div>
        <label>Amount (NGN)<div className="money-input"><span>₦</span><input required min="100" step="100" type="number" value={form.amount} onChange={update('amount')} placeholder="0.00" /></div><small className="balance">Demo balance · ₦1,240,500.00</small></label>
        <label>Description <i>Optional</i><input value={form.description} onChange={update('description')} placeholder="What is this transfer for?" /></label>
        <hr />
        <div className="form-step"><span>3</span><div><b>Authorize payment</b><small>Confirm this transfer with your four-digit payment PIN.</small></div></div>
        {pinStatus && !pinStatus.has_pin ? <div className="pin-required"><LockKeyhole /><span><b>Payment PIN required</b><small>Set your PIN before making your first transfer.</small></span><Link className="button secondary" to="/settings">Set PIN</Link></div> : <label>Payment PIN<input required type="password" inputMode="numeric" pattern="[0-9]{4}" maxLength="4" autoComplete="off" value={form.paymentPin} onChange={update('paymentPin')} placeholder="••••" /></label>}
        {error && <div className="form-error"><TriangleAlert size={17} />{error}</div>}
        <button className="button primary full" type="submit" disabled={pinStatus && !pinStatus.has_pin}>Review with Eso <ArrowRight size={18} /></button>
      </form>
      <aside className="transfer-aside"><div className="guardian-visual"><span><ShieldCheck /></span><i className="orbit o1" /><i className="orbit o2" /></div><span className="eyebrow">ESO GUARDIAN</span><h2>Built for Nigerian banking fraud patterns.</h2><p>Eso learns your GTBank, Opay, and UBA habits — then challenges SIM-swap urgency, late-night wires, and unknown beneficiaries before money leaves.</p><div className="aside-points"><span><Check /> Learns recipients after safe transfers</span><span><Check /> Flags SIM swap &amp; odd-hour patterns</span><span><Check /> Every decision recorded in ₦</span></div></aside>
    </section>
  </>
}

function Analysis({ progress, cancel }) {
  const checks = ['Recipient history', 'Amount pattern', 'Behaviour profile', 'Time analysis', 'Fraud signals']
  return <div className="flow-wrap"><div className="analysis-card card"><div className="analysis-shield"><ShieldCheck /></div><span className="eyebrow muted">AI TRANSACTION ANALYSIS</span><h1>Analysing your transfer</h1><p>Eso is comparing this transfer with your usual behaviour.</p><div className="analysis-progress"><span style={{ width: `${progress}%` }} /></div><b className="progress-label">{progress}% complete</b><div className="check-list">{checks.map((check, i) => { const done = progress >= (i + 1) * 18; return <div key={check} className={done ? 'done' : ''}>{done ? <Check /> : <LoaderCircle className="spin" />}<span>{check}</span></div> })}</div><button className="button secondary full" onClick={cancel}><X size={17} /> Cancel analysis</button></div></div>
}

function reasonList(reason = '') {
  const parts = reason.split(/[.;]\s*/).filter((part) => part.length > 3)
  return parts.length ? parts.slice(0, 3) : ['This transfer differs from your usual behaviour.']
}

function ReportPanel({ transaction, onTransaction }) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('impersonation')
  const [detail, setDetail] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const submit = async () => {
    setBusy(true); setMessage('')
    try {
      const result = await api.reportRecipient(transaction.id, { reason, detail })
      onTransaction?.(result.transaction)
      setMessage(`Report recorded. ${result.report_count} Eso user${result.report_count === 1 ? '' : 's'} have now reported this account.`)
    } catch (err) { setMessage(err.message) } finally { setBusy(false) }
  }
  if (!transaction.recipient_account_id) return null
  return <div className="report-control">
    <button type="button" className="report-trigger" onClick={() => setOpen((value) => !value)}><Flag size={16} /> Report this recipient as suspicious</button>
    {open && <div className="report-panel"><b>Help protect the Eso community</b><p>Your report raises this beneficiary account’s risk for other users.</p><label>What looked suspicious?<select value={reason} onChange={(event) => setReason(event.target.value)}><option value="impersonation">Impersonation</option><option value="investment">Investment scam</option><option value="romance">Romance scam</option><option value="purchase">Goods or services scam</option><option value="coercion">Pressure or coercion</option><option value="other">Other suspicious activity</option></select></label><label>What happened? <i>Optional</i><textarea value={detail} onChange={(event) => setDetail(event.target.value)} placeholder="Share a short detail without including passwords or PINs." /></label>{message && <div className="report-message">{message}</div>}<button type="button" className="button danger" onClick={submit} disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <Flag size={16} />}Submit community report</button></div>}
  </div>
}

function Intervention({ transaction, onTransaction, onConfirm, onCancel, onRequestReview, error }) {
  const [answer, setAnswer] = useState(transaction.reflection_answer || '')
  const [reflectionError, setReflectionError] = useState('')
  const [busy, setBusy] = useState(false)
  const secondsRemaining = () => transaction.cooldown_until ? Math.max(0, Math.ceil((new Date(transaction.cooldown_until).getTime() - Date.now()) / 1000)) : 0
  const [seconds, setSeconds] = useState(secondsRemaining)
  useEffect(() => {
    setSeconds(secondsRemaining())
    const timer = window.setInterval(() => setSeconds(secondsRemaining()), 500)
    return () => window.clearInterval(timer)
  }, [transaction.cooldown_until])
  const reflected = Boolean(transaction.reflection_submitted_at)
  const critical = transaction.risk_tier === 'critical'
  const submitReflection = async () => {
    setBusy(true); setReflectionError('')
    try { onTransaction(await api.submitReflection(transaction.id, answer)) }
    catch (err) { setReflectionError(err.message) } finally { setBusy(false) }
  }
  return <div className="intervention-page"><div className="intervention-card card"><div className="warning-mark"><ShieldAlert /></div><span className="eyebrow amber">ESO INTERVENTION</span><h1>Pause and think</h1><p className="lead">This transfer needs a more deliberate review.</p><RiskRing value={transaction.risk_score} tone="amber" />
    <section className="reasons"><span className="eyebrow muted">WHY WAS THIS FLAGGED?</span><h2>Here’s what Eso noticed</h2>{reasonList(transaction.risk_reason).map((reason, i) => <div key={reason}><span>{i === 0 ? <UserRound /> : i === 1 ? <TrendingUp /> : <Clock3 />}</span><p>{reason}</p></div>)}</section>
    {transaction.network_report_count > 0 && <div className="network-warning"><UsersRound /><span><b>Shared safety signal</b><p>{transaction.network_report_count} other Eso user{transaction.network_report_count === 1 ? '' : 's'} reported this beneficiary account. This signal applies across the network, not only to your profile.</p></span></div>}
    {!reflected ? <section className="reflection-step"><span className="eyebrow muted"><MessageSquareText size={14} /> REQUIRED REFLECTION</span><h2>{transaction.reflection_prompt || 'In your own words, what is this payment for?'}</h2><p>Answer independently. Do not ask anyone on a call or chat what to type.</p><textarea autoFocus value={answer} onChange={(event) => setAnswer(event.target.value)} maxLength="1000" placeholder="Write at least a short sentence…" /><small>{answer.trim().length} characters · your answer is stored in the transparency ledger</small>{reflectionError && <div className="form-error"><TriangleAlert size={17} />{reflectionError}</div>}<button type="button" className="button primary full" disabled={busy} onClick={submitReflection}>{busy ? <LoaderCircle className="spin" size={17} /> : <ArrowRight size={17} />}Review my answer</button></section> : <section className="reflection-record"><CheckCircle2 /><span><b>Your reflection was recorded</b><p>“{transaction.reflection_answer}”</p></span></section>}
    {transaction.reflection_red_flags?.length > 0 && <div className="escalation-alert"><TriangleAlert /><span><b>Risk escalated</b><p>Your answer contains language commonly seen when someone is directing a payment: {transaction.reflection_red_flags.join(', ')}.</p></span></div>}
    {reflected && critical && <section className="cooldown-card"><Clock3 /><div><span className="eyebrow muted">INDEPENDENT SECURITY HOLD</span><h2>{seconds > 0 ? `${seconds} second minimum pause` : 'Ready for independent review'}</h2><p>{seconds > 0 ? 'This pause continues while a separate reviewer examines the transfer. You cannot release it from this session.' : 'This transaction still requires approval from an independent security reviewer.'}</p><div className="cooldown-track"><span style={{ width: `${Math.max(0, Math.min(100, ((30 - seconds) / 30) * 100))}%` }} /></div></div></section>}
    <ReportPanel transaction={transaction} onTransaction={onTransaction} />
    {(error || reflectionError) && error && <div className="form-error"><TriangleAlert size={17} />{error}</div>}
    <div className="decision-actions">{critical ? <button className="button secondary" disabled={!reflected} onClick={onRequestReview}><ClipboardCheck size={18} />Request security review</button> : <button className="button secondary" disabled={!reflected} onClick={onConfirm}>Continue after reflection</button>}<button className="button primary" onClick={onCancel}><XCircle size={18} /> Cancel transfer</button></div>
  </div></div>
}

function ReviewHold({ transaction, onCancel, onLedger }) {
  return <div className="flow-wrap"><div className="result-card card"><span className="result-icon warning"><LockKeyhole /></span><span className="eyebrow amber">INDEPENDENT SECURITY HOLD</span><h1>Review requested</h1><p className="lead">This critical-risk transfer cannot be released from your account session.</p><div className="review-hold-summary"><div><span>Recipient</span><b>{transaction.recipient}</b></div><div><span>Amount</span><b>{naira.format(transaction.amount)}</b></div><div><span>Risk score</span><b>{Math.round((transaction.risk_score || 0) * 100)}%</b></div><div><span>Status</span><StatusPill status={transaction.status} /></div></div><div className="record-note"><ClipboardCheck /><span><b>A separate decision is now required</b><small>A security reviewer can approve or block this transaction. You can still cancel it at any time.</small></span></div><div className="decision-actions"><button className="button primary" onClick={onLedger}>View ledger</button><button className="button danger" onClick={onCancel}><XCircle size={18} />Cancel transfer</button></div></div></div>
}

function TransferResult({ type, transaction, onReset, onLedger }) {
  const configs = {
    approved: { icon: CheckCircle2, tone: 'safe', title: 'Transfer approved', copy: 'This transaction matches your usual behaviour.', note: 'Eso completed its checks without adding friction.' },
    confirmed: { icon: Shield, tone: 'warning', title: 'Transaction completed', copy: 'You chose to continue after reviewing Eso’s warning.', note: 'Your override has been recorded for future protection.' },
    cancelled: { icon: LockKeyhole, tone: 'safe', title: 'Transfer cancelled', copy: 'No money left your account.', note: 'Your decision will help refine your future protection.' },
  }
  const config = configs[type]; const Icon = config.icon
  return <div className="flow-wrap"><div className="result-card card"><span className={`result-icon ${config.tone}`}><Icon /></span><span className="eyebrow muted">TRANSFER DECISION</span><h1>{config.title}</h1><p className="lead">{config.copy}</p><div className="result-summary"><div><span>Risk score</span><b>{Math.round((transaction.risk_score || 0) * 100)}%</b></div><div><span>Decision</span><StatusPill status={transaction.status} /></div><div><span>Recipient</span><b>{transaction.recipient}</b></div><div><span>Amount</span><b>{naira.format(transaction.amount)}</b></div></div><div className="record-note"><FileCheck2 /><span><b>Securely recorded</b><small>{config.note}</small></span></div><div className="decision-actions"><button className="button primary" onClick={onLedger}>View ledger</button><button className="button secondary" onClick={onReset}>Make another transfer</button></div></div></div>
}

function Ledger() {
  const [items, setItems] = useState([]); const [loading, setLoading] = useState(true); const [filter, setFilter] = useState('all'); const [query, setQuery] = useState(''); const [expanded, setExpanded] = useState(null)
  useEffect(() => { getLedgerWithTransactions().then(setItems).catch(() => {}).finally(() => setLoading(false)) }, [])
  const unique = [...new Map(items.map((item) => [item.transaction, { ...item.transactionDetail, ledgerEvent: item.event_type, ledgerDetail: item.detail }])).values()].filter((item) => item.id)
  const filtered = unique.filter((t) => (filter === 'all' || t.status === filter || (filter === 'confirmed' && t.status === 'confirmed')) && `${t.recipient} ${t.id}`.toLowerCase().includes(query.toLowerCase()))
  const exportLedger = () => {
    const headers = ['Date', 'Recipient', 'Account', 'Bank', 'Amount (NGN)', 'Status', 'Risk Tier', 'Risk Score', 'Network Reports', 'Risk Reason', 'Reflection Prompt', 'Reflection Answer', 'Reflection Red Flags', 'Review Status', 'Reviewer Note', 'Event', 'Detail', 'Transaction ID']
    const rows = filtered.map((t) => [
      new Date(t.created_at).toISOString(),
      t.recipient,
      t.recipient_account_id,
      t.recipient_bank,
      t.amount,
      t.status,
      t.risk_tier,
      t.risk_score ?? '',
      t.network_report_count ?? 0,
      t.risk_reason ?? '',
      t.reflection_prompt ?? '',
      t.reflection_answer ?? '',
      (t.reflection_red_flags || []).join(' | '),
      t.security_review?.status ?? '',
      t.security_review?.reviewer_note ?? '',
      t.ledgerEvent ?? '',
      t.ledgerDetail ?? '',
      t.id,
    ])
    const csv = [headers, ...rows].map((row) => row.map(csvEscape).join(',')).join('\n')
    const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `eso-ledger-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }
  return <>
    <PageHeading eyebrow="AUDIT TRAIL" title="Transparency ledger" copy="Every AI assessment and user decision is recorded here — export for auditors or judges." action={<button className="button secondary" onClick={exportLedger}><Download size={17} />Export CSV</button>} />
    <div className="ledger-toolbar"><div className="ledger-search"><Search size={18} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search recipient or transaction ID" /></div><div className="filter-tabs">{[['all','All'],['approved','Approved'],['flagged','Flagged'],['awaiting_review','In review'],['blocked','Blocked'],['cancelled','Cancelled']].map(([value,label]) => <button key={value} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)}>{label}<span>{value === 'all' ? unique.length : unique.filter((t) => t.status === value).length}</span></button>)}</div></div>
    <div className="ledger-layout"><aside className="card ledger-summary"><span className="eyebrow muted">YOUR RECORD</span><h3>Decision overview</h3><div className="ledger-stat"><span>Transfers analysed</span><b>{unique.length}</b></div><div className="ledger-stat safe"><span>Approved</span><b>{unique.filter((t) => ['approved','review_approved'].includes(t.status)).length}</b></div><div className="ledger-stat warning"><span>Flagged / held</span><b>{unique.filter((t) => ['flagged','confirmed','awaiting_review'].includes(t.status)).length}</b></div><div className="ledger-stat danger"><span>Cancelled / blocked</span><b>{unique.filter((t) => ['cancelled','blocked'].includes(t.status)).length}</b></div><div className="tamper-note"><LockKeyhole /><p><b>Tamper-evident record</b><small>Eso preserves a clear trail of how every decision was made.</small></p></div></aside>
      <section className="ledger-list">{loading ? <div className="card"><LoadingRows /></div> : filtered.length ? filtered.map((t) => <LedgerCard key={t.id} transaction={t} expanded={expanded === t.id} toggle={() => setExpanded(expanded === t.id ? null : t.id)} />) : <div className="card"><EmptyState icon={Search} title="No matching entries" copy="Try another filter or make a transfer to create a record." /></div>}</section></div>
  </>
}

function LedgerCard({ transaction: t, expanded, toggle }) {
  const [transaction, setTransaction] = useState(t)
  useEffect(() => setTransaction(t), [t])
  const item = transaction
  const meta = statusMap[item.status] || statusMap.pending
  return <article className={`card ledger-card ${meta.tone}`}>
    <button className="ledger-card-main" onClick={toggle}><span className={`ledger-event-icon ${meta.tone}`}>{meta.tone === 'safe' ? <Check /> : meta.tone === 'danger' ? <X /> : <TriangleAlert />}</span><div className="ledger-primary"><div><b>{naira.format(item.amount)}</b><StatusPill status={item.status} />{item.risk_tier === 'critical' && <span className="pill danger">Critical</span>}</div><p>to {item.recipient}</p><small>{new Date(item.created_at).toLocaleString('en-NG', { dateStyle: 'long', timeStyle: 'short' })}</small></div><div className="ledger-risk"><RiskRing value={item.risk_score} tone={meta.tone === 'danger' ? 'red' : meta.tone === 'warning' ? 'amber' : 'green'} size="small" /><ChevronDown className={expanded ? 'rotate' : ''} /></div></button>
    {expanded && <div className="ledger-detail">
      <div><span className="eyebrow muted"><BrainCircuit size={14} /> AI REASONING</span><p>{item.risk_reason || 'This transaction matched the user’s learned behaviour profile.'}</p>{item.network_report_count > 0 && <p className="ledger-network"><UsersRound size={16} /><b>{item.network_report_count} shared recipient report{item.network_report_count === 1 ? '' : 's'}</b> contributed to this assessment.</p>}</div>
      {item.reflection_answer && <div className="ledger-reflection"><span className="eyebrow muted"><MessageSquareText size={14} /> USER REFLECTION</span><b>{item.reflection_prompt}</b><blockquote>“{item.reflection_answer}”</blockquote>{item.reflection_red_flags?.length > 0 && <small>Escalation phrases: {item.reflection_red_flags.join(', ')}</small>}</div>}
      {item.security_review && <div className="ledger-review"><span className="eyebrow muted"><ClipboardCheck size={14} /> INDEPENDENT REVIEW</span><p><b>Status:</b> {item.security_review.status}</p>{item.security_review.reviewer_note && <blockquote>“{item.security_review.reviewer_note}”</blockquote>}</div>}
      <div><span className="eyebrow muted">TRANSACTION ID</span><code>{item.id}</code><button className="copy-button" onClick={() => navigator.clipboard.writeText(item.id)}><Copy size={14} /> Copy</button></div>
      <ReportPanel transaction={item} onTransaction={setTransaction} />
    </div>}
  </article>
}

function SecurityReviews() {
  const { user } = useAuth()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notes, setNotes] = useState({})
  const [busy, setBusy] = useState(null)
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    if (!user?.is_staff) return
    api.securityReviews().then(setItems).catch((err) => setError(err.message)).finally(() => setLoading(false))
  }, [user?.is_staff])
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 500); return () => window.clearInterval(timer) }, [])
  if (!user?.is_staff) return <Navigate to="/" replace />
  const decide = async (transaction, decision) => {
    setBusy(`${transaction.id}:${decision}`); setError('')
    try {
      await api.decideSecurityReview(transaction.id, decision, notes[transaction.id] || '')
      setItems((current) => current.filter((item) => item.id !== transaction.id))
    } catch (err) { setError(err.message) } finally { setBusy(null) }
  }
  return <>
    <PageHeading eyebrow="INDEPENDENT CONTROL" title="Security review queue" copy="Critical-risk transfers require a decision from someone outside the sender’s session." />
    {error && <div className="form-error review-page-error"><TriangleAlert size={17} />{error}</div>}
    <section className="review-queue">
      {loading ? <div className="card"><LoadingRows /></div> : items.length ? items.map((transaction) => {
        const seconds = transaction.cooldown_until ? Math.max(0, Math.ceil((new Date(transaction.cooldown_until).getTime() - now) / 1000)) : 0
        const hasNote = (notes[transaction.id] || '').trim().length >= 10
        return <article className="card review-case" key={transaction.id}>
          <div className="review-case-head"><span className="warning-mark"><ShieldAlert /></span><div><span className="eyebrow amber">CRITICAL · {Math.round(transaction.risk_score * 100)}% RISK</span><h2>{naira.format(transaction.amount)} to {transaction.recipient}</h2><small>{transaction.recipient_bank} · {transaction.recipient_account_id}</small></div><StatusPill status={transaction.status} /></div>
          <div className="review-evidence"><div><span className="eyebrow muted"><BrainCircuit size={14} /> WHY ESO INTERVENED</span><p>{transaction.risk_reason}</p>{transaction.network_report_count > 0 && <p className="ledger-network"><UsersRound size={16} />{transaction.network_report_count} community reports on this beneficiary.</p>}</div><div><span className="eyebrow muted"><MessageSquareText size={14} /> SENDER REFLECTION</span><b>{transaction.reflection_prompt}</b><blockquote>“{transaction.reflection_answer}”</blockquote>{transaction.reflection_red_flags?.length > 0 && <small className="red-flags">Detected coaching language: {transaction.reflection_red_flags.join(', ')}</small>}</div></div>
          <label className="review-note">Reviewer note <i>Required for a clear audit trail</i><textarea value={notes[transaction.id] || ''} onChange={(event) => setNotes((current) => ({ ...current, [transaction.id]: event.target.value }))} placeholder="Explain why this transfer should be approved or blocked." /></label>
          <div className="review-case-actions"><button className="button danger" disabled={Boolean(busy) || !hasNote} onClick={() => decide(transaction, 'block')}><LockKeyhole size={17} />Block transfer</button><button className="button primary" disabled={Boolean(busy) || seconds > 0 || !hasNote} onClick={() => decide(transaction, 'approve')}>{busy === `${transaction.id}:approve` ? <LoaderCircle className="spin" size={17} /> : <CheckCircle2 size={17} />}{seconds > 0 ? `Approve available after ${seconds}s` : 'Approve independently'}</button></div>
        </article>
      }) : <div className="card"><EmptyState icon={ClipboardCheck} title="No reviews waiting" copy="New critical-risk requests will appear here." /></div>}
    </section>
  </>
}

function SettingsPage() {
  const { user, logout } = useAuth(); const [baseline, setBaseline] = useState(null); const [level, setLevel] = useState(localStorage.getItem('eso_protection') || 'guardian'); const [prefs, setPrefs] = useState({ anomalies: true, weekly: true, routine: false }); const [dark, setDark] = useState(document.documentElement.dataset.theme === 'dark')
  const [pinStatus, setPinStatus] = useState(null)
  const [pinForm, setPinForm] = useState({ current_password: '', pin: '', pin_confirmation: '' })
  const [pinMessage, setPinMessage] = useState('')
  const [pinBusy, setPinBusy] = useState(false)
  useEffect(() => { api.baseline().then(setBaseline).catch(() => {}) }, [])
  useEffect(() => { api.paymentPinStatus().then(setPinStatus).catch(() => {}) }, [])
  const chooseLevel = (next) => { setLevel(next); localStorage.setItem('eso_protection', next) }
  const toggleDark = () => { const next = !dark; setDark(next); document.documentElement.dataset.theme = next ? 'dark' : ''; localStorage.setItem('eso_theme', next ? 'dark' : 'light') }
  const updatePin = (key) => (event) => setPinForm((current) => ({ ...current, [key]: event.target.value }))
  const savePin = async (event) => {
    event.preventDefault(); setPinBusy(true); setPinMessage('')
    try {
      const result = await api.setPaymentPin(pinForm)
      setPinStatus(result); setPinForm({ current_password: '', pin: '', pin_confirmation: '' })
      setPinMessage(pinStatus?.has_pin ? 'Payment PIN changed successfully.' : 'Payment PIN created successfully.')
    } catch (err) { setPinMessage(err.message) } finally { setPinBusy(false) }
  }
  return <>
    <PageHeading eyebrow="PREFERENCES" title="Settings" copy="Manage your profile, guardian behaviour and notifications." />
    <div className="settings-grid">
      <section className="card settings-card"><div className="settings-title"><span><UserRound /></span><div><h2>Profile information</h2><p>Your Eso account and protection status.</p></div></div><div className="profile-row"><span className="avatar large">{user.username[0].toUpperCase()}</span><div><span className="status-dot safe">FULLY VERIFIED</span><h3>{user.username}</h3><p>{user.email || 'No email supplied'}</p></div></div></section>
      <section className="card settings-card"><div className="settings-title"><span><LockKeyhole /></span><div><h2>Payment PIN</h2><p>{pinStatus?.has_pin ? 'Change the PIN used to authorize transfers.' : 'Create a PIN before making your first transfer.'}</p></div></div><form className="pin-settings-form" onSubmit={savePin}><label>Account password<input required type="password" autoComplete="current-password" value={pinForm.current_password} onChange={updatePin('current_password')} placeholder="Confirm your identity" /></label><div><label>New four-digit PIN<input required type="password" inputMode="numeric" pattern="[0-9]{4}" maxLength="4" autoComplete="new-password" value={pinForm.pin} onChange={updatePin('pin')} placeholder="••••" /></label><label>Confirm PIN<input required type="password" inputMode="numeric" pattern="[0-9]{4}" maxLength="4" autoComplete="new-password" value={pinForm.pin_confirmation} onChange={updatePin('pin_confirmation')} placeholder="••••" /></label></div>{pinMessage && <div className={pinMessage.includes('successfully') ? 'pin-success' : 'form-error'}>{pinMessage}</div>}<button className="button primary full" disabled={pinBusy}>{pinBusy ? <LoaderCircle className="spin" size={17} /> : <LockKeyhole size={17} />}{pinStatus?.has_pin ? 'Change payment PIN' : 'Create payment PIN'}</button></form></section>
      <section className="card settings-card span-2"><div className="settings-title"><span><Shield /></span><div><h2>AI security protocol</h2><p>Choose how assertively Eso monitors unusual behaviour.</p></div></div><div className="protection-levels">{[['standard','Standard','Known malicious patterns only.'],['guardian','Guardian','Recommended. Learns your habits and challenges anomalies.'],['maximum','Maximum','Every new recipient requires review.']].map(([value,title,copy]) => <button key={value} className={level === value ? 'active' : ''} onClick={() => chooseLevel(value)}><span>{level === value && <Check />}</span><b>{title}</b><p>{copy}</p></button>)}</div><div className="baseline-line"><span><b>Behaviour profile</b><small>{baseline ? `${baseline.typical_recipients.length} known recipients · typical range ${compactNaira.format(baseline.typical_amount_min)} – ${compactNaira.format(baseline.typical_amount_max)} · updates after safe transfers` : 'Loading learned baseline…'}</small></span><BrainCircuit /></div></section>
      <section className="card settings-card span-2"><div className="settings-title"><span><Bell /></span><div><h2>AI notifications</h2><p>Control when the guardian communicates with you.</p></div></div>{[['anomalies','Anomaly alerts','Unusual spending patterns and high-risk transfers.'],['weekly','Weekly protection summary','A concise report of activity and interventions.'],['routine','Routine confirmations','Notifications for normal, recurring transfers.']].map(([key,title,copy]) => <div className="toggle-row" key={key}><span><b>{title}</b><small>{copy}</small></span><button className={`toggle ${prefs[key] ? 'on' : ''}`} onClick={() => setPrefs((p) => ({ ...p, [key]: !p[key] }))}><i /></button></div>)}</section>
      <section className="card setting-action"><span className="settings-action-icon"><Download /></span><h3>Transparency records</h3><p>Your full decision history is available from the ledger.</p><a className="button primary full" href="/ledger">Open ledger</a></section>
      <section className="card setting-action"><span className="settings-action-icon"><Moon /></span><h3>Appearance</h3><p>Use the interface that is most comfortable for you.</p><button className="button secondary full" onClick={toggleDark}>{dark ? <Sun size={17} /> : <Moon size={17} />}{dark ? 'Use light mode' : 'Use dark mode'}</button></section>
      <section className="card settings-footer span-2"><span><LockKeyhole /><div><b>Signed in securely</b><small>Sign out of Eso on this device.</small></div></span><button className="button danger" onClick={logout}><LogOut size={17} />Sign out</button></section>
    </div>
  </>
}

function App() {
  useEffect(() => { document.documentElement.dataset.theme = localStorage.getItem('eso_theme') === 'dark' ? 'dark' : '' }, [])
  return <AuthProvider><Routes><Route path="/login" element={<AuthGate />} /><Route path="*" element={<Protected><Shell><Routes><Route path="/" element={<Dashboard />} /><Route path="/send" element={<SendMoney />} /><Route path="/ledger" element={<Ledger />} /><Route path="/reviews" element={<SecurityReviews />} /><Route path="/settings" element={<SettingsPage />} /><Route path="*" element={<Navigate to="/" replace />} /></Routes></Shell></Protected>} /></Routes></AuthProvider>
}
function AuthGate() { const { user, loading } = useAuth(); if (loading) return <div className="splash"><Brand /><LoaderCircle className="spin" /></div>; return user ? <Navigate to="/" replace /> : <AuthPage /> }

export default App
export { Intervention, ReportPanel }
