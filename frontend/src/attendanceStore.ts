import {Visit,visits} from './data'
export type StoredVisit=Visit&{source?:'qr'|'manual';note?:string}
export function getManualVisits():StoredVisit[]{try{return JSON.parse(localStorage.getItem('manual-check-ins')||'[]')}catch{return[]}}
export function getAllVisits():StoredVisit[]{return[...getManualVisits(),...visits.map(v=>({...v,source:'qr' as const}))]}
export function addManualVisit(visit:StoredVisit){const rows=getManualVisits();rows.unshift(visit);localStorage.setItem('manual-check-ins',JSON.stringify(rows));dispatchEvent(new CustomEvent('attendance-changed',{detail:visit}))}
