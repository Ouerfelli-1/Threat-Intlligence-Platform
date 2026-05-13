from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ..database.models import DataSource, SourceType
from ..models.schemas import DataSourceCreate, DataSourceUpdate
from datetime import datetime


class DataSourceService:
    """Service for managing reconnaissance data sources"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_source(self, source_data: DataSourceCreate) -> DataSource:
        """Create a new data source"""
        source = DataSource(
            scope_id=source_data.scope_id,
            source_type=source_data.source_type,
            name=source_data.name,
            enabled=source_data.enabled,
            rate_limit=source_data.rate_limit,
            timeout=source_data.timeout
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source
    
    def get_source(self, source_id: int) -> Optional[DataSource]:
        """Get data source by ID"""
        return self.db.query(DataSource).filter(DataSource.id == source_id).first()
    
    def get_source_by_name(self, scope_id: int, name: str) -> Optional[DataSource]:
        """Get data source by name within a scope"""
        return self.db.query(DataSource).filter(
            and_(DataSource.scope_id == scope_id, DataSource.name == name)
        ).first()
    
    def list_sources(
        self,
        scope_id: Optional[int] = None,
        source_type: Optional[SourceType] = None,
        enabled_only: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[DataSource]:
        """List data sources with filters"""
        query = self.db.query(DataSource)
        
        if scope_id:
            query = query.filter(DataSource.scope_id == scope_id)
        if source_type:
            query = query.filter(DataSource.source_type == source_type)
        if enabled_only:
            query = query.filter(DataSource.enabled == True)
        
        return query.offset(skip).limit(limit).all()
    
    def update_source(self, source_id: int, source_data: DataSourceUpdate) -> Optional[DataSource]:
        """Update data source"""
        source = self.get_source(source_id)
        if not source:
            return None
        
        update_dict = source_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(source, key, value)
        
        source.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(source)
        return source
    
    def delete_source(self, source_id: int) -> bool:
        """Delete a data source"""
        source = self.get_source(source_id)
        if not source:
            return False
        self.db.delete(source)
        self.db.commit()
        return True
    
    def enable_source(self, source_id: int) -> Optional[DataSource]:
        """Enable a data source"""
        source = self.get_source(source_id)
        if not source:
            return None
        source.enabled = True
        source.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(source)
        return source
    
    def disable_source(self, source_id: int) -> Optional[DataSource]:
        """Disable a data source"""
        source = self.get_source(source_id)
        if not source:
            return None
        source.enabled = False
        source.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(source)
        return source
    
    def update_last_used(self, source_id: int) -> Optional[DataSource]:
        """Update last used timestamp"""
        source = self.get_source(source_id)
        if not source:
            return None
        source.last_used = datetime.utcnow()
        self.db.commit()
        self.db.refresh(source)
        return source
