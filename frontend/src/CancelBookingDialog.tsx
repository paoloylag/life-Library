import React from 'react'
import {X} from 'lucide-react'

export default function CancelBookingDialog({booking,onClose,onConfirm}:{booking:{resource_name:string;starts_at:string};onClose:()=>void;onConfirm:()=>Promise<void>}) {
 const dialog=React.useRef<HTMLDialogElement>(null)
 const [saving,setSaving]=React.useState(false),[error,setError]=React.useState('')
 React.useEffect(()=>{dialog.current?.showModal()},[])
 async function submit(event:React.FormEvent){event.preventDefault();setSaving(true);setError('');try{await onConfirm();onClose()}catch(reason){setError(reason instanceof Error?reason.message:'Cancellation failed')}finally{setSaving(false)}}
 return <dialog ref={dialog} className="manual-modal resource-policy-modal" aria-labelledby="cancel-booking-title" onCancel={event=>{event.preventDefault();if(!saving)onClose()}}><form onSubmit={submit}><header><h3 id="cancel-booking-title">Cancel booking?</h3><button type="button" className="icon-button" aria-label="Close cancellation" disabled={saving} onClick={onClose}><X size={18}/></button></header><div className="resource-policy-body"><p><strong>{booking.resource_name}</strong></p><p>{new Date(booking.starts_at).toLocaleString('en-PH',{timeZone:'Asia/Manila'})} (Manila)</p><p>The reserved time will become available to other users.</p>{error&&<p role="alert" className="module-error">{error}</p>}</div><footer><button type="button" className="secondary-button" disabled={saving} onClick={onClose}>Keep booking</button><button className="primary-button" disabled={saving}>{saving?'Cancelling...':'Cancel booking'}</button></footer></form></dialog>
}
