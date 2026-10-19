import React from 'react'
import {CreditCard} from 'lucide-react'
import './pass-reminder-dialog.css'

export default function PassReminderDialog({booking,onAcknowledge}:{booking:{id:number;resource_name:string}|null;onAcknowledge:()=>Promise<void>}){
 const dialog=React.useRef<HTMLDialogElement>(null)
 const[busy,setBusy]=React.useState(false),[error,setError]=React.useState('')
 React.useEffect(()=>{setError('');if(booking){if(!dialog.current?.open)dialog.current?.showModal()}else dialog.current?.close()},[booking?.id])
 async function acknowledge(){setBusy(true);setError('');try{await onAcknowledge()}catch{setError('Your booking is confirmed, but we could not save your acknowledgement. Please try again.')}finally{setBusy(false)}}
 return <dialog ref={dialog} className="pass-reminder-dialog" aria-labelledby="pass-reminder-title" aria-describedby="pass-reminder-message" onCancel={event=>event.preventDefault()}><CreditCard size={32} aria-hidden="true"/><p className="eyebrow">Booking Confirmed</p><h2 id="pass-reminder-title">Collect Your Booking Pass</h2><p className="pass-reminder-reference">Reservation #{booking?.id}</p><strong>{booking?.resource_name}</strong><p id="pass-reminder-message">Before using the facility, please surrender your ID to the librarian and collect your pass.</p><p>Show your reservation number to the librarian to confirm your booking.</p>{error&&<p role="alert">{error}</p>}<button autoFocus type="button" className="primary-button" disabled={busy} onClick={()=>void acknowledge()}>{busy?'Saving…':'I Understand'}</button></dialog>
}
