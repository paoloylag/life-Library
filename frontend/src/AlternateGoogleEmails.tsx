import React from 'react'
import {apiRequest} from './api'

type Approval={email:string;is_active:boolean}
export default function AlternateGoogleEmails({number}:{number:string}){
 const[rows,setRows]=React.useState<Approval[]>([]),[email,setEmail]=React.useState(''),[busy,setBusy]=React.useState(false),[error,setError]=React.useState('')
 const path='/api/library/users/'+encodeURIComponent(number)
 React.useEffect(()=>{apiRequest<Approval[]>(path+'/alternate-google-emails').then(setRows).catch(reason=>setError(reason.message))},[path])
 async function save(value:string,active:boolean){setBusy(true);setError('');try{await apiRequest(path+'/alternate-google-email',{method:'PUT',body:JSON.stringify({email:value,is_active:active})});setRows(await apiRequest<Approval[]>(path+'/alternate-google-emails'));setEmail('')}catch(reason){setError(reason instanceof Error?reason.message:'Unable to update alternate email')}finally{setBusy(false)}}
 return <div className="wide"><label>Approved alternate Google email<input type="email" value={email} onChange={event=>setEmail(event.target.value)}/></label><button type="button" className="secondary-button" disabled={busy||!email.trim()} onClick={()=>void save(email,true)}>Approve email</button>{rows.map(row=><div key={row.email}><span>{row.email} ({row.is_active?'Approved':'Revoked'})</span> <button type="button" className="secondary-button" disabled={busy} onClick={()=>void save(row.email,!row.is_active)}>{row.is_active?'Revoke':'Approve'}</button></div>)}{error&&<p className="module-error" role="alert">{error}</p>}</div>
}
