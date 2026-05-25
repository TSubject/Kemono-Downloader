import os
import queue
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import cloudscraper
import requests
from curl_cffi import requests as cffi_requests
from PyQt5.QtCore import QThread, pyqtSignal

from PIL import Image
import imagehash
from ...core.database_manager import DatabaseManager

from ...core.bunkr_client import fetch_bunkr_data
from ...core.pixeldrain_client import fetch_pixeldrain_data
from ...core.saint2_client import fetch_saint2_data
from ...core.simpcity_client import fetch_single_simpcity_page
from ...services.drive_downloader import (
    download_mega_file as drive_download_mega_file,
    download_gofile_folder  
)
from ...utils.file_utils import clean_folder_name


class SimpCityDownloadThread(QThread):
    progress_signal = pyqtSignal(str)
    file_progress_signal = pyqtSignal(str, object)
    finished_signal = pyqtSignal(int, int, bool, list)
    overall_progress_signal = pyqtSignal(int, int)

    def __init__(self, url, post_id, output_dir, cookies, parent=None):
        super().__init__(parent)
        self.start_url = url
        self.post_id = post_id
        self.output_dir = output_dir
        self.cookies = cookies
        self.is_cancelled = False
        self.parent_app = parent
        self.image_queue = queue.Queue()
        self.service_queue = queue.Queue()
        self.counter_lock = threading.Lock()
        self.total_dl_count = 0
        self.total_skip_count = 0
        self.total_jobs_found = 0
        self.total_jobs_processed = 0
        self.processed_job_urls = set()
        
        self.db = DatabaseManager()

    def _check_pause_cancel(self):
        if self.is_cancelled or (self.parent_app and self.parent_app.cancellation_event.is_set()):
            self.is_cancelled = True
            return True
            
        if self.parent_app and self.parent_app.pause_event.is_set():
            self.progress_signal.emit("   Download paused...")
            while self.parent_app.pause_event.is_set():
                if self.is_cancelled or (self.parent_app and self.parent_app.cancellation_event.is_set()):
                    self.is_cancelled = True
                    return True
                time.sleep(0.5)
            self.progress_signal.emit("   Download resumed.")
            
        return self.is_cancelled

    def _smart_sleep(self, seconds):
        for _ in range(int(seconds * 10)):
            if self._check_pause_cancel(): return True
            time.sleep(0.1)
        return False

    def _record_to_db(self, filepath, filename):
        calculated_phash = None
        valid_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
        if os.path.splitext(filepath)[1].lower() in valid_exts:
            try:
                calculated_phash = str(imagehash.phash(Image.open(filepath), hash_size=16))
            except Exception:
                pass
        self.db.record_tagless_download(
            file_path=filepath,
            file_name=filename,
            file_hash=None,
            phash=calculated_phash
        )

    def cancel(self):
        self.is_cancelled = True

    class _ServiceLoggerAdapter:
        def __init__(self, signal_emitter, prefix=""):
            self.emit = signal_emitter
            self.prefix = prefix

        def __call__(self, msg, *args, **kwargs):
            self.info(msg, *args, **kwargs)
            
        def info(self, msg, *args, **kwargs): self.emit(f"{self.prefix}{str(msg) % args}")
        def error(self, msg, *args, **kwargs): self.emit(f"{self.prefix}❌ ERROR: {str(msg) % args}")
        def warning(self, msg, *args, **kwargs): self.emit(f"{self.prefix}⚠️ WARNING: {str(msg) % args}")

    def _log_interceptor(self, message):
        if "[SimpCity] Scraper found" in message or "[SimpCity] Scraping page" in message:
            pass
        else:
            self.progress_signal.emit(message)

    def _get_enriched_jobs(self, jobs_to_check):
        if not jobs_to_check:
            return []
            
        enriched_jobs = []
        bunkr_logger = self._ServiceLoggerAdapter(self.progress_signal.emit, prefix="      ")
        pixeldrain_logger = self._ServiceLoggerAdapter(self.progress_signal.emit, prefix="      ")
        saint2_logger = self._ServiceLoggerAdapter(self.progress_signal.emit, prefix="      ")
        
        for job in jobs_to_check:
            if self._check_pause_cancel(): break
            job_type = job.get('type')
            job_url = job.get('url')

            if job_type in ['image', 'saint2_direct', 'saint2']:
                enriched_jobs.append(job)
            elif (job_type == 'bunkr' and self.should_dl_bunkr) or \
                 (job_type == 'pixeldrain' and self.should_dl_pixeldrain):
                self.progress_signal.emit(f"   -> Checking {job_type} album for file count...")
                
                fetch_map = {
                    'bunkr': (fetch_bunkr_data, bunkr_logger),
                    'pixeldrain': (fetch_pixeldrain_data, pixeldrain_logger)
                }
                fetch_func, logger_adapter = fetch_map[job_type]
                album_name, files = fetch_func(job_url, logger_adapter)
                
                if files:
                    job['prefetched_files'] = files
                    job['prefetched_album_name'] = album_name
                    enriched_jobs.append(job)
        
        if enriched_jobs and not self.is_cancelled:
            summary_counts = Counter()
            current_page_file_count = 0
            for job in enriched_jobs:
                if job.get('prefetched_files'):
                    file_count = len(job['prefetched_files'])
                    summary_counts[job['type']] += file_count
                    current_page_file_count += file_count
                else:
                    summary_counts[job['type']] += 1
                    current_page_file_count += 1
            
            summary_parts = [f"{job_type} ({count})" for job_type, count in summary_counts.items()]
            self.progress_signal.emit(f"   [SimpCity] Content Found: {' | '.join(summary_parts)}")
            
            with self.counter_lock: self.total_jobs_found += current_page_file_count
            self.overall_progress_signal.emit(self.total_jobs_found, self.total_jobs_processed)

        return enriched_jobs

    def _download_single_image(self, job, album_path, session):
        filename = job['filename']
        filepath = os.path.join(album_path, filename)
        try:
            if os.path.exists(filepath):
                self.progress_signal.emit(f"   -> Skip (Image): '{filename}'")
                with self.counter_lock: self.total_skip_count += 1
                return
            self.progress_signal.emit(f"   -> Downloading (Image): '{filename}'...")
            response = session.get(job['url'], stream=True, timeout=180, headers={'Referer': self.start_url})
            response.raise_for_status()
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self._check_pause_cancel():
                        f.close()
                        os.remove(filepath)
                        return
                    f.write(chunk)
            if not self.is_cancelled:
                self._record_to_db(filepath, filename)
                with self.counter_lock: self.total_dl_count += 1
        except Exception as e:
            self.progress_signal.emit(f"      -> ❌ Image download failed for '{filename}': {e}")
            with self.counter_lock: self.total_skip_count += 1
        finally:
            if not self.is_cancelled:
                with self.counter_lock: self.total_jobs_processed += 1
                self.overall_progress_signal.emit(self.total_jobs_found, self.total_jobs_processed)

    def _image_worker(self, album_path):
        session = cloudscraper.create_scraper()
        while True:
            if self._check_pause_cancel(): break
            try:
                job = self.image_queue.get(timeout=1)
                if job is None: break
                self._download_single_image(job, album_path, session)
                self.image_queue.task_done()
            except queue.Empty:
                continue

    def _service_worker(self, album_path):
        while True:
            if self._check_pause_cancel(): break
            try:
                job = self.service_queue.get(timeout=1)
                if job is None: break
                
                job_type = job['type']
                job_url = job['url']
                
                if job_type in ['pixeldrain', 'bunkr']:
                    if (job_type == 'pixeldrain' and self.should_dl_pixeldrain) or \
                       (job_type == 'bunkr' and self.should_dl_bunkr):
                        self.progress_signal.emit(f"\n--- Processing Service ({job_type.capitalize()}): {job_url} ---")
                        self._download_album(job.get('prefetched_files', []), job_url, album_path)
                
                elif job_type in ['saint2', 'saint2_direct'] and self.should_dl_saint2:
                    self.progress_signal.emit(f"\n--- Processing Service (Saint2/Turbo): {job_url} ---")
                    saint2_logger = self._ServiceLoggerAdapter(self.progress_signal.emit, prefix="      ")
                    album_name, files = fetch_saint2_data(job_url, saint2_logger)
                    if files:
                        self._download_album(files, job_url, album_path)
                    with self.counter_lock: 
                        self.total_jobs_processed += 1
                        self.overall_progress_signal.emit(self.total_jobs_found, self.total_jobs_processed)
                
                elif job_type == 'mega' and self.should_dl_mega:
                    self.progress_signal.emit(f"\n--- Processing Service (Mega): {job_url} ---")
                    drive_download_mega_file(job_url, album_path, self.progress_signal.emit, self.file_progress_signal.emit)
                elif job_type == 'gofile' and self.should_dl_gofile:
                    self.progress_signal.emit(f"\n--- Processing Service (Gofile): {job_url} ---")
                    download_gofile_folder(job_url, album_path, self.progress_signal.emit, self.file_progress_signal.emit)
                
                self.service_queue.task_done()
            except queue.Empty:
                continue

    def _download_album(self, files_to_process, source_url, album_path):
        if not files_to_process: return
        
        session = cffi_requests.Session(impersonate="chrome120")
        
        for file_data in files_to_process:
            if self._check_pause_cancel(): return 
            filename = file_data.get('filename') or file_data.get('name')
            filepath = os.path.join(album_path, filename)
            
            try:
                if os.path.exists(filepath):
                    with self.counter_lock: self.total_skip_count += 1
                else:
                    self.progress_signal.emit(f"       -> Downloading: '{filename}'...")
                    
                    headers = file_data.get('headers', {'Referer': source_url})
                    req_cookies = file_data.get('cookies', {})
                    
                    response = session.get(file_data.get('url'), stream=True, timeout=180, headers=headers, cookies=req_cookies)
                    
                    content_type = response.headers.get('Content-Type', '')
                    if 'text/html' in content_type:
                        self.progress_signal.emit(f"       ❌ Blocked by CDN! Downloaded a 42KB HTML page instead of the video.")
                        with self.counter_lock: self.total_skip_count += 1
                        continue
                        
                    response.raise_for_status()
                    
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if self._check_pause_cancel(): 
                                f.close()
                                os.remove(filepath)
                                return
                            f.write(chunk)
                            
                    if not self.is_cancelled:
                        self._record_to_db(filepath, filename)
                        with self.counter_lock: self.total_dl_count += 1
            except Exception as e:
                self.progress_signal.emit(f"       ❌ Download Error: {e}")
                with self.counter_lock: self.total_skip_count += 1
            finally:
                if not self.is_cancelled:
                    with self.counter_lock: self.total_jobs_processed += 1
                    self.overall_progress_signal.emit(self.total_jobs_found, self.total_jobs_processed)
    
    def run(self):
        self.progress_signal.emit("=" * 40)
        self.progress_signal.emit(f"🚀 Starting SimpCity Download for: {self.start_url}")

        self.should_dl_pixeldrain = self.parent_app.simpcity_dl_pixeldrain_cb.isChecked()
        self.should_dl_saint2 = self.parent_app.simpcity_dl_saint2_cb.isChecked()
        self.should_dl_mega = self.parent_app.simpcity_dl_mega_cb.isChecked()
        self.should_dl_images = self.parent_app.simpcity_dl_images_cb.isChecked()
        self.should_dl_bunkr = self.parent_app.simpcity_dl_bunkr_cb.isChecked()
        self.should_dl_gofile = self.parent_app.simpcity_dl_gofile_cb.isChecked()
        
        is_single_post_mode = self.post_id or '/post-' in self.start_url
        album_path = ""
        
        try:
            if is_single_post_mode:
                self.progress_signal.emit("   Mode: Single Post detected.")
                album_title, _, _ = fetch_single_simpcity_page(self.start_url, self._log_interceptor, cookies=self.cookies, post_id=self.post_id, check_pause_func=self._check_pause_cancel)
                album_path = os.path.join(self.output_dir, clean_folder_name(album_title or "simpcity_post"))
            else:
                self.progress_signal.emit("   Mode: Full Thread detected.")
                first_page_url = re.sub(r'(/page-\d+)|(/post-\d+)', '', self.start_url).split('#')[0].strip('/')
                album_title, _, _ = fetch_single_simpcity_page(first_page_url, self._log_interceptor, cookies=self.cookies, check_pause_func=self._check_pause_cancel)
                album_path = os.path.join(self.output_dir, clean_folder_name(album_title or "simpcity_album"))
                
            if self._check_pause_cancel():
                self.finished_signal.emit(0, 0, True, [])
                return
                
            os.makedirs(album_path, exist_ok=True)
            self.progress_signal.emit(f"   Saving all content to folder: '{os.path.basename(album_path)}'")
        except Exception as e:
            self.progress_signal.emit(f"❌ Could not process the initial page. Aborting. Error: {e}")
            self.finished_signal.emit(0, 0, self.is_cancelled, []); return
            
        num_service_threads = 4  
        service_executor = ThreadPoolExecutor(max_workers=num_service_threads, thread_name_prefix='SimpCityService')
        for _ in range(num_service_threads): 
            service_executor.submit(self._service_worker, album_path)
            
        num_image_threads = 15
        image_executor = ThreadPoolExecutor(max_workers=num_image_threads, thread_name_prefix='SimpCityImage')
        for _ in range(num_image_threads): 
            image_executor.submit(self._image_worker, album_path)

        try:
            if is_single_post_mode:
                _, jobs, _ = fetch_single_simpcity_page(self.start_url, self._log_interceptor, cookies=self.cookies, post_id=self.post_id, check_pause_func=self._check_pause_cancel)
                enriched_jobs = self._get_enriched_jobs(jobs)
                if enriched_jobs and not self.is_cancelled:
                    for job in enriched_jobs:
                        if job['type'] == 'image': 
                            if self.should_dl_images: self.image_queue.put(job)
                        else: self.service_queue.put(job)         
         
            else:
                base_url = re.sub(r'(/page-\d+)|(/post-\d+)', '', self.start_url).split('#')[0].strip('/')
                page_counter = 1; end_of_thread = False; MAX_RETRIES = 3
                while not end_of_thread:
                    if self._check_pause_cancel(): break
                    page_url = f"{base_url}/page-{page_counter}"; retries = 0; page_fetch_successful = False
                    while retries < MAX_RETRIES:
                        if self._check_pause_cancel(): end_of_thread = True; break
                        self.progress_signal.emit(f"\n--- Analyzing page {page_counter} (Attempt {retries + 1}/{MAX_RETRIES}) ---")
                        try:
                            page_title, jobs_on_page, final_url = fetch_single_simpcity_page(page_url, self._log_interceptor, cookies=self.cookies, check_pause_func=self._check_pause_cancel)
                            
                            if self.is_cancelled: end_of_thread = True; break
                            
                            if final_url != page_url:
                                self.progress_signal.emit(f"   -> Redirect detected from {page_url} to {final_url}")
                                try:
                                    req_page_match = re.search(r'/page-(\d+)', page_url)
                                    final_page_match = re.search(r'/page-(\d+)', final_url)

                                    if req_page_match:
                                        req_page_num = int(req_page_match.group(1))

                                        if final_page_match and int(final_page_match.group(1)) < req_page_num:
                                            self.progress_signal.emit(f"   -> Redirected to an earlier page ({final_page_match.group(0)}). Reached end of thread.")
                                            end_of_thread = True
                                        
                                        elif not final_page_match and req_page_num > 1:
                                            self.progress_signal.emit(f"   -> Redirected to base thread URL. Reached end of thread.")
                                            end_of_thread = True

                                except (ValueError, TypeError):
                                    pass
                            
                            if end_of_thread:
                                page_fetch_successful = True; break

                            if page_counter > 1 and not page_title:
                                self.progress_signal.emit(f"   -> Page {page_counter} is invalid or has no title. Reached end of thread.")
                                end_of_thread = True
                            elif not jobs_on_page: 
                                self.progress_signal.emit(f"   -> Page {page_counter} has no content. Reached end of thread.")
                                end_of_thread = True
                            else:
                                new_jobs = [job for job in jobs_on_page if job.get('url') not in self.processed_job_urls]
                                if not new_jobs and page_counter > 1: 
                                    self.progress_signal.emit(f"   -> Page {page_counter} contains no new content. Reached end of thread.")
                                    end_of_thread = True
                                else:
                                    enriched_jobs = self._get_enriched_jobs(new_jobs)
                                    if not enriched_jobs and not new_jobs:
                                        self.progress_signal.emit(f"   -> Page {page_counter} content was filtered out. Reached end of thread.")
                                        end_of_thread = True

                                    else:
                                        for job in enriched_jobs:
                                            self.processed_job_urls.add(job.get('url'))
                                            if job['type'] == 'image':
                                                if self.should_dl_images: self.image_queue.put(job)
                                            else: self.service_queue.put(job)

                            page_fetch_successful = True; break
                        except requests.exceptions.HTTPError as e:
                            if e.response.status_code in [403, 404]: 
                                self.progress_signal.emit(f"   -> Page {page_counter} returned {e.response.status_code}. Reached end of thread.")
                                end_of_thread = True; break
                            elif e.response.status_code == 429: 
                                self.progress_signal.emit(f"   -> Rate limited (429). Waiting...")
                                if self._smart_sleep(5 * (retries + 2)):
                                    end_of_thread = True
                                    break
                                retries += 1
                            else: 
                                self.progress_signal.emit(f"   -> HTTP Error {e.response.status_code} on page {page_counter}. Stopping crawl.")
                                end_of_thread = True; break
                        except Exception as e:
                            self.progress_signal.emit(f"   Stopping crawl due to error on page {page_counter}: {e}"); end_of_thread = True; break
                    if not page_fetch_successful and not end_of_thread: 
                        self.progress_signal.emit(f"   -> Failed to fetch page {page_counter} after {MAX_RETRIES} attempts. Stopping crawl.")
                        end_of_thread = True
                    if not end_of_thread: page_counter += 1
        except Exception as e:
            self.progress_signal.emit(f"❌ A critical error occurred during the main fetch phase: {e}")

        self.progress_signal.emit("\n--- All pages analyzed. Waiting for background downloads to complete... ---")
        
        for _ in range(num_image_threads): self.image_queue.put(None)
        for _ in range(num_service_threads): self.service_queue.put(None)
        
        image_executor.shutdown(wait=True)
        service_executor.shutdown(wait=True)
        
        self.finished_signal.emit(self.total_dl_count, self.total_skip_count, self.is_cancelled, [])