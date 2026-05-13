"""
Scheduler Service
Monitors schedules in database and triggers jobs via Redis queue
"""
import os
import json
import redis
import time
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
        self.redis_host = os.getenv('REDIS_HOST', 'redis')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_client = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            decode_responses=True
        )
        
        # Database connection
        db_user = os.getenv('POSTGRES_USER', 'recon')
        db_pass = os.getenv('POSTGRES_PASSWORD', 'recon123')
        db_host = os.getenv('POSTGRES_HOST', 'database')
        db_name = os.getenv('POSTGRES_DB', 'recon_db')
        
        self.db_url = f"postgresql://{db_user}:{db_pass}@{db_host}/{db_name}"
        self.engine = create_engine(self.db_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # APScheduler
        self.scheduler = BackgroundScheduler()
        self.job_queue = 'recon_jobs'
        
        # Track loaded schedules
        self.loaded_schedules = {}
        
        logger.info(f"Scheduler initialized - Redis: {self.redis_host}:{self.redis_port}, DB: {db_host}")
    
    def create_job_in_db(self, scope_id: int, target_id: int, schedule_id: int) -> int:
        """Create a job record in database"""
        try:
            with self.engine.connect() as conn:
                query = text("""
                    INSERT INTO jobs (scope_id, target_id, schedule_id, status, triggered_by, created_at)
                    VALUES (:scope_id, :target_id, :schedule_id, 'pending', 'scheduler', NOW())
                    RETURNING id
                """)
                result = conn.execute(query, {
                    "scope_id": scope_id,
                    "target_id": target_id,
                    "schedule_id": schedule_id
                })
                job_id = result.fetchone()[0]
                conn.commit()
                return job_id
        except Exception as e:
            logger.error(f"Failed to create job in DB: {e}")
            return None
    
    def update_schedule_last_run(self, schedule_id: int):
        """Update schedule last_run timestamp"""
        try:
            with self.engine.connect() as conn:
                query = text("UPDATE schedules SET last_run = NOW() WHERE id = :id")
                conn.execute(query, {"id": schedule_id})
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to update schedule last_run: {e}")
    
    def trigger_scheduled_job(self, schedule_id: int, scope_id: int, target_id: int):
        """Trigger a job from schedule"""
        try:
            logger.info(f"Triggering scheduled job - Schedule: {schedule_id}, Scope: {scope_id}, Target: {target_id}")
            
            # Create job in database
            job_id = self.create_job_in_db(scope_id, target_id, schedule_id)
            
            if job_id:
                # Push job to Redis queue
                job_data = {
                    'job_id': job_id,
                    'scope_id': scope_id,
                    'target_id': target_id,
                    'schedule_id': schedule_id
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
                    SELECT s.id, s.scope_id, s.target_id, s.name, s.cron_expression, sc.enabled as scope_enabled, t.enabled as target_enabled
                    FROM schedules s
                    JOIN scopes sc ON s.scope_id = sc.id
                    LEFT JOIN targets t ON s.target_id = t.id
                    WHERE s.enabled = true AND sc.enabled = true
                """)
                result = conn.execute(query)
                schedules = result.fetchall()
                
                current_schedule_ids = set()
                
                for row in schedules:
                    schedule_id = row[0]
                    scope_id = row[1]
                    target_id = row[2]
                    name = row[3]
                    cron_expr = row[4]
                    scope_enabled = row[5]
                    target_enabled = row[6]
                    
                    current_schedule_ids.add(schedule_id)
                    
                    # Skip if target is disabled
                    if target_id and not target_enabled:
                        logger.info(f"Skipping schedule {schedule_id} - target {target_id} disabled")
                        continue
                    
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
                                args=[schedule_id, scope_id, target_id],
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
                
                logger.info(f"Loaded {len(self.loaded_schedules)} schedules")
                
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
