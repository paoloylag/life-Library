import React from 'react'
import {LoaderCircle, ShieldCheck} from 'lucide-react'

export function ScanFrame({children}:{children:React.ReactNode}){
 return <main className="scan-page"><header><div className="scan-brand"><img src={import.meta.env.BASE_URL+'lifeos-platform-crest.svg'} alt="Life College"/><span><strong>Life College</strong><small>Library Attendance</small></span></div><span className="secure-label"><ShieldCheck size={15}/>Secure</span></header><section className="scan-card">{children}</section><footer>Life College Library · Powered by LifeOS</footer></main>
}

export function GoogleSignInPrompt({onGoogle,onLocal,loading=false,checking=false,enabled=true,allowLocal=true}:{onGoogle:()=>void;onLocal:()=>void;loading?:boolean;checking?:boolean;enabled?:boolean;allowLocal?:boolean}){
 if(checking)return <div className="auth-checking" role="status"><LoaderCircle className="spin" size={21}/><span>Checking your Google session...</span></div>
 return <><div className="demo-notice"><ShieldCheck size={18}/><span><strong>Life College Google account</strong>Your verified identity will be matched with your library profile.</span></div><button type="button" className="scan-primary google" onClick={onGoogle} disabled={!enabled||loading}>{loading?<LoaderCircle className="spin" size={19}/>:<span className="google-g">G</span>}{enabled?'Continue with Google':'Google authentication is not configured'}</button>{import.meta.env.DEV&&allowLocal&&<button type="button" className="scan-secondary auth-switch" onClick={onLocal} disabled={loading}>Use local test account</button>}</>
}
