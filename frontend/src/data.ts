export type UserType='Student'|'Faculty'|'Non-Teaching'|'Visitor'
export type SeedUser={name:string;number:string;userType:UserType;yearLevel:string;section:string;program:string;department:string}
export type Visit={id:number;date:string;academicYear:string;semester:string;userType:UserType;yearLevel:string;section:string;program:string;department:string;visitor:string;studentNumber:string;timeIn:string}
export const programs=['BS Information Technology','BS Business Administration','BS Hospitality Management','Senior High School']
export const sections=['Section A','Section B','Section C']
export const userTypes:UserType[]=['Student','Faculty','Non-Teaching','Visitor']
export const departments=['Academic Affairs','Administration','Student Services','Library Services','Finance']
export const years=['1st Year','2nd Year','3rd Year','4th Year']
export const users:SeedUser[]=[
{name:'Angela Reyes',number:'LC-2026-00124',userType:'Student',program:programs[0],yearLevel:'1st Year',section:'Section A',department:''},
{name:'Marcus Lim',number:'LC-2025-00817',userType:'Student',program:programs[1],yearLevel:'2nd Year',section:'Section B',department:''},
{name:'Sofia Navarro',number:'LC-2024-00309',userType:'Student',program:programs[2],yearLevel:'3rd Year',section:'Section C',department:''},
{name:'Daniel Cruz',number:'LC-2023-00542',userType:'Student',program:programs[0],yearLevel:'4th Year',section:'Section A',department:''},
{name:'Mika Santos',number:'LC-2025-00288',userType:'Student',program:programs[3],yearLevel:'2nd Year',section:'Section B',department:''},
{name:'Paolo Garcia',number:'LC-2024-00911',userType:'Student',program:programs[1],yearLevel:'3rd Year',section:'Section C',department:''},
{name:'Nina Flores',number:'LC-2026-00417',userType:'Student',program:programs[2],yearLevel:'1st Year',section:'Section A',department:''},
{name:'Ethan Ramos',number:'LC-2023-00726',userType:'Student',program:programs[0],yearLevel:'4th Year',section:'Section B',department:''},
{name:'Dr. Carla Mendoza',number:'FAC-0018',userType:'Faculty',program:'',yearLevel:'',section:'',department:'Academic Affairs'},
{name:'Prof. Luis Bautista',number:'FAC-0031',userType:'Faculty',program:'',yearLevel:'',section:'',department:'Academic Affairs'},
{name:'Prof. Aira Villanueva',number:'FAC-0044',userType:'Faculty',program:'',yearLevel:'',section:'',department:'Student Services'},
{name:'Grace Dela Rosa',number:'NTP-0012',userType:'Non-Teaching',program:'',yearLevel:'',section:'',department:'Library Services'},
{name:'Noel Castillo',number:'NTP-0025',userType:'Non-Teaching',program:'',yearLevel:'',section:'',department:'Administration'},
{name:'Rina Torres',number:'NTP-0038',userType:'Non-Teaching',program:'',yearLevel:'',section:'',department:'Finance'},
{name:'Juan Dela Cruz',number:'VIS-2026-0184',userType:'Visitor',program:'',yearLevel:'',section:'',department:'External Visitor'},
{name:'Maria Salazar',number:'VIS-2026-0217',userType:'Visitor',program:'',yearLevel:'',section:'',department:'External Visitor'},
]
export const visits:Visit[]=Array.from({length:128},(_,i)=>{
 const user=users[i%users.length],academicYear=i<72?'2026-2027':'2025-2026',semester=i%3===0?'2nd Semester':i%3===1?'1st Semester':'Summer'
 const month=academicYear==='2026-2027'?(5+(i%4)):(9+(i%3)),day=1+(i*5)%27,date=new Date(academicYear==='2026-2027'?2026:2025,month,day)
 const hour=8+(i*3)%10,minute=(i*7)%60,timeIn=new Date(date)
 timeIn.setHours(hour,minute)
 return{id:i+1,date:date.toISOString().slice(0,10),academicYear,semester,userType:user.userType,yearLevel:user.yearLevel,section:user.section,program:user.program,department:user.department,visitor:user.name,studentNumber:user.number,timeIn:timeIn.toISOString()}
})

