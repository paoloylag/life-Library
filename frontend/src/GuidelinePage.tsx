import React from 'react'
import type {Guidelines} from './BookingGuidelines'
import './guideline-page.css'

export default function GuidelinePage({slug}:{slug:string}) {
 const kind=({'nap-pod':'nap_pod','collaboration-room':'collaboration_room'} as Record<string,string>)[slug]
 const [document,setDocument]=React.useState<Guidelines|null>(null)
 const [error,setError]=React.useState('')
 React.useEffect(()=>{
  if(!kind){setError('Guidelines not found.');return}
  const controller=new AbortController()
  fetch((import.meta.env.VITE_API_URL||'').replace(/\/$/,'')+'/api/bookings/guidelines/'+kind,{signal:controller.signal})
   .then(async response=>{if(!response.ok)throw Error('Unable to load guidelines. Please try again.');setDocument(await response.json())})
   .catch(reason=>{if(reason.name!=='AbortError')setError(reason.message)})
  return ()=>controller.abort()
 },[kind])
 return <div className="guideline-page"><header><a href={import.meta.env.BASE_URL+'book'}><img src={import.meta.env.BASE_URL+'life-college-favicon-150.png'} alt="Life College"/>Life College Library</a></header><main><h1>{document?.title||'Usage Guidelines'}</h1>{error?<p role="alert">{error}</p>:!document?<p role="status">Loading guidelines...</p>:<>{document.sections.map(section=><section key={section.title}><h2>{section.title}</h2><ol>{section.items.map(text=><li key={text}>{text}</li>)}</ol></section>)}<p>Questions? <a href={'mailto:'+document.contact}>{document.contact}</a></p><a className="guideline-book" href={import.meta.env.BASE_URL+'book'}>Go to booking page</a></>}</main></div>
}
