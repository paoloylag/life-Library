import {useEffect, useRef} from 'react'
import {createPortal} from 'react-dom'
import {bookingErrorTitle} from './booking-messages'
import {AlertCircle, X} from 'lucide-react'

export default function BookingErrorToast({message,onDismiss}:{message:string;onDismiss:()=>void}) {
 const dismiss=useRef(onDismiss)
 useEffect(()=>{dismiss.current=onDismiss},[onDismiss])
 useEffect(()=>{
  if(!message)return
  const timer=window.setTimeout(()=>dismiss.current(),1500)
  return()=>window.clearTimeout(timer)
 },[message])
 if(!message)return null
 const container=Array.from(document.querySelectorAll('dialog[open]')).at(-1)||document.body
 return createPortal(<div className="booking-toast-region"><div className="booking-toast booking-error-toast" role="alert"><AlertCircle size={22} aria-hidden="true"/><div><strong>{bookingErrorTitle(message)}</strong><span>{message}</span></div><button type="button" className="booking-toast-close" aria-label="Dismiss booking error" title="Dismiss" onClick={onDismiss}><X size={18}/></button></div></div>,container)
}
