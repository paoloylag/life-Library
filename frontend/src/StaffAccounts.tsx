import React from 'react'
import StaffRolePicker from './StaffRolePicker'
import {Plus, ShieldCheck, X} from 'lucide-react'
import {apiRequest} from './api'
import {staffRoleName} from './LoginPage'
import type {LibrarianSession} from './LoginPage'
import BookingUserPicker from './BookingUserPicker'
import type {ApiUser} from './api'

type Staff = LibrarianSession & {is_active:boolean;is_development:boolean}
type Role = Staff['role']

export default function StaffAccounts({current}:{current:LibrarianSession}){
 const[accounts,setAccounts]=React.useState<Staff[]>([])
 const[error,setError]=React.useState('')
 const[editing,setEditing]=React.useState<Staff|null|undefined>(undefined)
 const[busy,setBusy]=React.useState(false)
 const[granting,setGranting]=React.useState(false)
 const roles:Role[]=current.role==='librarian'?['librarian','librarian_associate','auditor','qr_display']:['librarian_associate','auditor','qr_display']
 const load=React.useCallback(()=>apiRequest<{items:Staff[]}>('/api/admin/accounts').then(result=>{setAccounts(result.items);setError('')}).catch(reason=>setError(reason.message)),[])
 React.useEffect(()=>{void load()},[load])
 return <div className="module-stack staff-page">
  <div className="module-heading"><div><h2>Administration</h2><p>Manage access to the library dashboard.</p></div><div className="booking-actions">{current.role==='librarian'&&<button className="secondary-button" onClick={()=>setGranting(true)}><ShieldCheck size={17}/>Grant Google access</button>}<button className="manual-button" onClick={()=>setEditing(null)}><Plus size={17}/>Add Account</button></div></div>
  <section className="panel">
   {error&&<p className="module-error" role="alert">{error}</p>}
   <div className="table-wrap"><table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead>
    <tbody>{accounts.map(account=><tr key={account.id}><td><strong>{account.name}</strong>{account.is_development&&<small>Development account</small>}</td><td>{account.email}</td><td>{staffRoleName(account.role)}</td><td><span className={account.is_active?'badge inside':'badge'}>{account.is_active?'Active':'Inactive'}</span></td><td><button className="row-action" title={account.is_development?'Development account cannot be edited':`Edit ${account.name}`} disabled={account.is_development||current.role!=='librarian'&&account.role==='librarian'} onClick={()=>setEditing(account)}><ShieldCheck size={17}/></button></td></tr>)}</tbody>
   </table></div>
  </section>
  {editing!==undefined&&<StaffEditor account={editing} current={current} roles={roles} busy={busy} setBusy={setBusy} close={()=>setEditing(undefined)} saved={()=>{setEditing(undefined);void load()}}/>}
  {granting&&<GoogleAccessEditor close={()=>setGranting(false)} saved={()=>{setGranting(false);void load()}}/>}
 </div>
}

function GoogleAccessEditor({close,saved}:{close:()=>void;saved:()=>void}){
 const[user,setUser]=React.useState<ApiUser|null>(null)
 const[role,setRole]=React.useState<Role>('librarian_associate')
 const[busy,setBusy]=React.useState(false),[error,setError]=React.useState('')
 const ref=React.useRef<HTMLDialogElement>(null)
 React.useEffect(()=>{ref.current?.showModal()},[])
 return <dialog ref={ref} className="manual-modal resource-policy-modal google-access-modal" aria-labelledby="google-access-title" onCancel={event=>{event.preventDefault();if(!busy)close()}}><form onSubmit={async event=>{event.preventDefault();if(!user)return;setBusy(true);setError('');try{await apiRequest('/api/admin/google-access',{method:'POST',body:JSON.stringify({number:user.number,role})});saved()}catch(reason){setError(reason instanceof Error?reason.message:'Unable to grant access')}finally{setBusy(false)}}}><header><div><span className="eyebrow">Staff permissions</span><h3 id="google-access-title">Grant Google access</h3></div><button type="button" className="icon-button" aria-label="Close Google access form" disabled={busy} onClick={close}><X size={18}/></button></header><div className="resource-policy-body"><div className="google-access-user"><span className="google-access-label">Library user</span><BookingUserPicker value={user} onSelect={setUser}/></div><StaffRolePicker value={role} onChange={setRole}/>{error&&<p className="module-error" role="alert">{error}</p>}</div><footer><button type="button" className="secondary-button" disabled={busy} onClick={close}>Cancel</button><button className="primary-button" disabled={busy||!user}>{busy?'Saving...':'Grant access'}</button></footer></form></dialog>
}

function StaffEditor({account,current,roles,busy,setBusy,close,saved}:{account:Staff|null;current:LibrarianSession;roles:Role[];busy:boolean;setBusy:(value:boolean)=>void;close:()=>void;saved:()=>void}){
 const[name,setName]=React.useState(account?.name||'')
 const[email,setEmail]=React.useState(account?.email||'')
 const[password,setPassword]=React.useState('')
 const[role,setRole]=React.useState<Role>(account?.role||'librarian_associate')
 const[active,setActive]=React.useState(account?.is_active??true)
 const[error,setError]=React.useState('')
 async function submit(event:React.FormEvent){
  event.preventDefault();setBusy(true);setError('')
  try{
   if(account)await apiRequest(`/api/admin/accounts/${account.id}`,{method:'PATCH',body:JSON.stringify({role,is_active:active})})
   else await apiRequest('/api/admin/accounts',{method:'POST',body:JSON.stringify({name,email,password,role})})
   saved()
  }catch(reason){setError(reason instanceof Error?reason.message:'Unable to save account')}
  finally{setBusy(false)}
 }
 return <div className="modal-backdrop" onMouseDown={event=>{if(event.target===event.currentTarget)close()}}><form className="manual-modal" onSubmit={submit}>
  <header><div><span className="eyebrow">Staff access</span><h3>{account?'Edit account':'Add account'}</h3><p>{account?'Change this account’s access.':'Create credentials for a staff member.'}</p></div><button type="button" className="icon-button" title="Close" onClick={close}><X size={18}/></button></header>
  <div className="manual-form">
   <label>Name<input value={name} required minLength={2} disabled={!!account} onChange={event=>setName(event.target.value)}/></label>
   <label>Email<input value={email} required type="email" disabled={!!account} onChange={event=>setEmail(event.target.value)}/></label>
   {!account&&<label className="wide">Initial password<input value={password} required minLength={10} type="password" autoComplete="new-password" onChange={event=>setPassword(event.target.value)}/><small>At least 10 characters. Give this to the staff member privately.</small></label>}
   <label>Role<select value={role} disabled={account?.id===current.id} onChange={event=>setRole(event.target.value as Role)}>{roles.map(value=><option key={value} value={value}>{staffRoleName(value)}</option>)}</select></label>
   {account&&<label className="user-active"><input type="checkbox" checked={active} disabled={account.id===current.id} onChange={event=>setActive(event.target.checked)}/>Active</label>}
   {account?.id===current.id&&<small className="wide">You cannot remove your own access.</small>}
   {error&&<p className="module-error wide" role="alert">{error}</p>}
  </div>
  <footer><button type="button" className="secondary-button" onClick={close}>Cancel</button><button type="submit" className="primary-button save-button" disabled={busy}>{busy?'Saving...':'Save account'}</button></footer>
 </form></div>
}
