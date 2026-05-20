from pydantic import BaseModel, Field


class ReviewIssue(BaseModel):
    finding_id: str
    severity: str  # critical | warning
    description: str
    suggestion: str = ""


class ReviewCheck(BaseModel):
    dimension: str
    status: str  # pass | fail
    issues: list[ReviewIssue] = Field(default_factory=list)


class ReviewResult(BaseModel):
    review_id: str
    round: int = 1
    verdict: str  # approved | rejected
    checks: list[ReviewCheck] = Field(default_factory=list)
    feedback_to: str = ""  # Writer | Analyst
    feedback_message: str = ""
