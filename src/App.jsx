import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, ArrowRight, Bell, BrainCircuit, Check, CheckCircle2, ChevronDown,
  CircleDollarSign, Clock3, Copy, Download, Eye, FileCheck2, Gauge, LayoutDashboard,
  LoaderCircle, LockKeyhole, LogOut, Menu, Moon, Search, Send, Settings as SettingsIcon,
  Shield, ShieldAlert, ShieldCheck, Sparkles, Sun, TrendingUp, TriangleAlert, UserRound,
  UsersRound, WalletCards, X, XCircle,
} from 'lucide-react'
import { api, getLedgerWithTransactions, session } from './lib/api'

const AuthContext = createContext(null)
const TEST_ACCOUNT = {
  username: 'eso_demo',
  email: 'demo@eso.ng',
  password: 'EsoDemo123!',
}
const naira = new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN', maximumFractionDigits: 0 })
const compactNaira = new Intl.NumberFormat('en-NG', { notation: 'compact', style: 'currency', currency: 'NGN' })
const statusMap = {
  approved: { label: 'Approved', tone: 'safe' },
  flagged: { label: 'Flagged', tone: 'warning' },
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
  const useTestAccount = async () => {
    setMode('login'); setForm(TEST_ACCOUNT); setError(''); setBusy(true)
    try {
      await login({ username: TEST_ACCOUNT.username, password: TEST_ACCOUNT.password })
    } catch {
      try {
        await register(TEST_ACCOUNT)
      } catch (err) {
        setError(err.message)
      }
    } finally { setBusy(false) }
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
        <div className="test-account">
          <div className="test-account-head"><span><Sparkles size={15} /> Hackathon test account</span><small>Creates itself on first use</small></div>
          <div className="test-credentials"><span><small>Username</small><code>{TEST_ACCOUNT.username}</code></span><span><small>Password</small><code>{TEST_ACCOUNT.password}</code></span></div>
          <button className="button secondary full" type="button" disabled={busy} onClick={useTestAccount}>{busy ? <LoaderCircle className="spin" size={17} /> : <UserRound size={17} />}Use test account</button>
        </div>
        <small className="auth-note"><LockKeyhole size={13} /> Your session is protected with secure access tokens.</small>
      </div>
    </section>
  </main>
}

const navItems = [
  ['/', 'Dashboard', LayoutDashboard], ['/send', 'Send Money', Send],
  ['/ledger', 'Transparency Ledger', WalletCards], ['/settings', 'Settings', SettingsIcon],
]

function Shell({ children }) {
  const location = useLocation(); const { user, logout } = useAuth(); const [open, setOpen] = useState(false)
  return <div className="app-shell">
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="side-head"><Brand /><button className="icon-button mobile-only" onClick={() => setOpen(false)}><X /></button></div>
      <nav>{navItems.map(([path, label, Icon]) => <Link key={path} to={path} className={location.pathname === path ? 'active' : ''} onClick={() => setOpen(false)}><Icon size={20} />{label}</Link>)}</nav>
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
  const approved = unique.filter((t) => t.status === 'approved').length
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

function SendMoney() {
  const navigate = useNavigate(); const [stage, setStage] = useState('form'); const [transaction, setTransaction] = useState(null)
  const [form, setForm] = useState({ recipient: '', bank: '', account: '', amount: '', description: '' }); const [error, setError] = useState(''); const [progress, setProgress] = useState(0)
  const update = (key) => (event) => setForm((value) => ({ ...value, [key]: event.target.value }))
  const submit = async (event) => {
    event.preventDefault(); setError(''); setStage('analysing'); setProgress(12)
    const timer = window.setInterval(() => setProgress((p) => Math.min(p + 17, 89)), 280)
    try {
      const result = await api.createTransaction({ recipient: form.recipient, amount: Number(form.amount), device_id: navigator.userAgent.slice(0, 150) })
      setTransaction(result); setProgress(100); await new Promise((resolve) => setTimeout(resolve, 450)); setStage(result.status === 'flagged' ? 'flagged' : 'approved')
    } catch (err) { setError(err.message); setStage('form') } finally { clearInterval(timer) }
  }
  const decide = async (decision) => {
    setStage('analysing'); setProgress(92)
    try { const result = await api.decideTransaction(transaction.id, decision); setTransaction(result); setStage(decision === 'confirm' ? 'confirmed' : 'cancelled') }
    catch (err) { setError(err.message); setStage('flagged') }
  }
  const reset = () => { setTransaction(null); setForm({ recipient: '', bank: '', account: '', amount: '', description: '' }); setStage('form'); setProgress(0) }
  if (stage === 'analysing') return <Analysis progress={progress} cancel={() => setStage(transaction ? 'flagged' : 'form')} />
  if (stage === 'flagged') return <Intervention transaction={transaction} onConfirm={() => decide('confirm')} onCancel={() => decide('cancel')} error={error} />
  if (['approved', 'confirmed', 'cancelled'].includes(stage)) return <TransferResult type={stage} transaction={transaction} onReset={reset} onLedger={() => navigate('/ledger')} />
  return <>
    <PageHeading eyebrow="NEW TRANSFER" title="Send money" copy="Eso analyses each transfer in real time before it leaves your account." />
    <section className="transfer-layout">
      <form className="card transfer-form" onSubmit={submit}>
        <div className="form-step"><span>1</span><div><b>Recipient details</b><small>Who are you sending money to?</small></div></div>
        <div className="form-grid">
          <label className="span-2">Recipient name<input required value={form.recipient} onChange={update('recipient')} placeholder="Enter their full name" /></label>
          <label>Bank<select required value={form.bank} onChange={update('bank')}><option value="">Select bank</option>{banks.map((bank) => <option key={bank}>{bank}</option>)}</select></label>
          <label>Account number<input required inputMode="numeric" pattern="[0-9]{10}" maxLength="10" value={form.account} onChange={update('account')} placeholder="0123456789" /></label>
        </div>
        <hr />
        <div className="form-step"><span>2</span><div><b>Transfer details</b><small>How much would you like to send?</small></div></div>
        <label>Amount (NGN)<div className="money-input"><span>₦</span><input required min="100" step="100" type="number" value={form.amount} onChange={update('amount')} placeholder="0.00" /></div><small className="balance">Demo balance · ₦1,240,500.00</small></label>
        <label>Description <i>Optional</i><input value={form.description} onChange={update('description')} placeholder="What is this transfer for?" /></label>
        {error && <div className="form-error"><TriangleAlert size={17} />{error}</div>}
        <button className="button primary full" type="submit">Review with Eso <ArrowRight size={18} /></button>
      </form>
      <aside className="transfer-aside"><div className="guardian-visual"><span><ShieldCheck /></span><i className="orbit o1" /><i className="orbit o2" /></div><span className="eyebrow">ESO GUARDIAN</span><h2>Protection without the friction.</h2><p>Routine transfers move quietly. When something breaks your normal pattern, Eso explains exactly why before you decide.</p><div className="aside-points"><span><Check /> Behaviour-aware scoring</span><span><Check /> Plain-language warnings</span><span><Check /> Every decision recorded</span></div></aside>
    </section>
  </>
}

function Analysis({ progress, cancel }) {
  const checks = ['Recipient history', 'Amount pattern', 'Behaviour profile', 'Time analysis', 'Fraud signals']
  return <div className="flow-wrap"><div className="analysis-card card"><div className="analysis-shield"><ShieldCheck /></div><span className="eyebrow muted">AI TRANSACTION ANALYSIS</span><h1>Analysing your transfer</h1><p>Eso is comparing this transfer with your usual behaviour.</p><div className="analysis-progress"><span style={{ width: `${progress}%` }} /></div><b className="progress-label">{progress}% complete</b><div className="check-list">{checks.map((check, i) => { const done = progress >= (i + 1) * 18; return <div key={check} className={done ? 'done' : ''}>{done ? <Check /> : <LoaderCircle className="spin" />}<span>{check}</span></div> })}</div><button className="button secondary full" onClick={cancel}><X size={17} /> Cancel analysis</button></div></div>
}

function reasonList(reason = '') {
  const parts = reason.split(/[,.;]\s*/).filter((part) => part.length > 3)
  return parts.length ? parts.slice(0, 3) : ['This transfer differs from your usual behaviour.']
}

function Intervention({ transaction, onConfirm, onCancel, error }) {
  return <div className="intervention-page"><div className="intervention-card card"><div className="warning-mark"><ShieldAlert /></div><span className="eyebrow amber">ESO INTERVENTION</span><h1>Hold on</h1><p className="lead">This transfer looks unusual.</p><RiskRing value={transaction.risk_score} tone="amber" />
    <section className="reasons"><span className="eyebrow muted">WHY WAS THIS FLAGGED?</span><h2>Here’s what Eso noticed</h2>{reasonList(transaction.risk_reason).map((reason, i) => <div key={reason}><span>{i === 0 ? <UserRound /> : i === 1 ? <TrendingUp /> : <Clock3 />}</span><p>{reason}</p></div>)}</section>
    <section className="decision-copy"><b>Before you decide</b><p>Confirm that you know and trust this recipient. Completed bank transfers can be difficult to reverse.</p></section>
    {error && <div className="form-error"><TriangleAlert size={17} />{error}</div>}
    <div className="decision-actions"><button className="button secondary" onClick={onConfirm}>Proceed anyway</button><button className="button primary" onClick={onCancel}><XCircle size={18} /> Cancel transfer</button></div>
  </div></div>
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
  const exportLedger = () => { const blob = new Blob([JSON.stringify(items, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `eso-ledger-${new Date().toISOString().slice(0, 10)}.json`; a.click(); URL.revokeObjectURL(url) }
  return <>
    <PageHeading eyebrow="AUDIT TRAIL" title="Transparency ledger" copy="Every AI assessment and user decision is recorded here." action={<button className="button secondary" onClick={exportLedger}><Download size={17} />Export records</button>} />
    <div className="ledger-toolbar"><div className="ledger-search"><Search size={18} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search recipient or transaction ID" /></div><div className="filter-tabs">{[['all','All'],['approved','Approved'],['flagged','Flagged'],['confirmed','Overrides'],['cancelled','Cancelled']].map(([value,label]) => <button key={value} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)}>{label}<span>{value === 'all' ? unique.length : unique.filter((t) => t.status === value).length}</span></button>)}</div></div>
    <div className="ledger-layout"><aside className="card ledger-summary"><span className="eyebrow muted">YOUR RECORD</span><h3>Decision overview</h3><div className="ledger-stat"><span>Transfers analysed</span><b>{unique.length}</b></div><div className="ledger-stat safe"><span>Approved</span><b>{unique.filter((t) => t.status === 'approved').length}</b></div><div className="ledger-stat warning"><span>Flagged / override</span><b>{unique.filter((t) => ['flagged','confirmed'].includes(t.status)).length}</b></div><div className="ledger-stat danger"><span>Cancelled</span><b>{unique.filter((t) => t.status === 'cancelled').length}</b></div><div className="tamper-note"><LockKeyhole /><p><b>Tamper-evident record</b><small>Eso preserves a clear trail of how every decision was made.</small></p></div></aside>
      <section className="ledger-list">{loading ? <div className="card"><LoadingRows /></div> : filtered.length ? filtered.map((t) => <LedgerCard key={t.id} transaction={t} expanded={expanded === t.id} toggle={() => setExpanded(expanded === t.id ? null : t.id)} />) : <div className="card"><EmptyState icon={Search} title="No matching entries" copy="Try another filter or make a transfer to create a record." /></div>}</section></div>
  </>
}

function LedgerCard({ transaction: t, expanded, toggle }) {
  const meta = statusMap[t.status] || statusMap.pending
  return <article className={`card ledger-card ${meta.tone}`}><button className="ledger-card-main" onClick={toggle}><span className={`ledger-event-icon ${meta.tone}`}>{meta.tone === 'safe' ? <Check /> : meta.tone === 'danger' ? <X /> : <TriangleAlert />}</span><div className="ledger-primary"><div><b>{naira.format(t.amount)}</b><StatusPill status={t.status} /></div><p>to {t.recipient}</p><small>{new Date(t.created_at).toLocaleString('en-NG', { dateStyle: 'long', timeStyle: 'short' })}</small></div><div className="ledger-risk"><RiskRing value={t.risk_score} tone={meta.tone === 'danger' ? 'red' : meta.tone === 'warning' ? 'amber' : 'green'} size="small" /><ChevronDown className={expanded ? 'rotate' : ''} /></div></button>{expanded && <div className="ledger-detail"><div><span className="eyebrow muted"><BrainCircuit size={14} /> AI REASONING</span><p>{t.risk_reason || 'This transaction matched the user’s learned behaviour profile.'}</p></div><div><span className="eyebrow muted">TRANSACTION ID</span><code>{t.id}</code><button className="copy-button" onClick={() => navigator.clipboard.writeText(t.id)}><Copy size={14} /> Copy</button></div></div>}</article>
}

function SettingsPage() {
  const { user, logout } = useAuth(); const [baseline, setBaseline] = useState(null); const [level, setLevel] = useState(localStorage.getItem('eso_protection') || 'guardian'); const [prefs, setPrefs] = useState({ anomalies: true, weekly: true, routine: false }); const [dark, setDark] = useState(document.documentElement.dataset.theme === 'dark')
  useEffect(() => { api.baseline().then(setBaseline).catch(() => {}) }, [])
  const chooseLevel = (next) => { setLevel(next); localStorage.setItem('eso_protection', next) }
  const toggleDark = () => { const next = !dark; setDark(next); document.documentElement.dataset.theme = next ? 'dark' : ''; localStorage.setItem('eso_theme', next ? 'dark' : 'light') }
  return <>
    <PageHeading eyebrow="PREFERENCES" title="Settings" copy="Manage your profile, guardian behaviour and notifications." />
    <div className="settings-grid">
      <section className="card settings-card"><div className="settings-title"><span><UserRound /></span><div><h2>Profile information</h2><p>Your Eso account and protection status.</p></div></div><div className="profile-row"><span className="avatar large">{user.username[0].toUpperCase()}</span><div><span className="status-dot safe">FULLY VERIFIED</span><h3>{user.username}</h3><p>{user.email || 'No email supplied'}</p></div></div></section>
      <section className="card settings-card span-2"><div className="settings-title"><span><Shield /></span><div><h2>AI security protocol</h2><p>Choose how assertively Eso monitors unusual behaviour.</p></div></div><div className="protection-levels">{[['standard','Standard','Known malicious patterns only.'],['guardian','Guardian','Recommended. Learns your habits and challenges anomalies.'],['maximum','Maximum','Every new recipient requires review.']].map(([value,title,copy]) => <button key={value} className={level === value ? 'active' : ''} onClick={() => chooseLevel(value)}><span>{level === value && <Check />}</span><b>{title}</b><p>{copy}</p></button>)}</div><div className="baseline-line"><span><b>Behaviour profile</b><small>{baseline ? `${baseline.typical_recipients.length} known recipients · typical ceiling ${compactNaira.format(baseline.typical_amount_max)}` : 'Loading learned baseline…'}</small></span><BrainCircuit /></div></section>
      <section className="card settings-card span-2"><div className="settings-title"><span><Bell /></span><div><h2>AI notifications</h2><p>Control when the guardian communicates with you.</p></div></div>{[['anomalies','Anomaly alerts','Unusual spending patterns and high-risk transfers.'],['weekly','Weekly protection summary','A concise report of activity and interventions.'],['routine','Routine confirmations','Notifications for normal, recurring transfers.']].map(([key,title,copy]) => <div className="toggle-row" key={key}><span><b>{title}</b><small>{copy}</small></span><button className={`toggle ${prefs[key] ? 'on' : ''}`} onClick={() => setPrefs((p) => ({ ...p, [key]: !p[key] }))}><i /></button></div>)}</section>
      <section className="card setting-action"><span className="settings-action-icon"><Download /></span><h3>Transparency records</h3><p>Your full decision history is available from the ledger.</p><a className="button primary full" href="/ledger">Open ledger</a></section>
      <section className="card setting-action"><span className="settings-action-icon"><Moon /></span><h3>Appearance</h3><p>Use the interface that is most comfortable for you.</p><button className="button secondary full" onClick={toggleDark}>{dark ? <Sun size={17} /> : <Moon size={17} />}{dark ? 'Use light mode' : 'Use dark mode'}</button></section>
      <section className="card settings-footer span-2"><span><LockKeyhole /><div><b>Signed in securely</b><small>Sign out of Eso on this device.</small></div></span><button className="button danger" onClick={logout}><LogOut size={17} />Sign out</button></section>
    </div>
  </>
}

function App() {
  useEffect(() => { document.documentElement.dataset.theme = localStorage.getItem('eso_theme') === 'dark' ? 'dark' : '' }, [])
  return <AuthProvider><Routes><Route path="/login" element={<AuthGate />} /><Route path="*" element={<Protected><Shell><Routes><Route path="/" element={<Dashboard />} /><Route path="/send" element={<SendMoney />} /><Route path="/ledger" element={<Ledger />} /><Route path="/settings" element={<SettingsPage />} /><Route path="*" element={<Navigate to="/" replace />} /></Routes></Shell></Protected>} /></Routes></AuthProvider>
}
function AuthGate() { const { user, loading } = useAuth(); if (loading) return <div className="splash"><Brand /><LoaderCircle className="spin" /></div>; return user ? <Navigate to="/" replace /> : <AuthPage /> }

export default App
