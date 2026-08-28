import React from 'react'
import {AlertCircle, ArrowLeft, Building2, Check, CheckCircle2, Clock3, GraduationCap, LoaderCircle, LogIn, ShieldCheck, UserRound, Users} from 'lucide-react'
import {SeedUser, UserType, users} from './data'
import {loadSettings} from './settings'

const BASE=import.meta.env.BASE_URL
const href=(path:string)=>BASE+(path==='/'?'':path.replace(/^\//,''))

type Result={action:'check_in'|'duplicate';at:string;user:SeedUser;organization?:string;purpose?:string;reference:string}
type LastScan={lastScan:string}
const types:UserType[]=['Student','Faculty','Non-Teaching','Visitor']
const labels:Record<UserType,string>={Student:'Student',Faculty:'Faculty','Non-Teaching':'Non-teaching',Visitor:'Visitor'}
const icons:Record<UserType,React.ComponentType<{size?:number}>>={Student:GraduationCap,Faculty:Users,'Non-Teaching':Building2,Visitor:UserRound}

export default function ScanPage(){
 const settings=loadSettings(),params=new URLSearchParams(location.search),expires=Number(params.get('expires')||0)
 const expired=Boolean(expires&&expires<Date.now())
 const[type,setType]=React.useState<UserType>('Student'),[selected,setSelected]=React.useState('')
 const[visitor,setVisitor]=React.useState({name:'',organization:'',purpose:''}),[loading,setLoading]=React.useState(false),[result,setResult]=React.useState<Result|null>(null)
 const available=users.filter(u=>u.userType===type),active=available.find(u=>u.number===selected)||available[0]
 React.useEffect(()=>setSelected(''),[type])
 function record(user:SeedUser,extra?:{organization:string;purpose:string}){
  setLoading(true);setTimeout(()=>{
   const now=new Date(),key='scan-last-'+user.number,stored=JSON.parse(localStorage.getItem(key)||'null') as LastScan|null
   const duplicate=stored&&(now.getTime()-new Date(stored.lastScan).getTime())<settings.duplicateWindowMinutes*60000
   let action:Result['action']='check_in'
   if(duplicate)action='duplicate'
   else localStorage.setItem(key,JSON.stringify({lastScan:now.toISOString()}))
   const receipt={action,at:now.toISOString(),user,...extra,reference:'LC-'+now.getFullYear()+'-'+String(now.getTime()).slice(-6)} as Result
   const history=JSON.parse(localStorage.getItem('scan-history')||'[]');history.unshift(receipt);localStorage.setItem('scan-history',JSON.stringify(history.slice(0,100)))
   setResult(receipt);setLoading(false)
  },700)
 }
 if(expired)return <ScanFrame><div className="scan-state"><span className="scan-state-icon error"><AlertCircle size={34}/></span><span className="eyebrow">Code expired</span><h1>This QR code is no longer active</h1><p>Please scan the current code displayed at the library entrance.</p><button className="scan-secondary" onClick={()=>location.reload()}>Try again</button></div></ScanFrame>
 if(result)return <Success result={result}/>
 return <ScanFrame><div className="scan-heading"><span className="eyebrow">Secure attendance</span><h1>Verify your identity</h1><p>Select your user type to continue with today’s library attendance.</p></div><div className="type-tabs" role="tablist">{types.map(t=>{const Icon=icons[t];return <button key={t} type="button" className={type===t?'active':''} onClick={()=>setType(t)}><Icon size={18}/><span>{labels[t]}</span></button>})}</div>{type==='Visitor'?<form className="scan-form" onSubmit={e=>{e.preventDefault();record({name:visitor.name,number:'VIS-'+Date.now().toString().slice(-6),userType:'Visitor',program:'',yearLevel:'',section:'',department:'External Visitor'},{organization:visitor.organization,purpose:visitor.purpose})}}><label>Full name<input value={visitor.name} onChange={e=>setVisitor(v=>({...v,name:e.target.value}))} required autoComplete="name"/></label><label>Organization<input value={visitor.organization} onChange={e=>setVisitor(v=>({...v,organization:e.target.value}))} required/></label><label>Purpose of visit<select value={visitor.purpose} onChange={e=>setVisitor(v=>({...v,purpose:e.target.value}))} required><option value="">Select purpose</option><option>Research and study</option><option>Borrow or return materials</option><option>Meeting or official business</option><option>Library tour</option><option>Other</option></select></label><button className="scan-primary" disabled={loading}>{loading?<LoaderCircle className="spin" size={19}/>:<Check size={19}/>}Register and record visit</button></form>:<div className="school-verify"><div className="demo-notice"><ShieldCheck size={18}/><span><strong>Google SSO preview</strong>This identity selector represents the account returned by Google while OAuth is being configured.</span></div><label className="account-select">Preview account<select value={active?.number||''} onChange={e=>setSelected(e.target.value)}>{available.map(u=><option value={u.number} key={u.number}>{u.name} · {u.number}</option>)}</select></label>{active&&<Identity user={active}/>}<button className="scan-primary google" onClick={()=>active&&record(active)} disabled={loading}>{loading?<LoaderCircle className="spin" size={19}/>:<span className="google-g">G</span>}Continue with Google</button><small className="privacy-note">Only your school identity and library profile are used for attendance.</small></div>}</ScanFrame>
}
function ScanFrame({children}:{children:React.ReactNode}){return <main className="scan-page"><header><button onClick={()=>location.assign(href('/'))} title="Back"><ArrowLeft size={19}/></button><div className="scan-brand"><img src={BASE+"lifeos-platform-crest.svg"} alt="Life College"/><span><strong>Life College</strong><small>Library Attendance</small></span></div><span className="secure-label"><ShieldCheck size={15}/>Secure</span></header><section className="scan-card">{children}</section><footer>Life College Library · Powered by LifeOS</footer></main>}
function Identity({user}:{user:SeedUser}){return <div className="identity-card"><span className="identity-avatar">{user.name.split(' ').map(x=>x[0]).slice(0,2).join('')}</span><div><strong>{user.name}</strong><small>{user.number}</small><p>{user.userType==='Student'?[user.program,user.yearLevel,user.section].filter(Boolean).join(' · '):user.department}</p></div><CheckCircle2 size={21}/></div>}
function Success({result}:{result:Result}){const duplicate=result.action==='duplicate',Icon=duplicate?Clock3:LogIn;const title=duplicate?'Attendance already recorded':'Check-in recorded';const detail=result.user.userType==='Student'?[result.user.program,result.user.yearLevel,result.user.section].filter(Boolean).join(' · '):result.user.userType==='Visitor'?[result.organization,result.purpose].filter(Boolean).join(' · '):result.user.department;return <ScanFrame><div className="scan-success"><span className={'success-mark '+(duplicate?'duplicate':'')}><Icon size={34}/></span><span className="eyebrow">{duplicate?'No changes made':'Attendance confirmed'}</span><h1>{title}</h1><p>{duplicate?'Your previous scan is still within the duplicate-scan window.':'Welcome to the Life College Library.'}</p><Identity user={result.user}/><dl><div><dt>User type</dt><dd>{labels[result.user.userType]}</dd></div><div><dt>Check-in time</dt><dd>{new Date(result.at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'})}</dd></div><div><dt>Date</dt><dd>{new Date(result.at).toLocaleDateString(undefined,{month:'long',day:'numeric',year:'numeric'})}</dd></div><div><dt>Reference</dt><dd>{result.reference}</dd></div>{detail&&<div className="wide"><dt>Profile</dt><dd>{detail}</dd></div>}</dl><button className="scan-secondary" onClick={()=>location.assign(href('/'))}>Done</button></div></ScanFrame>}
