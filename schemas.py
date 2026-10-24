"""Pydantic models: request validation and response shapes."""
from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

PHONE_PATTERN = r"^\+?[0-9\s\-()]{7,20}$"


class StudentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, pattern=PHONE_PATTERN)
    course: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    enrollment_date: Optional[date] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def dob_not_future(cls, v: date) -> date:
        if v >= date.today():
            raise ValueError("date_of_birth must be in the past")
        return v

    @model_validator(mode="after")
    def check_contact_and_dates(self):
        if not self.email and not self.phone:
            raise ValueError("at least one of email or phone is required")
        if self.enrollment_date and self.enrollment_date < self.date_of_birth:
            raise ValueError("enrollment_date cannot be before date_of_birth")
        return self


class StudentCreate(StudentBase):
    """Body for POST and PUT (full record)."""


class StudentUpdate(BaseModel):
    """Body for PATCH: every field optional, only sent fields change."""
    name: Optional[str] = None
    date_of_birth: Optional[date] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    course: Optional[str] = None
    address: Optional[str] = None
    enrollment_date: Optional[date] = None


class Student(StudentBase):
    id: int


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    records_used: int
