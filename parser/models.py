from pydantic import BaseModel, Field
from typing import List, Optional

class PersonalInfo(BaseModel):
    name: Optional[str] = Field(None, description="Full name of the candidate")
    headline: Optional[str] = Field(None, description="Professional headline or title")
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    location: Optional[str] = Field(None, description="Candidate's location (city, state, country)")
    address: Optional[str] = Field(None)
    linkedin: List[str] = Field(default_factory=list)
    github: List[str] = Field(default_factory=list)
    websites: List[str] = Field(default_factory=list)

class Skills(BaseModel):
    explicit: List[str] = Field(default_factory=list, description="Skills explicitly listed in a skills section")
    from_experience: List[str] = Field(default_factory=list, description="Skills mentioned within experience")
    from_projects: List[str] = Field(default_factory=list, description="Skills mentioned within projects")

class Score(BaseModel):
    type: Optional[str] = None
    value: Optional[str] = None
    scale: Optional[str] = None
    raw: Optional[str] = None

class EducationEntry(BaseModel):
    level: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    branch: Optional[str] = None
    group: Optional[str] = None
    specialization: Optional[str] = None

    institution: Optional[str] = None
    college: Optional[str] = None
    school: Optional[str] = None
    university: Optional[str] = None
    board: Optional[str] = None

    location: Optional[str] = None

    start_date: Optional[str] = None
    end_date: Optional[str] = None

    start_year: Optional[str] = None
    end_year: Optional[str] = None

    graduation_year: Optional[str] = None
    passing_year: Optional[str] = None

    gpa: Optional[str] = None
    cgpa: Optional[str] = None
    gpa_scale: Optional[str] = None

    percentage: Optional[str] = None

    marks_obtained: Optional[str] = None
    maximum_marks: Optional[str] = None

    grade: Optional[str] = None
    rank: Optional[str] = None

    score: Optional[Score] = None

    details: List[str] = Field(default_factory=list)

    source_text: Optional[str] = None
    page: Optional[int] = None
    confidence: Optional[float] = None

class ExperienceEntry(BaseModel):
    job_title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration: Optional[str] = None
    is_current: bool = False
    description: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)

class ProjectEntry(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    role: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    url: Optional[str] = None

class ResumeSchema(BaseModel):
    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    summary: Optional[str] = None
    skills: Skills = Field(default_factory=Skills)
    education: List[EducationEntry] = Field(default_factory=list)
    experience: List[ExperienceEntry] = Field(default_factory=list)
    projects: List[ProjectEntry] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    awards: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    publications: List[str] = Field(default_factory=list)
    volunteer: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    courses: List[str] = Field(default_factory=list)
    training: List[str] = Field(default_factory=list)
    raw_text: Optional[str] = None
    unmapped_information: List[str] = Field(default_factory=list)

    def to_dict(self):
        return self.model_dump()

    def to_json(self):
        return self.model_dump_json(indent=2)
