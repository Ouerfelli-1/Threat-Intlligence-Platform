from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from database.models import Scope, Target, DataSource, APIKey
from models.schemas import (
    ScopeCreate, ScopeUpdate, ScopeConfig, PassiveFeatures, ActiveFeatures, ReconParameters
)
import json
from datetime import datetime


class ScopeService:
    """Service for managing reconnaissance scopes"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_scope(self, scope_data: ScopeCreate) -> Scope:
        """Create a new scope"""
        import uuid
        config = scope_data.config or ScopeConfig()
        scope = Scope(
            id=str(uuid.uuid4()),
            name=scope_data.name,
            description=scope_data.description,
            enabled=scope_data.enabled,
            config=config.model_dump()
        )
        self.db.add(scope)
        self.db.commit()
        self.db.refresh(scope)
        return scope
    
    def get_scope(self, scope_id: int) -> Optional[Scope]:
        """Get scope by ID"""
        return self.db.query(Scope).filter(Scope.id == scope_id).first()
    
    def get_scope_by_name(self, name: str) -> Optional[Scope]:
        """Get scope by name"""
        return self.db.query(Scope).filter(Scope.name == name).first()
    
    def list_scopes(
        self, 
        skip: int = 0, 
        limit: int = 100,
        enabled_only: bool = False
    ) -> List[Scope]:
        """List all scopes with pagination"""
        query = self.db.query(Scope)
        if enabled_only:
            query = query.filter(Scope.enabled == True)
        return query.offset(skip).limit(limit).all()
    
    def update_scope(self, scope_id: int, scope_data: ScopeUpdate) -> Optional[Scope]:
        """Update scope configuration"""
        scope = self.get_scope(scope_id)
        if not scope:
            return None
        
        update_dict = scope_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if key in ['passive_features', 'active_features', 'parameters']:
                setattr(scope, key, value.model_dump() if value else {})
            else:
                setattr(scope, key, value)
        
        scope.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(scope)
        return scope
    
    def delete_scope(self, scope_id: int) -> bool:
        """Delete a scope"""
        scope = self.get_scope(scope_id)
        if not scope:
            return False
        self.db.delete(scope)
        self.db.commit()
        return True
    
    def enable_scope(self, scope_id: int) -> Optional[Scope]:
        """Enable a scope"""
        scope = self.get_scope(scope_id)
        if not scope:
            return None
        scope.enabled = True
        scope.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(scope)
        return scope
    
    def disable_scope(self, scope_id: int) -> Optional[Scope]:
        """Disable a scope"""
        scope = self.get_scope(scope_id)
        if not scope:
            return None
        scope.enabled = False
        scope.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(scope)
        return scope
    
    def update_passive_features(self, scope_id: int, features: PassiveFeatures) -> Optional[Scope]:
        """Update passive reconnaissance features"""
        scope = self.get_scope(scope_id)
        if not scope:
            return None
        scope.passive_features = features.model_dump()
        scope.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(scope)
        return scope
    
    def update_active_features(self, scope_id: int, features: ActiveFeatures) -> Optional[Scope]:
        """Update active reconnaissance features"""
        scope = self.get_scope(scope_id)
        if not scope:
            return None
        scope.active_features = features.model_dump()
        scope.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(scope)
        return scope
    
    def update_parameters(self, scope_id: int, parameters: ReconParameters) -> Optional[Scope]:
        """Update reconnaissance parameters"""
        scope = self.get_scope(scope_id)
        if not scope:
            return None
        scope.parameters = parameters.model_dump()
        scope.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(scope)
        return scope
    
    def get_enabled_targets(self, scope_id: int) -> List[Target]:
        """Get all enabled targets for a scope"""
        return self.db.query(Target).filter(
            and_(Target.scope_id == scope_id, Target.enabled == True)
        ).all()
    
    def get_enabled_sources(self, scope_id: int) -> List[DataSource]:
        """Get all enabled data sources for a scope"""
        return self.db.query(DataSource).filter(
            and_(DataSource.scope_id == scope_id, DataSource.enabled == True)
        ).all()
