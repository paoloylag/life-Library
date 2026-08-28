import React from 'react'
import { createRoot } from 'react-dom/client'
import { BarChart3, Bell, ChevronRight, Clock3, LayoutDashboard, Maximize2, Menu, Moon, QrCode, Search, Settings, Sun, UserPlus, Users, X } from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import Reports from './Reports'
import Students, {StudentDetail} from './Students'
import Attendance from './Attendance'
import SettingsPage from './SettingsPage'
import ScanPage from './ScanPage'
import {loadSettings} from './settings'
import './index.css'

const BASE=import.meta.env.BASE_URL
const currentPath=()=>{const path=location.pathname;const base=BASE.endsWith('/')?BASE.slice(0,-1):BASE;return base&&path.startsWith(base)?path.slice(base.length)||'/':path}
const href=(path:string)=>BASE+(path==='/'?'':path.replace(/^\//,''))

const visits=[
 {id:1,name:'Angela Reyes',number:'2026-00124',timeIn:'8:32 AM'},
 {id:2,name:'Marcus Lim',number:'2025-00817',timeIn:'8:43 AM'},
 {id:3,name:'Sofia Navarro',number:'2024-00309',timeIn:'9:01 AM'},
 {id:4,name:'Daniel Cruz',number:'2023-00542',timeIn:'7:45 AM'},
 {id:5,name:'Mika Santos',number:'2025-00288',timeIn:'7:10 AM'},
]
const navigation=[
 {label:'Library',items:[{label:'Dashboard',path:'/',icon:LayoutDashboard},{label:'Attendance',path:'/attendance',icon:Clock3},{label:'Students',path:'/students',icon:Users},{label:'Reports',path:'/reports',icon:BarChart3}]},
 {label:'Administration',items:[{label:'Settings',path:'/settings',icon:Settings}]},
]
function App(){
 const[path,setPath]=React.useState(currentPath())
 const[drawer,setDrawer]=React.useState(false)
 const[dark,setDark]=React.useState(()=>localStorage.getItem('dark-mode')==='true')
 React.useEffect(()=>{const fn=()=>setPath(currentPath());addEventListener('popstate',fn);return()=>removeEventListener('popstate',fn)},[])
 React.useEffect(()=>localStorage.setItem('dark-mode',String(dark)),[dark])
 function navigate(next:string){history.pushState({},'',href(next));setPath(next);setDrawer(false)}
 if(path==='/qr-display')return <QrDisplay close={()=>navigate('/')}/>
 if(path.startsWith('/scan/'))return <ScanPage/>
 const title=path==='/reports'?'Reports':path==='/attendance'?'Attendance':path.startsWith('/students')?'Students':path==='/settings'?'Settings':'Dashboard'
 return <div className={`lifeos-shell ${dark?'dark':''}`}><Sidebar path={path} navigate={navigate}/>
 <div className="lifeos-workspace"><Topbar title={title} dark={dark} setDark={setDark} open={()=>setDrawer(true)}/><main className="lifeos-content">{path==='/reports'?<Reports/>:path.startsWith('/students/')?<StudentDetail number={decodeURIComponent(path.slice('/students/'.length))}/>:path==='/students'?<Students/>:path==='/attendance'?<Attendance/>:path==='/settings'?<SettingsPage/>:path==='/'?<Dashboard/>:<Placeholder title={title}/>}</main></div>
 {drawer&&<div className="lifeos-drawer"><div className="drawer-head"><Brand/><button className="icon-button" onClick={()=>setDrawer(false)}><X size={20}/></button></div><Sidebar path={path} navigate={navigate} compact/></div>}</div>
}
function Brand(){return <div className="brand-lockup"><span className="brand-mark"><img src={BASE+"lifeos-platform-crest.svg"} alt="LifeOS"/></span><span><strong>Life College</strong><small>Library Attendance</small></span></div>}
function Sidebar({path,navigate,compact=false}:{path:string;navigate:(p:string)=>void;compact?:boolean}){return <aside className={`lifeos-sidebar ${compact?'compact':''}`}>{!compact&&<div className="sidebar-head"><Brand/></div>}<nav>{navigation.map(section=><div className="nav-section" key={section.label}><p>{section.label}</p>{section.items.map(item=>{const Icon=item.icon;return <button key={item.path} onClick={()=>navigate(item.path)} className={path===item.path||(item.path!=='/'&&path.startsWith(item.path+'/'))?'active':''}><Icon size={18}/><span>{item.label}</span><ChevronRight size={15}/></button>})}</div>)}</nav><div className="sidebar-foot"><span className="status-dot"/>LifeOS tenant connected</div></aside>}
function Topbar({title,dark,setDark,open}:{title:string;dark:boolean;setDark:(v:boolean)=>void;open:()=>void}){return <header className="lifeos-topbar"><button className="icon-button mobile" onClick={open}><Menu size={20}/></button><div><h1>{title}</h1></div><div className="top-actions"><label className="search"><Search size={17}/><input placeholder="Search"/></label><button className="icon-button" title="Notifications"><Bell size={19}/></button><button className="icon-button" title="Theme" onClick={()=>setDark(!dark)}>{dark?<Sun size={19}/>:<Moon size={19}/>}</button><div className="user-chip"><span>LR</span><strong>Library Registrar</strong></div></div></header>}
function Dashboard(){const[url,setUrl]=React.useState(localStorage.getItem('qr'));const settings=loadSettings();function generate(){const expires=Date.now()+settings.qrExpiryMinutes*60000;const next=location.origin+href('/scan/demo-daily-token?expires=')+expires;setUrl(next);localStorage.setItem('qr',next);localStorage.setItem('qr-expires',String(expires))}return <div className="dashboard-grid"><section className="overview-hero"><div><span className="eyebrow">Library operations</span><h2>Library overview</h2><p>Monitor daily foot traffic and manage the student attendance code.</p></div><div className="date-block"><span>Today</span><strong>{new Date().toLocaleDateString(undefined,{month:'long',day:'numeric'})}</strong><small>{new Date().toLocaleDateString(undefined,{weekday:'long',year:'numeric'})}</small></div></section><Metric label="Check-ins today" value="6" detail="Across all user types"/><Metric label="Unique visitors" value="5" detail="Recorded today"/><Metric label="Peak check-in hour" value="9 AM" detail="Highest arrival volume"/><section className="panel qr-panel"><div className="panel-title"><div><QrCode size={18}/><h3>Daily QR code</h3></div><button className="icon-button qr-display-button" title="Open student display" onClick={()=>location.assign(href('/qr-display'))}><QrCode size={18}/></button></div>{url?<div className="qr-code"><QRCodeSVG value={url} size={230}/></div>:<div className="qr-empty">No active code</div>}<div className="qr-actions"><button className="primary-button" onClick={generate}>{url?'Replace daily QR':'Generate daily QR'}</button><button className="secondary-button manual-qr-button" onClick={()=>location.assign(href('/attendance?manual=1'))}><UserPlus size={17}/>Manual check-in</button></div><small>Students verify their identity with Google after scanning.</small></section><section className="panel activity-panel"><div className="panel-title"><div><Clock3 size={18}/><h3>Today's activity</h3></div><button className="secondary-button">Export</button></div><div className="table-wrap"><table><thead><tr><th>User</th><th>Check-in time</th><th>Attendance</th></tr></thead><tbody>{visits.map(v=><tr key={v.id}><td><strong>{v.name}</strong><small>{v.number}</small></td><td>{v.timeIn}</td><td><span className="badge inside">Checked in</span></td></tr>)}</tbody></table></div></section></div>}
function QrDisplay({close}:{close:()=>void}){const settings=loadSettings();const stored=localStorage.getItem('qr');const url=Number(localStorage.getItem('qr-expires')||Infinity)>Date.now()?stored:null;async function fullscreen(){await document.documentElement.requestFullscreen?.()}return <main className="student-display"><header><Brand/><div><button className="display-action" onClick={fullscreen}><Maximize2 size={18}/>Fullscreen</button><button className="display-action" onClick={close}>Back to dashboard</button></div></header><section className="display-card"><div className="display-copy"><span className="eyebrow">{settings.libraryName}</span><h1>{settings.qrHeading}</h1><p>{settings.qrInstructions}</p><div className="display-date">{new Date().toLocaleDateString(undefined,{weekday:'long',month:'long',day:'numeric',year:'numeric'})}</div></div><div className="display-qr">{url?<QRCodeSVG value={url} size={560} level="M"/>:<div className="display-empty"><QrCode size={52}/><strong>No active QR code</strong><span>Generate today's code from the librarian dashboard.</span></div>}</div></section><footer>Library Attendance <span/> Powered by LifeOS</footer></main>}
function Metric({label,value,detail}:{label:string;value:string;detail:string}){return <section className="metric-card"><span>{label}</span><strong>{value}</strong><small>{detail}</small></section>}
function Placeholder({title}:{title:string}){return <section className="placeholder"><span className="eyebrow">Module</span><h2>{title}</h2><p>This LifeOS tenant module is ready for its library-specific workflow.</p></section>}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)

