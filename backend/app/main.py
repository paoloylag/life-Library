from datetime import datetime,time,timezone
from authlib.integrations.starlette_client import OAuth
from fastapi import Depends,FastAPI,HTTPException,Request,Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import or_,select,update
from sqlalchemy.orm import selectinload
from starlette.middleware.sessions import SessionMiddleware
from app.auth import current_librarian,current_user,issue_librarian,issue_student,verify_password
from app.config import settings
from app.database import get_db
from app.models import Librarian,LibrarySession,LibraryVisit,StudentProfile,User
from app.services import scan,token_pair
app=FastAPI(title="Library Attendance API")
app.add_middleware(SessionMiddleware,secret_key=settings.secret_key)
app.add_middleware(CORSMiddleware,allow_origins=[settings.frontend_url],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
oauth=OAuth();oauth.register(name="google",client_id=settings.google_client_id,client_secret=settings.google_client_secret,server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",client_kwargs={"scope":"openid email profile"})
@app.get("/api/health")
async def health():return {"status":"ok"}
@app.get("/api/auth/google")
async def login(request:Request,next:str="/"):request.session["next"]=next if next.startswith("/") else "/";return await oauth.google.authorize_redirect(request,settings.google_redirect_uri,hd=settings.google_allowed_domain)
@app.get("/api/auth/google/callback")
async def callback(request:Request,db=Depends(get_db)):
    info=(await oauth.google.authorize_access_token(request))["userinfo"]
    if info["email"].split("@")[-1].lower()!=settings.google_allowed_domain.lower():raise HTTPException(403,"Use your school Google account")
    user=await db.scalar(select(User).where(or_(User.google_id==info["sub"],User.email==info["email"])))
    if not user:user=User(email=info["email"],name=info["name"],google_id=info["sub"],avatar_url=info.get("picture"));db.add(user)
    await db.commit();await db.refresh(user);response=RedirectResponse(settings.frontend_url+request.session.pop("next","/"));response.set_cookie("library_session",issue_student(user.id),httponly=True,samesite="lax",max_age=43200);return response
@app.post("/api/admin/login")
async def admin_login(request:Request,db=Depends(get_db)):
    body=await request.json()
    librarian=await db.scalar(select(Librarian).where(Librarian.email==str(body.get("email","")).strip().lower(),Librarian.is_active.is_(True)))
    if not librarian or not verify_password(str(body.get("password","")),librarian.password_hash):raise HTTPException(401,"Invalid email or password")
    response=Response(status_code=204);response.set_cookie("librarian_session",issue_librarian(librarian.id),httponly=True,samesite="lax",max_age=28800);return response
@app.get("/api/admin/me")
async def admin_me(librarian=Depends(current_librarian)):return {"id":librarian.id,"name":librarian.name,"email":librarian.email}
@app.post("/api/admin/logout")
async def admin_logout():
    response=Response(status_code=204);response.delete_cookie("librarian_session");return response
@app.get("/api/auth/me")
async def me(user=Depends(current_user)):return {"id":user.id,"name":user.name,"email":user.email,"role":user.role}
@app.post("/api/library/sessions")
async def create_session(librarian=Depends(current_librarian),db=Depends(get_db)):
    now=datetime.now(timezone.utc);await db.execute(update(LibrarySession).where(LibrarySession.session_date==now.date(),LibrarySession.status=="open").values(status="closed"));raw,h=token_pair();row=LibrarySession(session_date=now.date(),name="Library attendance",token_hash=h,starts_at=now,expires_at=datetime.combine(now.date(),time.max,tzinfo=timezone.utc),status="open",created_by=librarian.id);db.add(row);await db.commit();return {"scan_url":f"{settings.frontend_url}/scan/{raw}","expires_at":row.expires_at}
@app.post("/api/library/scan/{token}")
async def record(token:str,user=Depends(current_user),db=Depends(get_db)):
    action,visit=await scan(db,token,user);return {"action":action,"check_in_time":visit.time_in}
@app.get("/api/library/dashboard")
async def dashboard(librarian=Depends(current_librarian),db=Depends(get_db)):
    today=datetime.now(timezone.utc).date();rows=(await db.scalars(select(LibraryVisit).join(LibrarySession).where(LibrarySession.session_date==today).options(selectinload(LibraryVisit.student).selectinload(StudentProfile.user)).order_by(LibraryVisit.time_in.desc()))).all();return {"check_in_count":len(rows),"visit_count":len(rows),"visits":[{"id":v.id,"name":v.student.user.name,"student_number":v.student.student_number,"check_in_time":v.time_in,"status":"checked_in"} for v in rows]}



