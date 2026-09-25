export const API=(import.meta.env.VITE_API_URL||'').replace(/\/$/,'')

export type ApiUser={
 number:string;display_number?:string;name:string;email:string;user_type:string;program:string;year_level:string;
 section:string;department:string;organization:string;preferred_name:string;employment_status:string;position:string;middle_name:string;immediate_supervisor:string;date_hired:string;regularization_date:string;contact_number:string;is_active:boolean;visit_count:number;last_visit:string|null
 managed_by_google:boolean
}
export type ApiVisit={
 id:number;user_number:string;name:string;user_type:string;program:string;year_level:string;
 section:string;department:string;organization:string;check_in_time:string;source:string;
 note:string;purpose:string;reference:string;recorded_by:string|null
}
export type Page<T>={items:T[];total:number;page:number;page_size:number}

export async function apiRequest<T>(path:string,init:RequestInit={}):Promise<T>{
 const headers=new Headers(init.headers)
 if(init.body&&!headers.has('Content-Type'))headers.set('Content-Type','application/json')
 const response=await fetch(API+path,{...init,headers,credentials:'include'})
 const body=await response.json().catch(()=>null)
 if(!response.ok)throw new Error(body?.detail||'The server could not complete the request.')
 return body as T
}

export function displayUserType(value:string){
 const normalized=value.toLowerCase()
 if(normalized==='student')return 'Student'
 if(normalized==='faculty')return 'Faculty'
 if(normalized==='administrator')return 'Administrator'
 if(normalized==='visitor')return 'Visitor'
 return 'Non-Teaching'
}
