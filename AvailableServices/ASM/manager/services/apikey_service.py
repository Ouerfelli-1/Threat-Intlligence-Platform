from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ..database.models import APIKey
from ..models.schemas import APIKeyCreate, APIKeyUpdate
from datetime import datetime
import base64


class APIKeyService:
    """Service for managing API keys"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def _encrypt_key(self, key: str) -> str:
        """Simple base64 encoding (replace with proper encryption in production)"""
        return base64.b64encode(key.encode()).decode()
    
    def _decrypt_key(self, encrypted_key: str) -> str:
        """Simple base64 decoding (replace with proper decryption in production)"""
        return base64.b64decode(encrypted_key.encode()).decode()
    
    def create_api_key(self, api_key_data: APIKeyCreate) -> APIKey:
        """Create a new API key"""
        api_key = APIKey(
            scope_id=api_key_data.scope_id,
            service_name=api_key_data.service_name,
            key_value=self._encrypt_key(api_key_data.key_value),
            enabled=api_key_data.enabled
        )
        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)
        return api_key
    
    def get_api_key(self, api_key_id: int, decrypt: bool = False) -> Optional[APIKey]:
        """Get API key by ID"""
        api_key = self.db.query(APIKey).filter(APIKey.id == api_key_id).first()
        if api_key and decrypt:
            # Create a copy with decrypted key for usage
            api_key.key_value = self._decrypt_key(api_key.key_value)
        return api_key
    
    def get_api_key_by_service(
        self, 
        scope_id: int, 
        service_name: str,
        decrypt: bool = False
    ) -> Optional[APIKey]:
        """Get API key by service name within a scope"""
        api_key = self.db.query(APIKey).filter(
            and_(
                APIKey.scope_id == scope_id, 
                APIKey.service_name == service_name,
                APIKey.enabled == True
            )
        ).first()
        if api_key and decrypt:
            api_key.key_value = self._decrypt_key(api_key.key_value)
        return api_key
    
    def list_api_keys(
        self,
        scope_id: Optional[int] = None,
        enabled_only: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[APIKey]:
        """List API keys with filters (never decrypted in list)"""
        query = self.db.query(APIKey)
        
        if scope_id:
            query = query.filter(APIKey.scope_id == scope_id)
        if enabled_only:
            query = query.filter(APIKey.enabled == True)
        
        return query.offset(skip).limit(limit).all()
    
    def update_api_key(self, api_key_id: int, api_key_data: APIKeyUpdate) -> Optional[APIKey]:
        """Update API key"""
        api_key = self.get_api_key(api_key_id)
        if not api_key:
            return None
        
        update_dict = api_key_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if key == 'key_value':
                setattr(api_key, key, self._encrypt_key(value))
            else:
                setattr(api_key, key, value)
        
        api_key.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(api_key)
        return api_key
    
    def delete_api_key(self, api_key_id: int) -> bool:
        """Delete an API key"""
        api_key = self.get_api_key(api_key_id)
        if not api_key:
            return False
        self.db.delete(api_key)
        self.db.commit()
        return True
    
    def enable_api_key(self, api_key_id: int) -> Optional[APIKey]:
        """Enable an API key"""
        api_key = self.get_api_key(api_key_id)
        if not api_key:
            return None
        api_key.enabled = True
        api_key.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(api_key)
        return api_key
    
    def disable_api_key(self, api_key_id: int) -> Optional[APIKey]:
        """Disable an API key"""
        api_key = self.get_api_key(api_key_id)
        if not api_key:
            return None
        api_key.enabled = False
        api_key.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(api_key)
        return api_key
