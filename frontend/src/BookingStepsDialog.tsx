import React from 'react'
import {X} from 'lucide-react'
import './booking-steps-dialog.css'

export default function BookingStepsDialog({children,modal,busy,onClose}:{children:React.ReactNode;modal:boolean;busy:boolean;onClose:()=>void}) {
 const ref=React.useRef<HTMLDialogElement>(null)
 React.useEffect(()=>{
  if(!modal)return
  const dialog=ref.current
  const previous=document.activeElement as HTMLElement|null
  const overflow=document.body.style.overflow
  document.body.style.overflow='hidden'
  dialog?.showModal()
  dialog?.focus()
  return ()=>{dialog?.close();document.body.style.overflow=overflow;previous?.focus()}
 },[modal])
 if(!modal)return <>{children}</>
 return <dialog ref={ref} tabIndex={-1} className="manual-modal booking-steps-dialog" aria-label="Confirm your booking" onCancel={event=>{event.preventDefault();if(!busy)onClose()}}><div className="booking-steps-heading"><h2>Confirm your booking</h2><button type="button" className="icon-button" aria-label="Close booking" title="Close booking" disabled={busy} onClick={onClose}><X size={18}/></button></div>{children}</dialog>
}
