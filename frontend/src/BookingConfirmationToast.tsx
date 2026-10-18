import React from 'react'
import {CheckCircle2, X} from 'lucide-react'

export type BookingConfirmation={resourceName:string;resourceId:number;key:number;status:'in_progress'|'upcoming'}

export default function BookingConfirmationToast({confirmation,onDismiss,onView}:{confirmation:BookingConfirmation|null;onDismiss:()=>void;onView:()=>void}){
 const[paused,setPaused]=React.useState(false)
 React.useEffect(()=>{setPaused(false)},[confirmation?.key])
 React.useEffect(()=>{if(!confirmation||paused)return;const timer=window.setTimeout(onDismiss,6000);return()=>window.clearTimeout(timer)},[confirmation,paused,onDismiss])
 return <div className="booking-toast-region" role="status" aria-live="polite" aria-atomic="true">{confirmation&&<div className="booking-toast" onMouseEnter={()=>setPaused(true)} onMouseLeave={()=>setPaused(false)} onFocusCapture={()=>setPaused(true)} onBlurCapture={event=>{if(!event.currentTarget.contains(event.relatedTarget))setPaused(false)}}><CheckCircle2 size={22} aria-hidden="true"/><div><strong>Booking confirmed</strong><span>{confirmation.resourceName}</span><button type="button" className="booking-toast-link" onClick={onView}>View booking</button></div><button type="button" className="booking-toast-close" aria-label="Dismiss booking confirmation" title="Dismiss" onClick={onDismiss}><X size={18}/></button></div>}</div>
}
