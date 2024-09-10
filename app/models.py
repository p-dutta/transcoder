"""
This File is used to store models for our ORM Models, For Postgres Database
"""
from typing import Hashable
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import text
from sqlalchemy.sql.sqltypes import TIMESTAMP

from .database import Base
from .utils import JobStatusEnum, JobStateEnum, ProtectionTypeEnum, DrmTypeEnum


class Post(Base):
    __tablename__ = "posts"  # create a table name
    id = Column(Integer, primary_key=True, nullable=False)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    published = Column(Boolean, nullable=False, server_default='FALSE')
    created_at = Column(TIMESTAMP(timezone=True),
                        nullable=False, server_default=text('now()'))
    owner_id = Column(Integer, ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False)

    owner = relationship("User")  # Fetches User Data for us


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, nullable=False)
    email = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True),
                        nullable=False, server_default=text('now()'))
    phone_number = Column(String)


# a user is only allowed to like a post once


class Vote(Base):
    __tablename__ = "votes"
    user_id = Column(Integer, ForeignKey(
        "users.id", ondelete="CASCADE"), primary_key=True)
    post_id = Column(Integer, ForeignKey(
        "posts.id", ondelete="CASCADE"), primary_key=True)


class AdminUsers(Base):
    __tablename__ = 'admin_users'

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True)
    username = Column(String, unique=True)
    first_name = Column(String)
    last_name = Column(String)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    role = Column(String)


class Todos(Base):
    __tablename__ = 'todos'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    priority = Column(Integer)
    complete = Column(Boolean, default=False)
    owner_id = Column(Integer, ForeignKey("admin_users.id"))


class Jobs(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(String)
    project_id = Column(String)
    template_id = Column(String)
    package_id = Column(String)
    content_id = Column(String)
    provider_id = Column(String)
    description = Column(String)
    custom_name = Column(String, unique=True)
    fully_qualified_name = Column(String)
    location = Column(String)
    input_uri = Column(String)
    output_uri = Column(String)
    created_by = Column(String)
    version = Column(Integer)
    duration_in_sec = Column(String)
    status = Column(Enum(JobStatusEnum), default=JobStatusEnum.WAITING)
    state = Column(Enum(JobStateEnum), default=JobStateEnum.INIT)
    created_at = Column(TIMESTAMP(timezone=True),
                        nullable=False, server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True),
                        nullable=False, server_default=text('now()'))


class JobTemplates(Base):
    __tablename__ = 'job_templates'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer)
    template_id = Column(String)
    description = Column(String)
    location = Column(String)
    topic = Column(String)
    custom_name = Column(String, unique=True)
    fully_qualified_name = Column(String)
    protection_type = Column(Enum(ProtectionTypeEnum), default=None)
    drm_type = Column(Enum(DrmTypeEnum), default=None)
    num_manifest_file = Column(String)
    container_format = Column(String)
    created_at = Column(TIMESTAMP(timezone=True),
                        nullable=False, server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True),
                        nullable=False, server_default=text('now()'))
