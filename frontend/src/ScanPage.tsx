import React from 'react'
import {AlertCircle, ArrowLeft, Building2, Check, CheckCircle2, Clock3, GraduationCap, LoaderCircle, LogIn, ShieldCheck, UserRound, Users} from 'lucide-react'
import {SeedUser, UserType} from './data'
import {loadSettings} from './settings'

const BASE=import.meta.env.BASE_URL
const href=(path:string)=>BASE+(path==='/'?'':path.replace(/^\//,''))
const configuredApi=(import.meta.env.VITE_API_URL||'').replace(/\/$/,'')
const backendEnabled=Boolean(configuredApi)||['localhost','127.0.0.1'].includes(location.hostname)
const api=(path:string)=>configuredApi+path

type AuthProfile={number:string;user_type:string;program:string;year_level:string;section:string;department:string}
type AuthUser={id:number;name:string;email:string;role:string;avatar_url?:string;profile:AuthProfile|null}
type Result={action:'check_in'|'duplicate';at:string;user:SeedUser;organization?:string;purpose?:string;reference:string}
type LastScan={lastScan:string}
const types:UserType[]=['Student','Faculty','Non-Teaching','Visitor']
const labels:Record<UserType,string>={Student:'Student',Faculty:'Faculty','Non-Teaching':'Non-teaching',Visitor:'Visitor'}
const icons:Record<UserType,React.ComponentType<{size?:number}>>={Student:GraduationCap,Faculty:Users,'Non-Teaching':Building2,Visitor:UserRound}

function profileUser(user:AuthUser):SeedUser|null{
 if(!user.profile)return null
 const raw=user.profile.user_type.toLowerCase()
 const userType:UserType=raw.includes('faculty')?'Faculty':raw.includes('non')?'Non-Teaching':'Student'
 return{name:user.name,number:user.profile.number,userType,program:user.profile.program,yearLevel:user.profile.year_level,section:user.profile.section,department:user.profile.department}
}

export default function ScanPage(){
 const settings=loadSettings(),params=new URLSearchParams(location.search),expires=Number(params.get('expires')||0)
 const expired=Boolean(expires&&expires<Date.now())
 const[type,setType]=React.useState<UserType>('Student'),[visitor,setVisitor]=React.useState({name:'',organization:'',purpose:''})
 const[loading,setLoading]=React.useState(false),[result,setResult]=React.useState<Result|null>(null)
 const[authUser,setAuthUser]=React.useState<AuthUser|null|undefined>(backendEnabled?undefined:null)
 const[error,setError]=React.useState(params.get('auth_error')?'Google authentication could not be completed. Please try again.':'')
 const token=decodeURIComponent(location.pathname.split('/scan/')[1]?.split('/')[0]||'')
 const verifiedUser=authUser?profileUser(authUser):null

 React.useEffect(()=>{
  if(!backendEnabled)return
  const controller=new AbortController(),timeout=window.setTimeout(()=>controller.abort(),8000)
  fetch(api('/api/auth/me'),{credentials:'include',signal:controller.signal})
   .then(async response=>{if(response.status===401)return null;if(!response.ok)throw new Error('Unable to verify your session');return response.json()})
   .then(setAuthUser)
   .catch(()=>{setAuthUser(null);setError('The authentication service could not be reached. Check your connection and try again.')})
   .finally(()=>clearTimeout(timeout))
  return()=>{clearTimeout(timeout);controller.abort()}
 },[])

 function recordVisitor(user:SeedUser,extra:{organization:string;purpose:string}){
  setLoading(true);setTimeout(()=>{
   const now=new Date(),key='scan-last-'+user.number,stored=JSON.parse(localStorage.getItem(key)||'null') as LastScan|null
   const duplicate=stored&&(now.getTime()-new Date(stored.lastScan).getTime())<settings.duplicateWindowMinutes*60000
   const action:Result['action']=duplicate?'duplicate':'check_in'
   if(!duplicate)localStorage.setItem(key,JSON.stringify({lastScan:now.toISOString()}))
   const receipt={action,at:now.toISOString(),user,...extra,reference:'LC-'+now.getFullYear()+'-'+String(now.getTime()).slice(-6)} as Result
   const history=JSON.parse(localStorage.getItem('scan-history')||'[]');history.unshift(receipt);localStorage.setItem('scan-history',JSON.stringify(history.slice(0,100)))
   setResult(receipt);setLoading(false)
  },700)
 }

 function startGoogle(){
  if(!backendEnabled)return
  const nextParams=new URLSearchParams(location.search);nextParams.delete('auth_error')
  const query=nextParams.toString()
  const next=`/scan/${encodeURIComponent(token)}${query?'?'+query:''}`
  location.assign(api('/api/auth/google?next='+encodeURIComponent(next)))
 }

 async function startLocal(){
  setLoading(true);setError('')
  try{
   const response=await fetch(api('/api/auth/dev-login'),{method:'POST',credentials:'include'})
   if(!response.ok)throw new Error('Local test sign-in is unavailable.')
   location.reload()
  }catch(reason){
   setError(reason instanceof Error?reason.message:'Local test sign-in is unavailable.')
   setLoading(false)
  }
 }

 async function recordAuthenticated(){
  if(!verifiedUser||!token)return
  setLoading(true);setError('')
  try{
   const response=await fetch(api('/api/library/scan/'+encodeURIComponent(token)),{method:'POST',credentials:'include'})
   const body=await response.json().catch(()=>({}))
   if(response.status===401){setAuthUser(null);throw new Error('Your Google session expired. Please sign in again.')}
   if(!response.ok)throw new Error(body.detail||'The attendance could not be recorded.')
   setResult({action:body.action,at:body.check_in_time,user:verifiedUser,reference:body.reference||'Pending'})
  }catch(reason){setError(reason instanceof Error?reason.message:'The attendance could not be recorded.')}finally{setLoading(false)}
 }

 if(expired)return <ScanFrame><div className="scan-state"><span className="scan-state-icon error"><AlertCircle size={34}/></span><span className="eyebrow">Code expired</span><h1>This QR code is no longer active</h1><p>Please scan the current code displayed at the library entrance.</p><button className="scan-secondary" onClick={()=>location.reload()}>Try again</button></div></ScanFrame>
 if(result)return <Success result={result}/>
 return <ScanFrame><div className="scan-heading"><span className="eyebrow">Secure attendance</span><h1>Verify your identity</h1><p>Select your user type to continue with today's library attendance.</p></div><div className="type-tabs" role="tablist">{types.map(t=>{const Icon=icons[t];return <button key={t} type="button" className={type===t?'active':''} onClick={()=>{setType(t);setError('')}}><Icon size={18}/><span>{labels[t]}</span></button>})}</div>{error&&<div className="scan-error" role="alert"><AlertCircle size={17}/><span>{error}</span></div>}{type==='Visitor'?<form className="scan-form" onSubmit={event=>{event.preventDefault();recordVisitor({name:visitor.name,number:'VIS-'+Date.now().toString().slice(-6),userType:'Visitor',program:'',yearLevel:'',section:'',department:'External Visitor'},{organization:visitor.organization,purpose:visitor.purpose})}}><label>Full name<input value={visitor.name} onChange={event=>setVisitor(value=>({...value,name:event.target.value}))} required autoComplete="name"/></label><label>Organization<input value={visitor.organization} onChange={event=>setVisitor(value=>({...value,organization:event.target.value}))} required/></label><label>Purpose of visit<select value={visitor.purpose} onChange={event=>setVisitor(value=>({...value,purpose:event.target.value}))} required><option value="">Select purpose</option><option>Research and study</option><option>Borrow or return materials</option><option>Meeting or official business</option><option>Library tour</option><option>Other</option></select></label><button className="scan-primary" disabled={loading}>{loading?<LoaderCircle className="spin" size={19}/>:<Check size={19}/>}Register and record visit</button></form>:<div className="school-verify"><div className="demo-notice"><ShieldCheck size={18}/><span><strong>Life College Google account</strong>Your verified school identity will be matched with your library profile.</span></div>{authUser===undefined?<div className="auth-checking"><LoaderCircle className="spin" size={21}/><span>Checking your Google session...</span></div>:authUser&&verifiedUser?<><Identity user={verifiedUser}/><button className="scan-primary" onClick={recordAuthenticated} disabled={loading}>{loading?<LoaderCircle className="spin" size={19}/>:<Check size={19}/>}Record library check-in</button><button className="scan-secondary auth-switch" onClick={startGoogle}>Use another Google account</button></>:authUser&&!verifiedUser?<div className="scan-error" role="alert"><AlertCircle size={18}/><span>Your Google account is verified, but no active library profile is linked to {authUser.email}.</span></div>:<button className="scan-primary google" onClick={startGoogle} disabled={!backendEnabled||loading}>{loading?<LoaderCircle className="spin" size={19}/>:<span className="google-g">G</span>}{backendEnabled?'Continue with Google':'Google authentication is not configured'}</button>}{import.meta.env.DEV&&authUser===null&&<button className="scan-secondary auth-switch" onClick={startLocal} disabled={loading}>Use local test account</button>}<small className="privacy-note">Only your school identity and library profile are used for attendance.</small></div>}</ScanFrame>
}

function ScanFrame({children}:{children:React.ReactNode}){return <main className="scan-page"><header><button onClick={()=>location.assign(href('/'))} title="Back"><ArrowLeft size={19}/></button><div className="scan-brand"><img src={BASE+"lifeos-platform-crest.svg"} alt="Life College"/><span><strong>Life College</strong><small>Library Attendance</small></span></div><span className="secure-label"><ShieldCheck size={15}/>Secure</span></header><section className="scan-card">{children}</section><footer>Life College Library · Powered by LifeOS</footer></main>}
function Identity({user}:{user:SeedUser}){return <div className="identity-card"><span className="identity-avatar">{user.name.split(' ').map(value=>value[0]).slice(0,2).join('')}</span><div><strong>{user.name}</strong><small>{user.number}</small><p>{user.userType==='Student'?[user.program,user.yearLevel,user.section].filter(Boolean).join(' · '):user.department}</p></div><CheckCircle2 size={21}/></div>}
function Success({result}:{result:Result}){const duplicate=result.action==='duplicate',Icon=duplicate?Clock3:LogIn;const title=duplicate?'Attendance already recorded':'Check-in recorded';const detail=result.user.userType==='Student'?[result.user.program,result.user.yearLevel,result.user.section].filter(Boolean).join(' · '):result.user.userType==='Visitor'?[result.organization,result.purpose].filter(Boolean).join(' · '):result.user.department;return <ScanFrame><div className="scan-success"><span className={'success-mark '+(duplicate?'duplicate':'')}><Icon size={34}/></span><span className="eyebrow">{duplicate?'No changes made':'Attendance confirmed'}</span><h1>{title}</h1><p>{duplicate?'Your previous scan is still within the duplicate-scan window.':'Welcome to the Life College Library.'}</p><Identity user={result.user}/><dl><div><dt>User type</dt><dd>{labels[result.user.userType]}</dd></div><div><dt>Check-in time</dt><dd>{new Date(result.at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'})}</dd></div><div><dt>Date</dt><dd>{new Date(result.at).toLocaleDateString(undefined,{month:'long',day:'numeric',year:'numeric'})}</dd></div><div><dt>Reference</dt><dd>{result.reference}</dd></div>{detail&&<div className="wide"><dt>Profile</dt><dd>{detail}</dd></div>}</dl><button className="scan-secondary" onClick={()=>location.assign(href('/'))}>Done</button></div></ScanFrame>}
