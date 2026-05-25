import os
import time
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt5.QtCore import QThread, pyqtSignal
from ...core.coomerfans_client import CoomerfansClient

MAX_WORKERS = 2  

class CoomerfansThread(QThread):
    progress_signal = pyqtSignal(str)
    file_progress_signal = pyqtSignal(str, object)
    overall_progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(int, int, bool, list)
    error_signal = pyqtSignal(str)

    def __init__(self, url, save_directory, main_app):
        super().__init__()
        self.url = url
        self.save_directory = save_directory
        self.main_app = main_app
        self.client = CoomerfansClient()
        self.is_running = True
        self.download_count = 0
        self.skip_count = 0
        self._count_lock = threading.Lock()  
        
        self.is_rate_limited = False
        self.rate_limit_lock = threading.Lock()

    def log(self, message):
        if self.main_app and hasattr(self.main_app, 'log_signal'):
            self.main_app.log_signal.emit(str(message))
        else:
            self.progress_signal.emit(str(message))

    def check_pause_and_cancel(self):
        if getattr(self.main_app, 'cancellation_event', None) and self.main_app.cancellation_event.is_set():
            self.is_running = False
            return False
        pause_evt = getattr(self.main_app, 'pause_event', None)
        if pause_evt:
            while pause_evt.is_set():
                if getattr(self.main_app, 'cancellation_event', None) and self.main_app.cancellation_event.is_set():
                    self.is_running = False
                    return False
                time.sleep(0.5)
        return True

    def _smart_sleep(self, seconds):
        """Sleeps in 0.5s intervals so the user can still cancel during a wait."""
        for _ in range(int(seconds * 2)):
            if not self.check_pause_and_cancel():
                return False
            time.sleep(0.5)
        return True

    def _handle_global_rate_limit(self, item_name):
        """Safely pauses all threads when the server issues a 429 or 403."""
        with self.rate_limit_lock:
            if not self.is_rate_limited:
                self.is_rate_limited = True
                self.log(f"   ⚠️ Rate limit hit on {item_name}. Pausing ALL threads for 15s to cool down...")
                self._smart_sleep(15)
                self.is_rate_limited = False
                
        while self.is_rate_limited and self.is_running:
            time.sleep(0.5)

    def run(self):
        try:
            parsed = urllib.parse.urlparse(self.url)
            paths = [p for p in parsed.path.split('/') if p]
            creator = paths[-1] if paths else "UnknownCreator"

            self.log(f"Starting Coomerfans scrape for: {creator}")
            creator_folder = os.path.join(self.save_directory, creator)
            os.makedirs(creator_folder, exist_ok=True)

            if "/p/" in self.url:
                self.log("Single post detected. Fetching media...")
                media_tasks = self._collect_post_tasks(self.url, creator_folder)
                self._run_parallel_downloads(media_tasks)
            else:
                self.log("Profile detected. Scraping all pages...")
                page = 1
                while self.is_running:
                    if not self.check_pause_and_cancel():
                        break

                    self.log(f"Scanning Page {page}...")
                    page_url = f"{self.url}?page={page}"
                    post_urls = self.client.get_posts_from_page(page_url)

                    if not post_urls:
                        self.log("No more posts found. Reached the end of the profile.")
                        break

                    self.log(f"Found {len(post_urls)} posts on page {page}. Queuing downloads...")

                    all_tasks = []
                    for post_url in post_urls:
                        if not self.check_pause_and_cancel():
                            break
                        all_tasks.extend(self._collect_post_tasks(post_url, creator_folder))

                    self._run_parallel_downloads(all_tasks)
                    page += 1

            if self.is_running:
                self.log("Complete! All Coomerfans media processed.")

            self.finished_signal.emit(self.download_count, self.skip_count, not self.is_running, [])

        except Exception as e:
            self.log(f"Coomerfans Engine Error: {str(e)}")


    def _collect_post_tasks(self, post_url, folder):
        media_urls = self.client.get_media_from_post(post_url)

        skip_images = hasattr(self.main_app, 'radio_videos') and self.main_app.radio_videos.isChecked()
        skip_videos = hasattr(self.main_app, 'radio_images') and self.main_app.radio_images.isChecked()

        tasks = []
        for media_url in media_urls:
            is_video = media_url.endswith('.mp4') or media_url.endswith('.webm')
            if is_video and skip_videos:
                continue
            if not is_video and skip_images:
                continue

            file_name = media_url.split('/')[-1].split('?')[0]
            save_path = os.path.join(folder, file_name)

            if os.path.exists(save_path):
                with self._count_lock:
                    self.skip_count += 1
                continue

            tasks.append((media_url, save_path))

        return tasks


    def _run_parallel_downloads(self, tasks):
        if not tasks:
            return

        self.log(f"Downloading {len(tasks)} file(s) with {MAX_WORKERS} parallel workers...")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(self.download_file, url, path): path
                       for url, path in tasks}

            for future in as_completed(futures):
                if not self.is_running:
                    for f in futures:
                        f.cancel()
                    break
                exc = future.exception()
                if exc:
                    self.log(f"Worker error: {exc}")


    def download_file(self, url, save_path):
        if not self.is_running:
            return
            
        while self.is_rate_limited and self.is_running: time.sleep(0.5)
            
        file_name = os.path.basename(save_path)
        
        response = None
        for attempt in range(4):
            try:
                res = self.client.session.get(url, headers=self.client.headers, stream=True, timeout=30)
                if res.status_code in [429, 403]:
                    self._handle_global_rate_limit(file_name)
                    continue
                res.raise_for_status()
                response = res
                break
            except Exception as e:
                if "429" in str(e) or "403" in str(e):
                    self._handle_global_rate_limit(file_name)
                    continue
                self.log(f"Failed to connect to {file_name}: {e}")
                return

        if not response or response.status_code != 200:
            return

        try:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            file_type = "Video:" if url.endswith('.mp4') or url.endswith('.webm') else "Image:"

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if not self.check_pause_and_cancel():
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            mb_dl = downloaded / (1024 * 1024)
                            mb_tot = total_size / (1024 * 1024)
                            self.file_progress_signal.emit(
                                file_type,
                                f"{file_name}: {percent}% ({mb_dl:.1f}MB / {mb_tot:.1f}MB)"
                            )
                            
            time.sleep(0.1)

            if self.is_running:
                self.overall_progress_signal.emit(1, 1)
                with self._count_lock:
                    self.download_count += 1
                self.log(f"✓ {file_name}")

        except Exception as e:
            self.log(f"Failed to download {url}: {e}")

    def stop(self):
        self.is_running = False