import React from 'react'
import {ChevronLeft, ChevronRight} from 'lucide-react'
import {displayUserType} from './api'

type Row = {resource:string;category:string;program:string;year_level:string;department:string;uses:number}

export default function BookingUsageTable({rows}:{rows:Row[]}) {
 const [page,setPage]=React.useState(1)
 const [size,setSize]=React.useState(10)
 const pages=Math.max(1,Math.ceil(rows.length/size))
 const current=Math.min(page,pages)
 React.useEffect(()=>setPage(1),[rows])
 return <section className="panel booking-section facility-usage" aria-labelledby="facility-usage-title">
  <h3 id="facility-usage-title">Usage breakdown</h3>
  <div className="table-wrap"><table><thead><tr><th>Resource</th><th>Category</th><th>Program</th><th>Year</th><th>Department</th><th>Uses</th></tr></thead><tbody>
   {rows.slice((current-1)*size,current*size).map((row,index)=><tr key={index}><td>{row.resource}</td><td>{displayUserType(row.category)}</td><td>{row.program||'-'}</td><td>{row.year_level||'-'}</td><td>{row.department||'-'}</td><td>{row.uses}</td></tr>)}
  </tbody></table>{!rows.length&&<p className="module-state">No usage for the selected filters.</p>}</div>
  <div className="directory-pagination"><label>Items per page<select aria-label="Usage rows per page" value={size} onChange={event=>{setSize(Number(event.target.value));setPage(1)}}>{[10,25,50].map(value=><option key={value} value={value}>{value}</option>)}</select></label>
   <span aria-live="polite">{rows.length?`${(current-1)*size+1}-${Math.min(current*size,rows.length)} of ${rows.length}`:'0 results'}</span>
   <nav aria-label="Usage pagination"><button type="button" className="icon-button" title="Previous page" aria-label="Previous usage page" disabled={current<=1} onClick={()=>setPage(current-1)}><ChevronLeft size={18}/></button><span>Page {current} of {pages}</span><button type="button" className="icon-button" title="Next page" aria-label="Next usage page" disabled={current>=pages} onClick={()=>setPage(current+1)}><ChevronRight size={18}/></button></nav>
  </div>
 </section>
}
