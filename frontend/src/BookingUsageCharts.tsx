type Breakdown={resource:string;category:string;program:string;year_level:string;department:string;uses:number}
type Total={resource:string;bookings:number;participant_uses:number}
export default function BookingUsageCharts({totals,breakdowns}:{totals:Total[];breakdowns:Breakdown[]}){
 const categories=new Map<string,number>()
 for(const row of breakdowns)categories.set(row.category,(categories.get(row.category)||0)+row.uses)
 const charts=[{title:'Bookings by resource',rows:totals.map(row=>[row.resource,row.bookings] as const)},{title:'Participant uses by category',rows:[...categories.entries()]}]
 return <><div className="profile-metrics"><div className="metric-card"><span>Bookings</span><strong>{totals.reduce((sum,row)=>sum+row.bookings,0)}</strong></div><div className="metric-card"><span>Participant uses</span><strong>{totals.reduce((sum,row)=>sum+row.participant_uses,0)}</strong></div><div className="metric-card"><span>Resources used</span><strong>{totals.filter(row=>row.bookings>0).length}</strong></div></div><div className="booking-usage-charts">{charts.map(chart=>{const max=Math.max(1,...chart.rows.map(row=>row[1]));return <figure key={chart.title}><figcaption>{chart.title}</figcaption>{chart.rows.length?chart.rows.map(([label,value])=><div className="booking-usage-bar" key={label}><span>{label}</span><div role="img" aria-label={`${label}: ${value}`}><i style={{width:`${value/max*100}%`}}/></div><strong>{value}</strong></div>):<p>No usage in this period.</p>}</figure>})}</div></>
}
