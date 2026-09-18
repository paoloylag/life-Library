import React from 'react'
import {BookOpen, LogIn} from 'lucide-react'
import {apiRequest} from './api'

export type LibrarianSession={id:number;name:string;email:string;role:'admin'|'librarian'|'auditor'}
type DevAccount={role:string;name:string;email:string;password:string}

function DevLoginAs({onSelect}:{onSelect:(account:DevAccount)=>void}){
 const[accounts,setAccounts]=React.useState<DevAccount[]>([])
 React.useEffect(()=>{
  if(!import.meta.env.DEV)return
  apiRequest<{accounts:DevAccount[]}>('/api/admin/dev-accounts')
   .then(value=>setAccounts(value.accounts)).catch(()=>setAccounts([]))
 },[])
 if(!accounts.length)return null
 return <label className="dev-login-as">Login as<select value="" onChange={event=>{const account=accounts.find(item=>item.role===event.target.value);if(account)onSelect(account)}}><option value="">Select a development role</option>{accounts.map(item=><option value={item.role} key={item.role}>{item.name}</option>)}</select></label>
}

export default function LoginPage({onLogin}:{onLogin:(session:LibrarianSession)=>void}){
 const[email,setEmail]=React.useState(''),[password,setPassword]=React.useState('')
 const[error,setError]=React.useState(''),[busy,setBusy]=React.useState(false)
 async function submit(event:React.FormEvent){
  event.preventDefault();setBusy(true);setError('')
  try{
   await apiRequest('/api/admin/login',{method:'POST',body:JSON.stringify({email,password})})
   onLogin(await apiRequest<LibrarianSession>('/api/admin/me'))
  }catch(reason){setError(reason instanceof Error?reason.message:'Sign-in failed')}
  finally{setBusy(false)}
 }
 return <main className="librarian-login"><form onSubmit={submit} className="librarian-login-form">
  <div className="librarian-login-brand"><BookOpen size={30}/><span><strong>Life College</strong><small>Library Attendance</small></span></div>
  <h1>Librarian sign-in</h1><p>Sign in to manage library attendance.</p>
  <label>Email<input type="email" autoComplete="username" value={email} onChange={event=>setEmail(event.target.value)} required/></label>
  <label>Password<input type="password" autoComplete="current-password" value={password} onChange={event=>setPassword(event.target.value)} required/></label>
  {error&&<p role="alert" className="librarian-login-error">{error}</p>}
  <button disabled={busy} type="submit"><LogIn size={17}/>{busy?'Signing in...':'Sign in'}</button>
  <DevLoginAs onSelect={account=>{setEmail(account.email);setPassword(account.password)}}/>
 </form></main>
}
