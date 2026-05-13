from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from database.models import Target
from models.schemas import TargetCreate, TargetUpdate, TargetType
from datetime import datetime


class TargetService:
    """Service for managing reconnaissance targets"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_target(self, target_data: TargetCreate) -> Target:
        """Create a new target"""
        import uuid
        target = Target(
            id=str(uuid.uuid4()),
            scope_id=target_data.scope_id,
            type=target_data.type,
            value=target_data.value,
            description=target_data.description,
            enabled=target_data.enabled
        )
        self.db.add(target)
        self.db.commit()
        self.db.refresh(target)
        return target
    
    def get_target(self, target_id: int) -> Optional[Target]:
        """Get target by ID"""
        return self.db.query(Target).filter(Target.id == target_id).first()
    
    def list_targets(
        self, 
        scope_id: Optional[int] = None,
        target_type: Optional[TargetType] = None,
        enabled_only: bool = False,
        skip: int = 0, 
        limit: int = 100
    ) -> List[Target]:
        """List targets with filters"""
        query = self.db.query(Target)
        
        if scope_id:
            query = query.filter(Target.scope_id == scope_id)
        if target_type:
            query = query.filter(Target.target_type == target_type)
        if enabled_only:
            query = query.filter(Target.enabled == True)
        
        return query.offset(skip).limit(limit).all()
    
    def update_target(self, target_id: int, target_data: TargetUpdate) -> Optional[Target]:
        """Update target"""
        target = self.get_target(target_id)
        if not target:
            return None
        
        update_dict = target_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(target, key, value)
        
        target.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(target)
        return target
    
    def delete_target(self, target_id: int) -> bool:
        """Delete a target"""
        target = self.get_target(target_id)
        if not target:
            return False
        self.db.delete(target)
        self.db.commit()
        return True
    
    def enable_target(self, target_id: int) -> Optional[Target]:
        """Enable a target"""
        target = self.get_target(target_id)
        if not target:
            return None
        target.enabled = True
        target.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(target)
        return target
    
    def disable_target(self, target_id: int) -> Optional[Target]:
        """Disable a target"""
        target = self.get_target(target_id)
        if not target:
            return None
        target.enabled = False
        target.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(target)
        return target
