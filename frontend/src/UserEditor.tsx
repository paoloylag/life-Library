import React from 'react'
import {X} from 'lucide-react'
import {apiRequest, ApiUser} from './api'
import {defaultSettings, getLibrarySettings} from './settings'

type UserFields = Pick<ApiUser, 'number' | 'name' | 'email' | 'user_type' | 'program' | 'year_level' | 'section' | 'department' | 'organization' | 'is_active'>
const empty: UserFields = {number:'', name:'', email:'', user_type:'student', program:'', year_level:'', section:'', department:'', organization:'', is_active:true}
const categories = [['student','Student'], ['faculty','Faculty / Teaching Personnel'], ['non-teaching personnel','Non-Teaching Personnel'], ['administrator','Administrator'], ['visitor','Visitor']]

export default function UserEditor({user,onClose,onSaved}:{user:ApiUser|null;onClose:()=>void;onSaved:()=>void}){
 const [fields,setFields]=React.useState<UserFields>(user ? {...empty,...user} : empty)
 const [options,setOptions]=React.useState(()=>({programs:defaultSettings.programs,yearLevels:defaultSettings.yearLevels,sections:defaultSettings.sections,departments:defaultSettings.departments}))
 const [saving,setSaving]=React.useState(false)
 const [error,setError]=React.useState('')
 const set=(key:keyof UserFields,value:string|boolean)=>setFields(current=>({...current,[key]:value}))
 const input=(key:keyof UserFields,label:string,required=false)=><label>{label}<input value={String(fields[key])} required={required} disabled={Boolean(user?.managed_by_google&&key==='number')} onChange={event=>set(key,event.target.value)}/></label>
 React.useEffect(()=>{let active=true;getLibrarySettings().then(result=>{if(active)setOptions({programs:result.settings.programs,yearLevels:result.settings.yearLevels,sections:result.settings.sections,departments:result.settings.departments})}).catch(()=>{});return()=>{active=false}},[])
 async function submit(event:React.FormEvent){
  event.preventDefault();setSaving(true);setError('')
  try{
   await apiRequest('/api/library/users'+(user?'/'+encodeURIComponent(user.number):''),{method:user?'PUT':'POST',body:JSON.stringify(fields)})
   onSaved()
  }catch(reason){setError(reason instanceof Error?reason.message:'Unable to save user')}
  finally{setSaving(false)}
 }
 return <div className="modal-backdrop" onMouseDown={event=>{if(event.target===event.currentTarget)onClose()}}>
  <form className="manual-modal" onSubmit={submit}>
   <header><div><span className="eyebrow">Library directory</span><h3>{user?'Edit library user':'Add library user'}</h3><p>Manage identity and reporting details.</p></div><button type="button" className="icon-button" title="Close" onClick={onClose}><X size={18}/></button></header>
   <div className="manual-form">
    {input('number','User number',true)}{input('name','Full name',true)}
    <label>User category<select value={fields.user_type} disabled={user?.managed_by_google} onChange={event=>set('user_type',event.target.value)}>{categories.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
    <label>Email{fields.user_type!=='visitor'?' (required)':''}<input type="email" required={fields.user_type!=='visitor'} disabled={user?.managed_by_google} value={fields.email} onChange={event=>set('email',event.target.value)}/></label>
    {user?.managed_by_google&&<small className="wide">Google Workspace manages this account's identity and category.</small>}
    {fields.user_type==='student'?<><label>Degree program<select value={fields.program} required onChange={event=>set('program',event.target.value)}><option value="">Select degree program</option>{fields.program&&!options.programs.includes(fields.program)&&<option value={fields.program} disabled>{fields.program} (not available)</option>}{options.programs.map(program=><option key={program}>{program}</option>)}</select></label><label>Year level<select value={fields.year_level} required onChange={event=>set('year_level',event.target.value)}><option value="">Select year level</option>{fields.year_level&&!options.yearLevels.includes(fields.year_level)&&<option value={fields.year_level} disabled>{fields.year_level} (not available)</option>}{options.yearLevels.map(level=><option key={level}>{level}</option>)}</select></label><label>Section<select value={fields.section} required onChange={event=>set('section',event.target.value)}><option value="">Select section</option>{fields.section&&!options.sections.includes(fields.section)&&<option value={fields.section} disabled>{fields.section} (not available)</option>}{options.sections.map(section=><option key={section}>{section}</option>)}</select></label></>:fields.user_type==='visitor'?input('organization','Organization'):<label>Department<select value={fields.department} required onChange={event=>set('department',event.target.value)}><option value="">Select department</option>{fields.department&&!options.departments.includes(fields.department)&&<option value={fields.department} disabled>{fields.department} (not available)</option>}{options.departments.map(department=><option key={department}>{department}</option>)}</select></label>}
    <label className="user-active"><input type="checkbox" checked={fields.is_active} onChange={event=>set('is_active',event.target.checked)}/>Active</label>
    {error&&<p className="module-error wide" role="alert">{error}</p>}
   </div>
   <footer><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button type="submit" className="primary-button save-button" disabled={saving}>{saving?'Saving...':'Save user'}</button></footer>
  </form>
 </div>
}
