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
  programs:['BS Information Technology','BS Business Administration','BS Psychology'],sections:['A','B','C'],
  yearLevels:['1st Year','2nd Year','3rd Year','4th Year'],departments:['Academic Affairs','Administration','Library Services'],
  librarians:['Library Registrar'],visitorFields:['Full name','Organization','Purpose of visit','Contact number'],
  defaultReportPeriod:'Monthly',defaultReportUserType:'All',retentionYears:5,qrHeading:'Scan to record your visit',
  qrInstructions:'Use your school Google account to verify your identity and record your library check-in.',roomBookingUrl:''
}
import {apiRequest} from './api'
export type SettingsAudit = {id:string;action:string;user:string;at:string}
export type SettingsResponse = {settings:LibrarySettings;audit:SettingsAudit[];configured:boolean}
export const getLibrarySettings = () => apiRequest<SettingsResponse>('/api/library/settings')
export const saveLibrarySettings = (settings:LibrarySettings) => apiRequest<SettingsResponse>('/api/library/settings',{method:'PUT',body:JSON.stringify(settings)})
export const getDisplaySettings = () => apiRequest<Pick<LibrarySettings,'libraryName'|'qrHeading'|'qrInstructions'|'roomBookingUrl'>>('/api/library/settings/display')

