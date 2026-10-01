import { useState, type FormEvent } from 'react'
import { ArrowRight, SealCheck } from '@phosphor-icons/react'
import { loginAccount, registerAccount, type Account } from './api/ragClient'

type Props = {
  onAuthenticated: (account: Account) => void
  onFixture: () => void
  notice?: string
}

export default function AccountGate({ onAuthenticated, onFixture, notice = '' }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const account = mode === 'login'
        ? await loginAccount(username, password)
        : await registerAccount(username, password)
      setPassword('')
      onAuthenticated(account)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Không thể xác thực tài khoản.')
    } finally {
      setBusy(false)
    }
  }

  return <main className="account-gate">
    <form className="account-form" onSubmit={(event) => void submit(event)}>
      <div className="account-brand"><SealCheck size={25} weight="fill" /><span>Trợ lý hành chính<small>Không gian hội thoại riêng</small></span></div>
      <h1>{mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản'}</h1>
      <label>Tên tài khoản<input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} minLength={3} maxLength={32} required /></label>
      <label>Mật khẩu<input type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} onChange={(event) => setPassword(event.target.value)} minLength={12} maxLength={128} required /></label>
      {error && <p className="account-error" role="alert">{error}</p>}
      {notice && <p className="account-notice" role="status">{notice}</p>}
      <button className="account-submit" type="submit" disabled={busy}>{mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản'}<ArrowRight size={18} /></button>
      <button className="account-switch" type="button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>
        {mode === 'login' ? 'Chưa có tài khoản? Tạo tài khoản' : 'Đã có tài khoản? Đăng nhập'}
      </button>
      {import.meta.env.DEV && <button className="fixture-entry" type="button" onClick={onFixture}>Mở fixture sandbox cục bộ</button>}
    </form>
  </main>
}
