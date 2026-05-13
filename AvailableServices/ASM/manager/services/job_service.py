from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from database.models import Job, JobStatusEnum
from models.schemas import JobCreate, JobUpdate
from datetime import datetime


class JobService:
    """Service for managing reconnaissance jobs"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_job(self, job_data: JobCreate) -> Job:
        """Create a new job"""
        import uuid
        job = Job(
            id=str(uuid.uuid4()),
            scope_id=job_data.scope_id,
            schedule_id=job_data.schedule_id,
            mode=job_data.mode,
            status=JobStatusEnum.PENDING,
            triggered_by=job_data.triggered_by
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job
    
    def get_job(self, job_id: int) -> Optional[Job]:
        """Get job by ID"""
        return self.db.query(Job).filter(Job.id == job_id).first()
    
    def list_jobs(
        self,
        scope_id: Optional[int] = None,
        target_id: Optional[int] = None,
        status: Optional[JobStatusEnum] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Job]:
        """List jobs with filters"""
        query = self.db.query(Job)
        
        if scope_id:
            query = query.filter(Job.scope_id == scope_id)
        if target_id:
            query = query.filter(Job.target_id == target_id)
        if status:
            query = query.filter(Job.status == status)
        
        return query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()
    
    def update_job(self, job_id: int, job_data: JobUpdate) -> Optional[Job]:
        """Update job"""
        job = self.get_job(job_id)
        if not job:
            return None
        
        update_dict = job_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(job, key, value)
        
        self.db.commit()
        self.db.refresh(job)
        return job
    
    def update_job_status(
        self, 
        job_id: int, 
        status: JobStatusEnum,
        error_message: Optional[str] = None
    ) -> Optional[Job]:
        """Update job status"""
        job = self.get_job(job_id)
        if not job:
            return None
        
        job.status = status
        
        if status == JobStatusEnum.RUNNING:
            job.started_at = datetime.utcnow()
        elif status in [JobStatusEnum.COMPLETED, JobStatusEnum.FAILED, JobStatusEnum.CANCELLED]:
            job.completed_at = datetime.utcnow()
        
        if error_message:
            job.error_message = error_message
        
        self.db.commit()
        self.db.refresh(job)
        return job
    
    def cancel_job(self, job_id: int) -> Optional[Job]:
        """Cancel a job"""
        return self.update_job_status(job_id, JobStatusEnum.CANCELLED)
    
    def get_pending_jobs(self, limit: int = 10) -> List[Job]:
        """Get pending jobs for processing"""
        return self.db.query(Job).filter(
            Job.status == JobStatusEnum.PENDING
        ).order_by(Job.created_at).limit(limit).all()
    
    def get_running_jobs(self) -> List[Job]:
        """Get currently running jobs"""
        return self.db.query(Job).filter(Job.status == JobStatusEnum.RUNNING).all()
