#!/usr/bin/env python3
"""
Queue Worker - Processes jobs from the database queue
Runs as a separate process alongside Flask app
"""
import time
import sys
import signal
import json
from queue_manager import QueueManager
from database import SessionLocal
from models import Job

# Global flag for graceful shutdown
shutdown_requested = False

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    global shutdown_requested
    print("\n[WORKER] Shutdown requested, finishing current job...")
    shutdown_requested = True

def process_job(job):
    """
    Process a single job

    Args:
        job: Job object to process
    """
    try:
        print(f"[WORKER] Starting job {job.job_id} (mode: {job.mode}, processing_mode: {job.processing_mode})")

        # Import processing functions (lazy import to avoid loading Flask app at startup)
        from app import prepare_audio_job, process_merged_files_job, update_job_status

        # Get job parameters
        if not job.input_path:
            print(f"[WORKER] Job {job.job_id} has no input_path")
            update_job_status(job.job_id, 'error', error_message="No input path")
            return

        # Check if it's a batch job (multiple files)
        is_batch = job.file_count > 1

        if is_batch:
            # Batch processing: input_path contains JSON array of file paths
            file_paths = json.loads(job.input_path)

            # Call batch processing function
            process_merged_files_job(
                job_id=job.job_id,
                file_paths=file_paths,
                original_filenames=job.filename.split(', '),  # Reconstruct filenames
                mode=job.processing_mode or 'smart_doc',
                chunking=job.chunking_strategy or 'standard',
                language=job.language or 'auto',
                use_diarization=job.use_diarization,
                doc_type=job.doc_type or 'other',
                user_id=job.user_id
            )
        else:
            # Single file processing
            prepare_audio_job(
                job_id=job.job_id,
                input_path=job.input_path,
                original_filename=job.filename or 'unknown',
                mode=job.processing_mode or 'smart_doc',
                chunking=job.chunking_strategy or 'standard',
                language=job.language or 'auto',
                use_diarization=job.use_diarization,
                doc_type=job.doc_type or 'other',
                user_id=job.user_id
            )

        print(f"[WORKER] Job {job.job_id} completed")

    except Exception as e:
        print(f"[WORKER] Error processing job {job.job_id}: {e}")
        import traceback
        traceback.print_exc()

        # Update job status to error
        from app import update_job_status
        update_job_status(
            job.job_id,
            'error',
            error_message=str(e)
        )

def run_worker(poll_interval=5):
    """
    Main worker loop

    Args:
        poll_interval: Seconds to wait between polls (default: 5)
    """
    print(f"[WORKER] Starting worker (poll interval: {poll_interval}s)")
    print("[WORKER] Press Ctrl+C to stop")

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    while not shutdown_requested:
        try:
            # Get next job from queue
            job = QueueManager.get_next_job()

            if job:
                # Process the job
                process_job(job)

                # Update queue positions after processing
                QueueManager.update_queue_positions()
            else:
                # No jobs in queue, wait before polling again
                time.sleep(poll_interval)

        except KeyboardInterrupt:
            print("\n[WORKER] Interrupted by user")
            break
        except Exception as e:
            print(f"[WORKER] Error in worker loop: {e}")
            # Wait before retrying
            time.sleep(poll_interval)

    print("[WORKER] Worker stopped")

if __name__ == "__main__":
    # Optional: accept poll interval as command line argument
    poll_interval = 5
    if len(sys.argv) > 1:
        try:
            poll_interval = int(sys.argv[1])
        except ValueError:
            print(f"Invalid poll interval: {sys.argv[1]}, using default: 5s")

    run_worker(poll_interval)
