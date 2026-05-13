from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from database.models import Schedule
from models.schemas import ScheduleCreate, ScheduleUpdate
from datetime import datetime


class ScheduleService:
    """Service for managing reconnaissance schedules"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_schedule(self, schedule_data: ScheduleCreate) -> Schedule:
        """Create a new schedule"""
        import uuid
        schedule = Schedule(
            id=str(uuid.uuid4()),
            scope_id=schedule_data.scope_id,
            name=schedule_data.name,
            mode=schedule_data.mode,
            cron_expression=schedule_data.cron_expression,
            enabled=schedule_data.enabled
        )
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule
    
    def get_schedule(self, schedule_id: int) -> Optional[Schedule]:
        """Get schedule by ID"""
        return self.db.query(Schedule).filter(Schedule.id == schedule_id).first()
    
    def list_schedules(
        self,
        scope_id: Optional[int] = None,
        target_id: Optional[int] = None,
        enabled_only: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[Schedule]:
        """List schedules with filters"""
        query = self.db.query(Schedule)
        
        if scope_id:
            query = query.filter(Schedule.scope_id == scope_id)
        if target_id:
            query = query.filter(Schedule.target_id == target_id)
        if enabled_only:
            query = query.filter(Schedule.enabled == True)
        
        return query.offset(skip).limit(limit).all()
    
    def update_schedule(self, schedule_id: int, schedule_data: ScheduleUpdate) -> Optional[Schedule]:
        """Update schedule"""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return None
        
        update_dict = schedule_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(schedule, key, value)
        
        schedule.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(schedule)
        return schedule
    
    def delete_schedule(self, schedule_id: int) -> bool:
        """Delete a schedule"""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return False
        self.db.delete(schedule)
        self.db.commit()
        return True
    
    def enable_schedule(self, schedule_id: int) -> Optional[Schedule]:
        """Enable a schedule"""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return None
        schedule.enabled = True
        schedule.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(schedule)
        return schedule
    
    def disable_schedule(self, schedule_id: int) -> Optional[Schedule]:
        """Disable a schedule"""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return None
        schedule.enabled = False
        schedule.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(schedule)
        return schedule
    
    def update_last_run(self, schedule_id: int) -> Optional[Schedule]:
        """Update last run timestamp"""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return None
        schedule.last_run = datetime.utcnow()
        self.db.commit()
        self.db.refresh(schedule)
        return schedule
    
    def get_enabled_schedules(self) -> List[Schedule]:
        """Get all enabled schedules for scheduler"""
        return self.db.query(Schedule).filter(Schedule.enabled == True).all()
