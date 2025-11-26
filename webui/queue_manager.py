"""
Queue Manager for job processing
Simple FIFO queue system using database
"""
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
from database import SessionLocal
from models import Job, User


class QueueManager:
    """Manages job queue operations"""

    @staticmethod
    def enqueue_job(job_id, user_id, mode, filename=None, file_count=1,
                    input_path=None, processing_mode=None, chunking_strategy=None,
                    language=None, doc_type=None, use_diarization=True):
        """
        Add a new job to the queue

        Args:
            job_id: Unique job identifier
            user_id: User who created the job
            mode: 'srt' or 'document'
            filename: Original filename
            file_count: Number of files to process
            input_path: Path to input file
            processing_mode: 'text', 'srt', 'smart_doc'
            chunking_strategy: 'standard', 'strong_head'
            language: 'auto', 'fr', 'en', etc.
            doc_type: 'course', 'meeting', etc.
            use_diarization: Enable speaker diarization

        Returns:
            Job object with queue position and estimated wait time
        """
        db = SessionLocal()
        try:
            # Create job with queued status
            job = Job(
                job_id=job_id,
                user_id=user_id,
                status='queued',
                mode=mode,
                filename=filename,
                file_count=file_count,
                queued_at=datetime.utcnow(),
                input_path=input_path,
                processing_mode=processing_mode,
                chunking_strategy=chunking_strategy,
                language=language,
                doc_type=doc_type,
                use_diarization=use_diarization
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            # Update queue positions
            QueueManager.update_queue_positions()

            # Refresh to get updated position
            db.refresh(job)

            print(f"[QUEUE] Job {job_id} enqueued at position {job.queue_position}")
            return job

        except Exception as e:
            db.rollback()
            print(f"[QUEUE] Error enqueuing job: {e}")
            raise
        finally:
            db.close()

    @staticmethod
    def get_next_job():
        """
        Get the next job to process (FIFO)

        Returns:
            Job object or None if queue is empty
        """
        db = SessionLocal()
        try:
            # Get oldest queued job
            job = db.query(Job).filter(
                Job.status == 'queued'
            ).order_by(Job.queued_at.asc()).first()

            if job:
                # Mark as processing
                job.status = 'processing'
                job.started_at = datetime.utcnow()
                job.queue_position = None
                db.commit()

                print(f"[QUEUE] Processing job {job.job_id}")

                # Update remaining queue positions
                QueueManager.update_queue_positions()

            return job

        except Exception as e:
            db.rollback()
            print(f"[QUEUE] Error getting next job: {e}")
            return None
        finally:
            db.close()

    @staticmethod
    def update_queue_positions():
        """Update queue positions and estimated wait times for all queued jobs"""
        db = SessionLocal()
        try:
            # Get all queued jobs ordered by queued_at
            queued_jobs = db.query(Job).filter(
                Job.status == 'queued'
            ).order_by(Job.queued_at.asc()).all()

            if not queued_jobs:
                return

            # Calculate average processing time from last 10 completed jobs
            avg_time = QueueManager._get_average_processing_time(db)

            # Update positions and estimates
            for position, job in enumerate(queued_jobs, start=1):
                job.queue_position = position

                # Estimate wait time: (position - 1) * avg_time
                # Position 1 is next, so no wait time
                if position == 1:
                    job.estimated_wait_seconds = 0
                else:
                    job.estimated_wait_seconds = int((position - 1) * avg_time)

            db.commit()
            print(f"[QUEUE] Updated positions for {len(queued_jobs)} jobs")

        except Exception as e:
            db.rollback()
            print(f"[QUEUE] Error updating positions: {e}")
        finally:
            db.close()

    @staticmethod
    def _get_average_processing_time(db):
        """
        Calculate average processing time from recent completed jobs

        Args:
            db: Database session

        Returns:
            Average processing time in seconds (default: 120)
        """
        # Get last 10 completed jobs with processing time
        recent_jobs = db.query(Job).filter(
            and_(
                Job.status == 'completed',
                Job.started_at.isnot(None),
                Job.completed_at.isnot(None)
            )
        ).order_by(Job.completed_at.desc()).limit(10).all()

        if not recent_jobs:
            # Default: 2 minutes if no history
            return 120

        # Calculate average
        total_time = sum(
            (job.completed_at - job.started_at).total_seconds()
            for job in recent_jobs
        )
        avg_time = total_time / len(recent_jobs)

        return max(avg_time, 30)  # Minimum 30 seconds

    @staticmethod
    def get_queue_status():
        """
        Get current queue status

        Returns:
            dict with queue information
        """
        db = SessionLocal()
        try:
            queued_count = db.query(Job).filter(Job.status == 'queued').count()
            processing_count = db.query(Job).filter(Job.status == 'processing').count()

            # Get first job in queue for estimated wait
            first_job = db.query(Job).filter(
                Job.status == 'queued'
            ).order_by(Job.queued_at.asc()).first()

            estimated_wait = first_job.estimated_wait_seconds if first_job else 0

            return {
                'queued': queued_count,
                'processing': processing_count,
                'estimated_wait_seconds': estimated_wait,
                'is_saturated': queued_count > 3  # Consider saturated if >3 jobs waiting
            }

        finally:
            db.close()

    @staticmethod
    def cancel_job(job_id):
        """
        Cancel a queued job

        Args:
            job_id: Job identifier

        Returns:
            True if cancelled, False otherwise
        """
        db = SessionLocal()
        try:
            job = db.query(Job).filter(
                and_(
                    Job.job_id == job_id,
                    Job.status == 'queued'
                )
            ).first()

            if job:
                job.status = 'cancelled'
                job.completed_at = datetime.utcnow()
                db.commit()

                print(f"[QUEUE] Job {job_id} cancelled")

                # Update remaining queue positions
                QueueManager.update_queue_positions()

                return True

            return False

        except Exception as e:
            db.rollback()
            print(f"[QUEUE] Error cancelling job: {e}")
            return False
        finally:
            db.close()

    @staticmethod
    def get_user_queue_info(user_id):
        """
        Get queue information for a specific user

        Args:
            user_id: User identifier

        Returns:
            dict with user's queue info or None
        """
        db = SessionLocal()
        try:
            # Get user's queued job (should only be one at a time)
            job = db.query(Job).filter(
                and_(
                    Job.user_id == user_id,
                    Job.status == 'queued'
                )
            ).order_by(Job.queued_at.desc()).first()

            if not job:
                return None

            return {
                'job_id': job.job_id,
                'position': job.queue_position,
                'estimated_wait_seconds': job.estimated_wait_seconds,
                'queued_at': job.queued_at.isoformat() if job.queued_at else None
            }

        finally:
            db.close()
