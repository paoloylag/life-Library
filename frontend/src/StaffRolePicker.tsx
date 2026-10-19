import React from 'react'
import {Check,ChevronDown} from 'lucide-react'
import {staffRoleName,type LibrarianSession} from './LoginPage'

type Role=LibrarianSession['role']
const roles:Role[]=['librarian','librarian_associate','auditor','qr_display']
export default function StaffRolePicker({value,onChange}:{value:Role;onChange:(role:Role)=>void}){
 const[open,setOpen]=React.useState(false),[active,setActive]=React.useState(roles.indexOf(value))
 const ref=React.useRef<HTMLDivElement>(null),trigger=React.useRef<HTMLButtonElement>(null)
 const id=React.useId()
 React.useEffect(()=>{if(!open)return;const outside=(event:PointerEvent)=>{if(!ref.current?.contains(event.target as Node))setOpen(false)};document.addEventListener('pointerdown',outside);return()=>document.removeEventListener('pointerdown',outside)},[open])
 React.useEffect(()=>{if(open)document.getElementById(id+'-'+active)?.focus()},[open,active,id])
 const choose=(role:Role)=>{onChange(role);setOpen(false);trigger.current?.focus()}
 return <div className="staff-role-picker" ref={ref} onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget))setOpen(false)}}><span id={id+'-label'} className="google-access-label">Staff role</span><button ref={trigger} type="button" className="staff-role-trigger" aria-labelledby={id+'-label '+id+'-value'} aria-haspopup="listbox" aria-expanded={open} aria-controls={open?id:undefined} onClick={()=>{setActive(roles.indexOf(value));setOpen(!open)}} onKeyDown={event=>{if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){event.preventDefault();setActive(event.key==='End'?roles.length-1:event.key==='Home'?0:roles.indexOf(value));setOpen(true)}}}><span id={id+'-value'}>{staffRoleName(value)}</span><ChevronDown size={18}/></button>{open&&<div id={id} role="listbox" aria-labelledby={id+'-label'} className="staff-role-options" onKeyDown={event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();setOpen(false);trigger.current?.focus()}else if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){event.preventDefault();setActive(event.key==='Home'?0:event.key==='End'?roles.length-1:(active+(event.key==='ArrowDown'?1:-1)+roles.length)%roles.length)}}}>{roles.map((role,index)=><button type="button" role="option" aria-selected={value===role} tabIndex={active===index?0:-1} id={id+'-'+index} key={role} onClick={()=>choose(role)}><span>{staffRoleName(role)}</span>{value===role&&<Check size={17}/>}</button>)}</div>}</div>
}

