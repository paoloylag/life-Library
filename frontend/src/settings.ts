export type LibrarySettings = {
  libraryName: string; timezone: string; opensAt: string; closesAt: string
  qrExpiryMinutes: number; duplicateWindowMinutes: number
  academicYear: string; semester: string; programs: string[]; sections: string[]
  yearLevels: string[]; departments: string[]; librarians: string[]; visitorFields: string[]
  defaultReportPeriod: string; defaultReportUserType: string; retentionYears: number
  qrHeading: string; qrInstructions: string; roomBookingUrl: string
}
export const defaultSettings: LibrarySettings = {
  libraryName:'Life College Library',timezone:'Asia/Manila',opensAt:'07:00',closesAt:'18:00',
  qrExpiryMinutes:1440,duplicateWindowMinutes:5,academicYear:'2026-2027',semester:'1st Semester',
  programs:['BS-ENTREP','BS-ENTREP-FE','BS-ENTREP-TE','BS-ENTREP-SE','BS-ENTREP-AE','BS-ENTREP-CE'],sections:['1A','1B','2A','2B'],
  yearLevels:['1st Year','2nd Year','3rd Year','4th Year'],departments:['Academic Affairs','Administration','Student Services','Library Services','Finance'],
  librarians:['Library Registrar'],visitorFields:['Full name','Organization','Purpose of visit','Contact number'],
  defaultReportPeriod:'Monthly',defaultReportUserType:'All',retentionYears:5,qrHeading:'Scan to record your visit',
  qrInstructions:'Use your school Google account to verify your identity and record your library check-in.',roomBookingUrl:''
}
import {apiRequest} from './api'
export type SettingsAudit = {
  id:string; action:string; user:string; actorId:number|null; actorEmail:string|null
  changedFields:string[]; beforeValues:Record<string,unknown>|null; afterValues:Record<string,unknown>|null; at:string
}
export type SettingsResponse = {settings:LibrarySettings;audit:SettingsAudit[];configured:boolean}
export const getLibrarySettings = () => apiRequest<SettingsResponse>('/api/library/settings')
export const saveLibrarySettings = (settings:LibrarySettings) => apiRequest<SettingsResponse>('/api/library/settings',{method:'PUT',body:JSON.stringify(settings)})
export const getDisplaySettings = () => apiRequest<Pick<LibrarySettings,'libraryName'|'qrHeading'|'qrInstructions'|'roomBookingUrl'>>('/api/library/settings/display')

