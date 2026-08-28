export type LibrarySettings = {
  libraryName: string; timezone: string; opensAt: string; closesAt: string
  qrExpiryMinutes: number; duplicateWindowMinutes: number
  academicYear: string; semester: string; programs: string[]; sections: string[]
  yearLevels: string[]; departments: string[]; librarians: string[]; visitorFields: string[]
  defaultReportPeriod: string; defaultReportUserType: string; retentionYears: number
  qrHeading: string; qrInstructions: string
}
export const defaultSettings: LibrarySettings = {
  libraryName:'Life College Library',timezone:'Asia/Manila',opensAt:'07:00',closesAt:'18:00',
  qrExpiryMinutes:1440,duplicateWindowMinutes:5,academicYear:'2026-2027',semester:'1st Semester',
  programs:['BS Information Technology','BS Business Administration','BS Psychology'],sections:['A','B','C'],
  yearLevels:['1st Year','2nd Year','3rd Year','4th Year'],departments:['Academic Affairs','Administration','Library Services'],
  librarians:['Library Registrar'],visitorFields:['Full name','Organization','Purpose of visit','Contact number'],
  defaultReportPeriod:'Monthly',defaultReportUserType:'All',retentionYears:5,qrHeading:'Scan to record your visit',
  qrInstructions:'Use your school Google account to verify your identity and record your library check-in.'
}
export function loadSettings(): LibrarySettings {try{const saved=JSON.parse(localStorage.getItem('library-settings')||'{}');if(saved.qrInstructions==='Use your school Google account to verify your identity. Scan once when entering and again when leaving.')delete saved.qrInstructions;return {...defaultSettings,...saved}}catch{return defaultSettings}}
export function saveSettings(settings:LibrarySettings){localStorage.setItem('library-settings',JSON.stringify(settings));const audit=JSON.parse(localStorage.getItem('settings-audit')||'[]');audit.unshift({id:crypto.randomUUID(),action:'Settings updated',user:'Library Registrar',at:new Date().toISOString()});localStorage.setItem('settings-audit',JSON.stringify(audit.slice(0,20)));dispatchEvent(new CustomEvent('library-settings-changed'))}

