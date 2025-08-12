#!/usr/bin/env python3
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, BigInteger, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class DownloadRequest(Base):
    __tablename__ = 'download_requests'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False)
    tiktok_url = Column(Text, nullable=False)
    request_type = Column(String(20))  # 'video', 'photos', 'audio'
    service_used = Column(String(50))  # 'snaptik', 'tikmate', etc.
    success = Column(Boolean, nullable=False)
    file_size = Column(BigInteger)  # in bytes
    files_count = Column(Integer, default=1)  # for photo carousels
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    processing_time = Column(Float)  # in seconds

class DatabaseManager:
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._connect()
        
    def _connect(self):
        """Connect to PostgreSQL database"""
        try:
            # Get database URL from environment
            db_host = os.getenv('DB_HOST', 'localhost')
            db_port = os.getenv('DB_PORT', '5432')
            db_name = os.getenv('DB_NAME', 'tiktok_bot')
            db_user = os.getenv('DB_USER', 'postgres')
            db_password = os.getenv('DB_PASSWORD', 'password')
            
            database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            
            logger.info("Connecting to PostgreSQL database...")
            self.engine = create_engine(database_url, echo=False)
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            
            # Create tables if they don't exist
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database setup completed successfully")
            
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
    
    def get_session(self) -> Session:
        """Get database session"""
        return self.SessionLocal()
    
    def get_or_create_user(self, telegram_id: int, username: str = None, 
                          first_name: str = None, last_name: str = None) -> User:
        """Get existing user or create new one"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter(User.telegram_id == telegram_id).first()
                
                if not user:
                    # Create new user
                    user = User(
                        telegram_id=telegram_id,
                        username=username,
                        first_name=first_name,
                        last_name=last_name
                    )
                    session.add(user)
                    session.commit()
                    session.refresh(user)
                    logger.info(f"Created new user: {telegram_id}")
                else:
                    # Update existing user info
                    updated = False
                    if username and user.username != username:
                        user.username = username
                        updated = True
                    if first_name and user.first_name != first_name:
                        user.first_name = first_name
                        updated = True
                    if last_name and user.last_name != last_name:
                        user.last_name = last_name
                        updated = True
                    
                    user.last_activity = datetime.utcnow()
                    
                    if updated:
                        session.commit()
                        logger.info(f"Updated user info: {telegram_id}")
                
                return user
                
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_or_create_user: {e}")
            raise
    
    def log_request(self, telegram_id: int, tiktok_url: str, request_type: str = None,
                   service_used: str = None, success: bool = True, file_size: int = None,
                   files_count: int = 1, error_message: str = None, 
                   processing_time: float = None) -> None:
        """Log download request"""
        try:
            with self.get_session() as session:
                request = DownloadRequest(
                    telegram_id=telegram_id,
                    tiktok_url=tiktok_url,
                    request_type=request_type,
                    service_used=service_used,
                    success=success,
                    file_size=file_size,
                    files_count=files_count,
                    error_message=error_message,
                    processing_time=processing_time
                )
                session.add(request)
                session.commit()
                logger.info(f"Logged request for user {telegram_id}: {success}")
                
        except SQLAlchemyError as e:
            logger.error(f"Database error in log_request: {e}")
    
    def get_user_stats(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get user statistics"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter(User.telegram_id == telegram_id).first()
                
                if not user:
                    return None
                
                # Get request statistics
                total_requests = session.query(DownloadRequest).filter(
                    DownloadRequest.telegram_id == telegram_id
                ).count()
                
                successful_requests = session.query(DownloadRequest).filter(
                    DownloadRequest.telegram_id == telegram_id,
                    DownloadRequest.success == True
                ).count()
                
                success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
                
                return {
                    'telegram_id': user.telegram_id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'member_since': user.created_at,
                    'last_activity': user.last_activity,
                    'total_requests': total_requests,
                    'successful_requests': successful_requests,
                    'success_rate': success_rate
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_user_stats: {e}")
            return None
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get overall service statistics"""
        try:
            with self.get_session() as session:
                total_users = session.query(User).count()
                total_requests = session.query(DownloadRequest).count()
                successful_requests = session.query(DownloadRequest).filter(
                    DownloadRequest.success == True
                ).count()
                
                success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
                
                return {
                    'total_users': total_users,
                    'total_requests': total_requests,
                    'successful_requests': successful_requests,
                    'success_rate': success_rate
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_service_stats: {e}")
            return {}

# Global database manager instance
_db_manager = None

def get_db_manager() -> DatabaseManager:
    """Get global database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
