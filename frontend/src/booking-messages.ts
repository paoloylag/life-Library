export function bookingErrorMessage(message:string,{admin=false,group=false}:{admin?:boolean;group?:boolean}={}){
 if(message.startsWith('A participant already has a booking during this time.'))return admin
  ?'The selected user or a room member already has another booking at this time. End the active session, cancel the upcoming reservation, or choose a different time.'
  :group?'You or a selected room member already has another booking at this time. Check My Bookings and ask your room members to check theirs, or choose a different time.'
  :'You already have another booking at this time, even if this resource is available. Open My Bookings to end your active session or cancel the upcoming reservation, or choose a different time.'
 if(message==='This time is already reserved; refresh availability')return 'This resource was reserved for the selected time. Close this form and choose another available time or resource.'
 if(message==='Not Found')return 'The booking service endpoint is unavailable. Reload the page and try again.'
 if(message==='Failed to fetch'||message==='Load failed')return 'Unable to connect to the booking service. Check your connection and try again. If you were confirming a booking, check My Bookings before retrying.'
 return message
}

export function bookingErrorTitle(message:string){
 if(message.includes('already has another booking')||message.includes('already have another booking')||message.includes('resource was reserved'))return 'Booking time conflict'
 if(message.includes('connect to the booking service'))return 'Connection problem'
 if(/sign.in|authentication|Authentication/.test(message))return 'Sign-in required'
 if(message.includes('booking guidelines'))return 'Guidelines agreement required'
 return 'Unable to complete request'
}

export function sessionEndedMessage(resource:string,admin:boolean,nextReserved:boolean){
 return `${admin?`The session for ${resource}`:'Your session'} has ended. ${nextReserved?'Another user is scheduled next. ':''}${admin?'Please ensure the facility is vacated and the booking pass is returned.':'Please return your pass to the librarian and collect your ID.'}`
}
