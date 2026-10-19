import React from 'react'
import {ArrowLeft,BookOpen,LogIn,ShieldX} from 'lucide-react'
import './access-denied.css'

export default function AccessDenied({staff=false,qrDisplay=false,dark=false}:{staff?:boolean;qrDisplay?:boolean;dark?:boolean}){
 const heading=React.useRef<HTMLHeadingElement>(null)
 React.useEffect(()=>{heading.current?.focus()},[])
 const base=import.meta.env.BASE_URL
 return <main className={'access-denied'+(dark?' dark':'')}><header><img src={base+'life-college-favicon-150.png'} alt="Life College"/><strong>Life College Library</strong></header><section aria-labelledby="access-denied-title"><ShieldX size={36} aria-hidden="true"/><p className="eyebrow">Access restricted</p><h1 id="access-denied-title" ref={heading} tabIndex={-1}>Access denied</h1><p>{staff?'Your staff role does not have permission to view this page.':'This page requires an authorized staff account. Your Library User account does not automatically include admin access.'}</p><nav aria-label="Access recovery"><a className="primary-button" href={base+'book?view=history'}><BookOpen size={17}/>My Bookings</a>{staff?<a className="secondary-button" href={qrDisplay?base+'qr-display':base}><ArrowLeft size={17}/>{qrDisplay?'Back to QR display':'Back to dashboard'}</a>:<a className="secondary-button" href={base+'staff'}><LogIn size={17}/>Staff sign-in</a>}</nav><p className="access-denied-help">Contact the librarian if you believe you should have access.</p></section></main>
}
