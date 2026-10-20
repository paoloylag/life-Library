import React from 'react'
import {AlertTriangle,RefreshCw} from 'lucide-react'
import {apiRequest} from './api'
import './calendar-conflict-warning.css'

type State='clear'|'conflict'|'unavailable'|'not_connected'|'disabled'
type Notice={state:'conflict'|'unavailable';key:string;checkedAt:number}
export function useCalendarConflictCheck(resourceId:number,start:string|null,manual:boolean){
 const key=JSON.stringify([resourceId,start,manual])
 const current=React.useRef(key);current.current=key
 const[notice,setNotice]=React.useState<Notice|null>(null)
 const[checking,setChecking]=React.useState(false)
 React.useEffect(()=>setNotice(null),[key])
 const active=notice?.key===key?notice:null
 async function check(force=false){
  if(manual)return true
  if(!force&&active&&Date.now()-active.checkedAt<30000){setNotice(null);return true}
  let state:State='unavailable'
  setChecking(true)
  try{
   const result=await apiRequest<{state:State}>('/api/calendar/conflicts',{method:'POST',body:JSON.stringify({resource_id:resourceId,starts_at:start})})
   if(['clear','conflict','unavailable','not_connected','disabled'].includes(result.state))state=result.state
  }catch{/* A failed calendar check must not prevent a library booking. */}finally{setChecking(false)}
  if(current.current!==key)return false
  if(state==='conflict'||state==='unavailable'){
   setNotice({state,key,checkedAt:Date.now()});return false
  }
  setNotice(null);return true
 }
 return {notice:active,check,confirmLabel:checking?'Checking Calendar...':active?.state==='conflict'?'Book Anyway':active?'Book Without Check':'Confirm booking'}
}

export default function CalendarConflictWarning({state,busy,onRetry}:{state:'conflict'|'unavailable';busy:boolean;onRetry:()=>void}){
 return <div className="calendar-conflict-warning" role="alert"><AlertTriangle size={20} aria-hidden="true"/><div><strong>{state==='conflict'?'Google Calendar Conflict':'Calendar Check Unavailable'}</strong><p>{state==='conflict'?'Your primary Google Calendar has a busy event overlapping this session. Choose another time, or select Book Anyway to continue.':'We could not check your Google Calendar. You can retry, or book without the calendar check.'}</p><button type="button" className="secondary-button" disabled={busy} onClick={onRetry}><RefreshCw size={16}/>Retry Calendar Check</button></div></div>
}
