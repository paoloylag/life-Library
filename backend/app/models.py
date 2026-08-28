from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Librarian(Base):
    __tablename__="librarians"
    id:Mapped[int]=mapped_column(primary_key=True)
    email:Mapped[str]=mapped_column(String(255),unique=True,index=True)
    name:Mapped[str]=mapped_column(String(255))
    password_hash:Mapped[str]=mapped_column(String(255))
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)

class User(Base):
    __tablename__="users"
    id:Mapped[int]=mapped_column(primary_key=True); email:Mapped[str]=mapped_column(String(255),unique=True,index=True)
    name:Mapped[str]=mapped_column(String(255)); google_id:Mapped[str]=mapped_column(String(255),unique=True)
    avatar_url:Mapped[str|None]=mapped_column(String(500)); role:Mapped[str]=mapped_column(String(30),default="student")
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)
    profile:Mapped["StudentProfile|None"]=relationship(back_populates="user",uselist=False)

class StudentProfile(Base):
    __tablename__="student_profiles"
    id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),unique=True)
    student_number:Mapped[str]=mapped_column(String(50),unique=True,index=True); user_type:Mapped[str]=mapped_column(String(50),default="student")
    program:Mapped[str|None]=mapped_column(String(120)); section:Mapped[str|None]=mapped_column(String(120)); is_active:Mapped[bool]=mapped_column(Boolean,default=True)
    user:Mapped[User]=relationship(back_populates="profile")

class LibrarySession(Base):
    __tablename__="library_sessions"
    id:Mapped[int]=mapped_column(primary_key=True); session_date:Mapped[date]=mapped_column(Date,index=True)
    name:Mapped[str]=mapped_column(String(120)); token_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True)
    starts_at:Mapped[datetime]=mapped_column(DateTime(timezone=True)); expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    status:Mapped[str]=mapped_column(String(20),default="open",index=True); created_by:Mapped[int]=mapped_column(ForeignKey("librarians.id"))

class LibraryVisit(Base):
    __tablename__="library_visits"
    id:Mapped[int]=mapped_column(primary_key=True); student_profile_id:Mapped[int]=mapped_column(ForeignKey("student_profiles.id"),index=True)
    library_session_id:Mapped[int]=mapped_column(ForeignKey("library_sessions.id"),index=True); time_in:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    status:Mapped[str]=mapped_column(String(30),default="checked_in",index=True)
    source:Mapped[str]=mapped_column(String(20),default="qr"); adjusted_by:Mapped[int|None]=mapped_column(ForeignKey("librarians.id")); adjustment_note:Mapped[str|None]=mapped_column(Text)
    student:Mapped[StudentProfile]=relationship(); session:Mapped[LibrarySession]=relationship()




