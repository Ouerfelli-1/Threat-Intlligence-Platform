"""
Scheduler Service
Monitors schedules in database and triggers jobs via Redis queue
"""
import os
import json
import redis
import time
import uuid
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SchedulerService:
    """Service that manages scheduled reconnaissance jobs"""
    
    def __init__(self):
        # Redis connection
        redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        
        # Database connection - use DATABASE_URL
        self.db_url = os.getenv('DATABASE_URL', 'postgresql://recon:changeme@database:5432/recon_manager')
        self.engine = create_engine(self.db_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # APScheduler
        self.scheduler = BackgroundScheduler()
        self.job_queue = 'recon_jobs'
        
        # Track loaded schedules
        self.loaded_schedules = {}
        
        logger.info(f"Scheduler initialized - DB: {self.db_url.split('@')[1] if '@' in self.db_url else 'configured'}")
    
    def create_job_in_db(self, scope_id: str, schedule_id: str, mode: str) -> str:
        """Create a job record in database"""
        try:
            job_id = str(uuid.uuid4())
            with self.engine.connect() as conn:
                query = text("""
                    INSERT INTO jobs (id, scope_id, schedule_id, mode, status, enabled, triggered_by, created_at)
                    VALUES (:job_id, :scope_id, :schedule_id, CAST(:mode AS reconmodeenum), 
                            CAST('PENDING' AS jobstatusenum), true, 'scheduler', NOW())
                    RETURNING id
                """)
                result = conn.execute(query, {
                    "job_id": job_id,
                    "scope_id": scope_id,
                    "schedule_id": schedule_id,
                    "mode": mode.upper()
                })
                conn.commit()
                return job_id
        except Exception as e:
            logger.error(f"Failed to create job in DB: {e}")
            return None
    
    def update_schedule_last_run(self, schedule_id: str):
        """Update schedule last_run timestamp"""
        try:
            with self.engine.connect() as conn:
                query = text("UPDATE schedules SET last_run = NOW() WHERE id = :id")
                conn.execute(query, {"id": schedule_id})
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to update schedule last_run: {e}")
    
    def trigger_scheduled_job(self, schedule_id: str, scope_id: str, mode: str):
        """Trigger a job from schedule"""
        try:
            logger.info(f"Triggering scheduled job - Schedule: {schedule_id}, Scope: {scope_id}, Mode: {mode}")
            
            # Create job in database
            job_id = self.create_job_in_db(scope_id, schedule_id, mode)
            
            if job_id:
                # Push job to Redis queue
                job_data = {
                    'job_id': job_id,
                    'scope_id': scope_id,
                    'schedule_id': schedule_id,
                    'mode': mode,
                    'triggered_by': 'scheduler'
                }
                
                self.redis_client.lpush(self.job_queue, json.dumps(job_data))
                logger.info(f"Job {job_id} queued successfully")
                
                # Update schedule last_run
                self.update_schedule_last_run(schedule_id)
            else:
                logger.error("Failed to create job in database")
                
        except Exception as e:
            logger.error(f"Failed to trigger scheduled job: {e}")
    
    def load_schedules_from_db(self):
        """Load all enabled schedules from database"""
        try:
            with self.engine.connect() as conn:
                query = text("""
                    SELECT s.id, s.scope_id, s.name, s.cron_expression, s.mode, sc.enabled as scope_enabled
                    FROM schedules s
                    JOIN scopes sc ON s.scope_id = sc.id
                    WHERE s.enabled = true AND sc.enabled = true
                """)
                result = conn.execute(query)
                schedules = result.fetchall()
                
                current_schedule_ids = set()
                
                for row in schedules:
                    schedule_id = row[0]
                    scope_id = row[1]
                    name = row[2]
                    cron_expr = row[3]
                    mode = str(row[4]).lower() if row[4] else 'passive'
                    
                    current_schedule_ids.add(schedule_id)
                    
                    # If schedule not loaded or cron changed, add/update it
                    if schedule_id not in self.loaded_schedules or self.loaded_schedules[schedule_id] != cron_expr:
                        try:
                            # Remove old job if exists
                            if schedule_id in self.loaded_schedules:
                                self.scheduler.remove_job(f"schedule_{schedule_id}")
                            
                            # Add new job
                            trigger = CronTrigger.from_crontab(cron_expr)
                            self.scheduler.add_job(
                                self.trigger_scheduled_job,
                                trigger=trigger,
                                id=f"schedule_{schedule_id}",
                                args=[schedule_id, scope_id, mode],
                                name=name,
                                replace_existing=True
                            )
                            
                            self.loaded_schedules[schedule_id] = cron_expr
                            logger.info(f"Loaded schedule {schedule_id}: {name} ({cron_expr})")
                            
                        except Exception as e:
                            logger.error(f"Failed to add schedule {schedule_id}: {e}")
                
                # Remove schedules that no longer exist or are disabled
                removed_schedules = set(self.loaded_schedules.keys()) - current_schedule_ids
                for schedule_id in removed_schedules:
                    try:
                        self.scheduler.remove_job(f"schedule_{schedule_id}")
                        del self.loaded_schedules[schedule_id]
                        logger.info(f"Removed schedule {schedule_id}")
                    except Exception as e:
                        logger.error(f"Failed to remove schedule {schedule_id}: {e}")
                
                logger.info(f"Loaded {len(self.loaded_schedules)} active schedules")
                
        except Exception as e:
            logger.error(f"Failed to load schedules: {e}")
    
    def run(self):
        """Main scheduler loop"""
        logger.info("Starting scheduler service...")
        
        # Start APScheduler
        self.scheduler.start()
        logger.info("APScheduler started")
        
        try:
            while True:
                # Reload schedules from database every 60 seconds
                self.load_schedules_from_db()
                time.sleep(60)
                
        except KeyboardInterrupt:
            logger.info("Shutting down scheduler...")
            self.scheduler.shutdown()


if __name__ == "__main__":
    service = SchedulerService()
    service.run()
