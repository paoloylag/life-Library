import React from 'react'
import {Download, Filter} from 'lucide-react'
import {API, apiRequest} from './api'
import {defaultSettings, getLibrarySettings} from './settings'

type Filters = {dateFrom:string;dateTo:string;academicYear:string;semester:string;grouping:string;userType:string;yearLevel:string;section:string;program:string;department:string}
type Item = {label:string;value:number}
type RecordRow = {id:number;date:string;check_in_time:string;name:string;user_number:string;category:string;program:string;year_level:string;section:string;department:string;source:string}
type Report = {
 generated_at:string;period_start:string|null;period_end:string|null;academic_years:string[];semesters:string[];
 calendar_note:string;profile_note:string;
 summary:{total_visits:number;unique_users:number;return_visits:number;returning_users:number;open_days:number;average_per_open_day:number;average_per_week:number;average_per_month:number;average_per_user:number;peak_day:Item|null;peak_hour:Item|null};
 breakdowns:Record<'trend'|'daily'|'weekly'|'monthly'|'hours'|'weekdays'|'semesters'|'categories'|'programs'|'year_levels'|'sections'|'year_sections',Item[]>;
 options:{academic_years:string[];semesters:string[];user_types:string[];year_levels:string[];sections:string[];programs:string[];departments:string[]};
 records:RecordRow[];
}
const labels:Record<keyof Filters,string>={dateFrom:'Date from',dateTo:'Date to',academicYear:'Academic Year',semester:'Semester',grouping:'Trend grouping',userType:'User Type',yearLevel:'Year Level',section:'Section',program:'Degree Program',department:'Staff Department'}
const colors=['#690f0d','#00a5b7','#e0a72e','#9e1d20','#65717e']
function query(filters:Filters){
 const map:Partial<Record<keyof Filters,string>>={dateFrom:'date_from',dateTo:'date_to',academicYear:'academic_year',semester:'semester',grouping:'grouping',userType:'user_type',yearLevel:'year_level',section:'section',program:'program',department:'department'}
 const params=new URLSearchParams()
 for(const [key,value] of Object.entries(filters) as [keyof Filters,string][]) if(value&&value!=='All')params.set(map[key]!,value)
 return params.toString()
}
function Bars({items}: {items:Item[]}){
 const shown=[...items].sort((a,b)=>b.value-a.value).slice(0,8),max=Math.max(1,...shown.map(item=>item.value))
 return <div className="report-bars">{shown.length?shown.map(item=><div key={item.label}><span title={item.label}>{item.label}</span><strong>{item.value}</strong><i><b style={{width:`${item.value/max*100}%`}}/></i></div>):<p>No records</p>}</div>
}
export default function Reports(){
 const initial=React.useMemo<Filters>(()=>({dateFrom:'',dateTo:'',academicYear:'All',semester:'All',grouping:defaultSettings.defaultReportPeriod,userType:'All',yearLevel:'All',section:'All',program:'All',department:'All'}),[])
 const [filters,setFilters]=React.useState(initial)
 React.useEffect(()=>{let active=true;getLibrarySettings().then(value=>{if(active)setFilters(current=>({...current,grouping:value.settings.defaultReportPeriod,userType:value.settings.defaultReportUserType}))}).catch(()=>{});return()=>{active=false}},[])
 const [report,setReport]=React.useState<Report|null>(null)
 const [loading,setLoading]=React.useState(true)
 const [error,setError]=React.useState('')
 const [exporting,setExporting]=React.useState('')
 const params=React.useMemo(()=>query(filters),[filters])
 React.useEffect(()=>{
  let current=true
  setLoading(true);setError('')
  apiRequest<Report>('/api/library/reports?'+params).then(value=>{if(current)setReport(value)}).catch(reason=>{if(current){setReport(null);setError(reason instanceof Error?reason.message:'Report unavailable')}}).finally(()=>{if(current)setLoading(false)})
  return ()=>{current=false}
 },[params])
 async function download(format:'xlsx'|'pdf'){
  setExporting(format);setError('')
  try{
   const response=await fetch(API+`/api/library/reports/export.${format}?`+params,{credentials:'include'})
   if(!response.ok){const body=await response.json().catch(()=>null);throw new Error(body?.detail||'Export failed')}
   const url=URL.createObjectURL(await response.blob()),link=document.createElement('a')
   link.href=url;link.download=`life-college-library-report.${format}`;link.click()
   setTimeout(()=>URL.revokeObjectURL(url),1000)
  }catch(reason){setError(reason instanceof Error?reason.message:'Export failed')}finally{setExporting('')}
 }
 const optionSets:Partial<Record<keyof Filters,string[]>>={
  academicYear:report?.options.academic_years||[],semester:report?.options.semesters||[],
  grouping:['Daily','Weekly','Monthly','Annual'],userType:report?.options.user_types||[],
  yearLevel:report?.options.year_levels||[],section:report?.options.sections||[],
  program:report?.options.programs||[],department:report?.options.departments||[]
 }
 const trend=report?.breakdowns.trend||[],maxTrend=Math.max(1,...trend.map(item=>item.value))
 const categories=report?.breakdowns.categories||[],catTotal=categories.reduce((sum,item)=>sum+item.value,0)
 let pieStop=0
 const pie=catTotal?categories.map((item,index)=>{const start=pieStop;pieStop+=item.value/catTotal*100;return `${colors[index%colors.length]} ${start}% ${pieStop}%`}).join(','):'#e4e4e7'
 const stats=report?.summary
 return <div className="reports-page space-y-6">
  <div className="module-heading"><div><h2>Library Usage</h2><p>Attendance, utilization, and academic-year analysis</p></div><div className="flex gap-2"><button disabled={!report||!!exporting} onClick={()=>download('xlsx')} className="flex items-center gap-2 border border-zinc-300 px-3 py-2 text-sm"><Download size={16}/>Excel workbook</button><button disabled={!report||!!exporting} onClick={()=>download('pdf')} className="flex items-center gap-2 bg-zinc-900 px-3 py-2 text-sm text-white"><Download size={16}/>PDF report</button></div></div>
  <section className="border border-zinc-200 bg-white p-5"><div className="mb-4 flex items-center justify-between"><div className="flex items-center gap-2 font-semibold"><Filter size={18}/>Report filters</div><button onClick={()=>setFilters(initial)} className="report-reset text-sm">Reset</button></div><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
   {(['dateFrom','dateTo'] as const).map(key=><label key={key} className="text-sm font-medium">{labels[key]}<input type="date" value={filters[key]} max={key==='dateFrom'?filters.dateTo||undefined:undefined} min={key==='dateTo'?filters.dateFrom||undefined:undefined} onChange={event=>setFilters(value=>({...value,[key]:event.target.value}))} className="mt-2 w-full border border-zinc-300 bg-white px-3 py-2.5 font-normal"/></label>)}
   {(Object.keys(optionSets) as (keyof Filters)[]).map(key=><label key={key} className="text-sm font-medium">{labels[key]}<select value={filters[key]} onChange={event=>setFilters(value=>({...value,[key]:event.target.value}))} className="mt-2 w-full border border-zinc-300 bg-white px-3 py-2.5 font-normal">{key!=='grouping'&&<option>All</option>}{optionSets[key]?.map(value=><option key={value}>{value}</option>)}</select></label>)}
  </div><p className="mt-4 text-sm text-zinc-500">{loading?'Loading report...':`${stats?.total_visits||0} check-ins match the current filters.`}</p></section>
  {error&&<div role="alert" className="border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
  {report&&stats&&<><section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[
   ['Total visits',stats.total_visits,`${stats.open_days} open days`],
   ['Unique users',stats.unique_users,`${stats.return_visits} return visits; ${stats.returning_users} returning users`],
   ['Average per open day',stats.average_per_open_day,`${stats.average_per_week} weekly; ${stats.average_per_month} monthly`],
   ['Peak hour',stats.peak_hour?.label||'-',stats.peak_day?`${stats.peak_day.label}: ${stats.peak_day.value} visits`:'No visits']
  ].map(([title,value,detail])=><div key={String(title)} className="border border-zinc-200 bg-white p-5"><p className="text-sm text-zinc-500">{title}</p><p className="mt-2 text-3xl font-semibold">{value}</p><p className="mt-2 text-xs text-zinc-500">{detail}</p></div>)}</section>
   <section className="border border-zinc-200 bg-white p-5"><h2 className="font-semibold">Executive summary</h2><div className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4"><p><strong>Academic year:</strong> {filters.academicYear==='All'?report.academic_years.join(', ')||'All':filters.academicYear}</p><p><strong>Semester:</strong> {filters.semester==='All'?report.semesters.join(', ')||'All':filters.semester}</p><p><strong>Period:</strong> {report.period_start||'-'} to {report.period_end||'-'}</p><p><strong>Trend grouping:</strong> {filters.grouping}</p><p><strong>Generated:</strong> {new Date(report.generated_at).toLocaleString()}</p><p><strong>Average per user:</strong> {stats.average_per_user}</p></div><p className="mt-3 text-xs text-zinc-500">{report.calendar_note} {report.profile_note}</p></section>
   <section className="report-dashboard"><article><h2>Attendance trend</h2><p>Visits grouped {filters.grouping.toLowerCase()}</p><svg className="line-chart" viewBox="0 0 600 230" preserveAspectRatio="none"><polyline points={trend.map((item,index)=>`${trend.length===1?300:index/(trend.length-1)*570+15},${205-item.value/maxTrend*180}`).join(' ')} fill="none" stroke="#00a5b7" strokeWidth="4" vectorEffect="non-scaling-stroke"/>{trend.map((item,index)=><circle key={item.label} cx={trend.length===1?300:index/(trend.length-1)*570+15} cy={205-item.value/maxTrend*180} r="5"><title>{item.label}: {item.value} visits</title></circle>)}</svg><div className="chart-labels"><span>{trend[0]?.label||'No data'}</span><span>{trend.at(-1)?.label||''}</span></div></article>
    <article><h2>Visits per user category</h2><div className="pie-layout"><div className="pie-chart" style={{background:`conic-gradient(${pie})`}}/><div>{categories.map((item,index)=><p key={item.label}><i style={{background:colors[index%colors.length]}}/><span>{item.label}</span><strong>{item.value}</strong></p>)}</div></div></article>
    <article><h2>Student visits by program</h2><Bars items={report.breakdowns.programs}/></article>
    <article><h2>Student visits by year level</h2><Bars items={report.breakdowns.year_levels}/></article>
    <article><h2>Student visits by section</h2><Bars items={report.breakdowns.sections}/></article>
    <article><h2>Monthly comparison</h2><Bars items={report.breakdowns.monthly}/></article>
    <article><h2>Semester comparison</h2><Bars items={report.breakdowns.semesters}/></article>
    <article><h2>Peak hours</h2><Bars items={report.breakdowns.hours}/></article></section>
   <section className="overflow-hidden border border-zinc-200 bg-white"><div className="border-b px-5 py-4"><h2 className="font-semibold">Filtered check-ins</h2><p className="text-xs text-zinc-500">Showing the first 80 records. Exports include every matching record.</p></div><div className="max-h-96 overflow-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="sticky top-0 bg-zinc-50 text-zinc-500"><tr><th className="p-3">Date</th><th>Name</th><th>User type</th><th>Program / Department</th><th>Year / Section</th><th>Check-in time</th><th>Source</th></tr></thead><tbody>{report.records.slice(0,80).map(row=><tr className="border-t" key={row.id}><td className="p-3">{row.date}</td><td>{row.name}</td><td>{row.category}</td><td>{row.program||row.department||'-'}</td><td>{[row.year_level,row.section].filter(Boolean).join(' / ')||'-'}</td><td>{new Date(row.check_in_time).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</td><td>{row.source}</td></tr>)}{!report.records.length&&<tr><td colSpan={7} className="p-10 text-center text-zinc-500">No records match these filters.</td></tr>}</tbody></table></div></section></>}
 </div>
}
