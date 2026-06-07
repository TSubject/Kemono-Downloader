import glob
import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from ...core.tag_query import (
    SOURCE_LABELS,
    build_query_from_text,
    build_site_query_tags,
    build_tag_batch_urls,
)


class TagBatchDownloadDialog(QDialog):
    """Tag-based batch downloader launcher for supported booru sources."""

    def __init__(self, main_app):
        super().__init__(main_app)
        self.main_app = main_app
        self.settings = main_app.settings
        self.source_checkboxes = {}

        self.setWindowTitle("Tag Batch Download")
        self.setMinimumWidth(760)
        self.resize(860, 660)

        self._build_ui()
        self._restore_values()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        main_layout.addWidget(self._create_source_group())
        main_layout.addWidget(self._create_tag_group())
        main_layout.addWidget(self._create_options_group())

        preview_group = QGroupBox("Generated URLs")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_output = QTextEdit()
        self.preview_output.setReadOnly(True)
        self.preview_output.setMinimumHeight(120)
        self.preview_output.setPlaceholderText("Click Preview to inspect the generated search URLs.")
        preview_layout.addWidget(self.preview_output)
        main_layout.addWidget(preview_group, 1)

        button_layout = QHBoxLayout()
        self.preview_button = QPushButton("Preview")
        self.start_button = QPushButton("Start Batch")
        self.close_button = QPushButton("Close")
        self.preview_button.clicked.connect(self._preview_urls)
        self.start_button.clicked.connect(self._start_batch)
        self.close_button.clicked.connect(self.reject)
        button_layout.addStretch(1)
        button_layout.addWidget(self.preview_button)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.close_button)
        main_layout.addLayout(button_layout)

    def _create_source_group(self):
        group = QGroupBox("Sources")
        layout = QHBoxLayout(group)

        for source in ("danbooru", "gelbooru", "rule34"):
            checkbox = QCheckBox(SOURCE_LABELS[source])
            checkbox.setChecked(True)
            self.source_checkboxes[source] = checkbox
            layout.addWidget(checkbox)

        rule34video_cb = QCheckBox(SOURCE_LABELS["rule34video"])
        rule34video_cb.setEnabled(False)
        rule34video_cb.setToolTip("Single video URLs are supported, but tag search batch is not available yet.")
        self.source_checkboxes["rule34video"] = rule34video_cb
        layout.addWidget(rule34video_cb)
        layout.addStretch(1)
        return group

    def _create_tag_group(self):
        group = QGroupBox("Tags")
        layout = QGridLayout(group)
        layout.setColumnStretch(1, 1)

        self.positive_input = QLineEdit()
        self.negative_input = QLineEdit()
        self.artist_input = QLineEdit()
        self.character_input = QLineEdit()
        self.general_input = QLineEdit()

        self.positive_input.setPlaceholderText("required tags, comma-separated")
        self.negative_input.setPlaceholderText("excluded tags, comma-separated")
        self.artist_input.setPlaceholderText("artist tags, comma-separated")
        self.character_input.setPlaceholderText("character tags, comma-separated")
        self.general_input.setPlaceholderText("general tags, comma-separated")

        rows = [
            ("Positive", self.positive_input),
            ("Negative", self.negative_input),
            ("Artist", self.artist_input),
            ("Character", self.character_input),
            ("General", self.general_input),
        ]
        for row, (label, widget) in enumerate(rows):
            layout.addWidget(QLabel(label), row, 0)
            layout.addWidget(widget, row, 1)

        return group

    def _create_options_group(self):
        group = QGroupBox("Options")
        layout = QGridLayout(group)
        layout.setColumnStretch(1, 1)

        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText("Download folder")
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._browse_output_dir)
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_dir_input, 1)
        output_layout.addWidget(self.browse_button)

        self.max_downloads_spin = QSpinBox()
        self.max_downloads_spin.setRange(0, 100000)
        self.max_downloads_spin.setSpecialValueText("Unlimited")
        self.max_downloads_spin.setToolTip("0 means no limit. Existing Booru/Rule34 downloaders read this setting.")

        self.download_images_cb = QCheckBox("Images")
        self.download_videos_cb = QCheckBox("Videos")
        self.download_images_cb.setChecked(True)
        self.download_videos_cb.setChecked(True)

        media_layout = QHBoxLayout()
        media_layout.addWidget(self.download_images_cb)
        media_layout.addWidget(self.download_videos_cb)
        media_layout.addStretch(1)

        self.source_subfolders_cb = QCheckBox("Create one subfolder per source")
        self.source_subfolders_cb.setChecked(True)

        layout.addWidget(QLabel("Output"), 0, 0)
        layout.addLayout(output_layout, 0, 1)
        layout.addWidget(QLabel("Max files"), 1, 0)
        layout.addWidget(self.max_downloads_spin, 1, 1)
        layout.addWidget(QLabel("Media"), 2, 0)
        layout.addLayout(media_layout, 2, 1)
        layout.addWidget(QLabel("Folders"), 3, 0)
        layout.addWidget(self.source_subfolders_cb, 3, 1)
        return group

    def _restore_values(self):
        selected_sources = str(
            self.settings.value("tag_batch_sources", "danbooru,gelbooru,rule34")
        ).split(",")
        for source, checkbox in self.source_checkboxes.items():
            if source != "rule34video":
                checkbox.setChecked(source in selected_sources)

        self.positive_input.setText(self.settings.value("tag_batch_positive", "", type=str))
        self.negative_input.setText(self.settings.value("tag_batch_negative", "", type=str))
        self.artist_input.setText(self.settings.value("tag_batch_artist", "", type=str))
        self.character_input.setText(self.settings.value("tag_batch_character", "", type=str))
        self.general_input.setText(self.settings.value("tag_batch_general", "", type=str))

        saved_output = self.settings.value("tag_batch_output_dir", "", type=str)
        current_output = ""
        if hasattr(self.main_app, "dir_input"):
            current_output = self.main_app.dir_input.text().strip()
        self.output_dir_input.setText(saved_output or current_output)

        self.max_downloads_spin.setValue(self._settings_int("tag_batch_max_downloads", self._settings_int("r34_max_downloads", 0)))
        self.download_images_cb.setChecked(self.settings.value("tag_batch_download_images", self.settings.value("r34_download_images", True), type=bool))
        self.download_videos_cb.setChecked(self.settings.value("tag_batch_download_videos", self.settings.value("r34_download_videos", True), type=bool))
        self.source_subfolders_cb.setChecked(self.settings.value("tag_batch_source_subfolders", True, type=bool))

    def _save_values(self):
        self.settings.setValue("tag_batch_sources", ",".join(self._selected_sources()))
        self.settings.setValue("tag_batch_positive", self.positive_input.text())
        self.settings.setValue("tag_batch_negative", self.negative_input.text())
        self.settings.setValue("tag_batch_artist", self.artist_input.text())
        self.settings.setValue("tag_batch_character", self.character_input.text())
        self.settings.setValue("tag_batch_general", self.general_input.text())
        self.settings.setValue("tag_batch_output_dir", self.output_dir_input.text().strip())
        self.settings.setValue("tag_batch_max_downloads", self.max_downloads_spin.value())
        self.settings.setValue("tag_batch_download_images", self.download_images_cb.isChecked())
        self.settings.setValue("tag_batch_download_videos", self.download_videos_cb.isChecked())
        self.settings.setValue("tag_batch_source_subfolders", self.source_subfolders_cb.isChecked())

    def _settings_int(self, key, default):
        try:
            return int(self.settings.value(key, default))
        except (TypeError, ValueError):
            return int(default)

    def _selected_sources(self):
        return [
            source
            for source, checkbox in self.source_checkboxes.items()
            if checkbox.isEnabled() and checkbox.isChecked()
        ]

    def _build_query(self):
        return build_query_from_text(
            self.positive_input.text(),
            self.negative_input.text(),
            self.artist_input.text(),
            self.character_input.text(),
            self.general_input.text(),
        )

    def _generated_urls(self):
        return build_tag_batch_urls(self._selected_sources(), self._build_query())

    def _preview_urls(self):
        urls = self._generated_urls()
        if not urls:
            self.preview_output.setPlainText("No URLs generated. Select at least one source and enter at least one tag.")
            return

        lines = []
        for source, url in urls:
            lines.append(f"{SOURCE_LABELS.get(source, source)}")
            lines.append(url)
            lines.append("")
        self.preview_output.setPlainText("\n".join(lines).strip())

    def _browse_output_dir(self):
        start_dir = self.output_dir_input.text().strip()
        if not start_dir and hasattr(self.main_app, "dir_input"):
            start_dir = self.main_app.dir_input.text().strip()
        selected = QFileDialog.getExistingDirectory(self, "Select Download Folder", start_dir or os.getcwd())
        if selected:
            self.output_dir_input.setText(selected)

    def _validate(self):
        if not self._selected_sources():
            QMessageBox.warning(self, "Missing Source", "Select at least one supported source.")
            return False

        if not build_site_query_tags(self._build_query()):
            QMessageBox.warning(self, "Missing Tags", "Enter at least one positive, artist, character, or general tag.")
            return False

        if not self.download_images_cb.isChecked() and not self.download_videos_cb.isChecked():
            QMessageBox.warning(self, "Missing Media Type", "Select Images, Videos, or both.")
            return False

        output_dir = self.output_dir_input.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "Missing Output", "Select a download folder.")
            return False

        if getattr(self.main_app, "is_running_job_queue", False) or self.main_app._is_download_active():
            QMessageBox.warning(self, "Busy", "A download or queue is already running.")
            return False

        if not os.path.isdir(output_dir):
            reply = QMessageBox.question(
                self,
                "Create Directory?",
                f"The directory '{output_dir}' does not exist.\nCreate it now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                return False
            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError as exc:
                QMessageBox.critical(self, "Directory Error", f"Could not create directory:\n{exc}")
                return False

        return True

    def _apply_download_settings(self):
        self.settings.setValue("r34_download_images", self.download_images_cb.isChecked())
        self.settings.setValue("r34_download_videos", self.download_videos_cb.isChecked())
        self.settings.setValue("r34_max_downloads", self.max_downloads_spin.value())
        self.settings.sync()

    def _target_output_dir(self, base_output_dir, source):
        if not self.source_subfolders_cb.isChecked():
            return base_output_dir
        return os.path.join(base_output_dir, SOURCE_LABELS.get(source, source))

    def _start_batch(self):
        if not self._validate():
            return

        urls = self._generated_urls()
        if not urls:
            QMessageBox.warning(self, "No URLs", "No supported URLs could be generated.")
            return

        self._save_values()
        self._apply_download_settings()
        self._preview_urls()

        if len(urls) == 1:
            self._start_single_download(urls[0])
        else:
            self._queue_multiple_downloads(urls)

    def _start_single_download(self, source_and_url):
        source, url = source_and_url
        output_dir = self._target_output_dir(self.output_dir_input.text().strip(), source)
        os.makedirs(output_dir, exist_ok=True)

        self.main_app.link_input.setText(url)
        self.main_app.dir_input.setText(output_dir)
        self._log(f"Tag batch starting {SOURCE_LABELS.get(source, source)}: {url}")

        if self.main_app.start_download():
            self.accept()

    def _queue_multiple_downloads(self, urls):
        existing_jobs = glob.glob(os.path.join(self.main_app.jobs_dir, "job_*.json"))
        if existing_jobs:
            reply = QMessageBox.question(
                self,
                "Pending Queue Jobs",
                "There are already pending queue jobs. Tag Batch will add its jobs and execute the whole queue.\nContinue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        base_output_dir = self.output_dir_input.text().strip()
        query_tags = build_site_query_tags(self._build_query())
        saved_count = 0

        for source, url in urls:
            output_dir = self._target_output_dir(base_output_dir, source)
            os.makedirs(output_dir, exist_ok=True)

            settings_dict = self.main_app._get_current_ui_settings_as_dict(
                api_url_override=url,
                output_dir_override=output_dir,
            )
            settings_dict["api_url"] = url
            settings_dict["output_dir"] = output_dir
            settings_dict["tag_batch_source"] = source
            settings_dict["tag_batch_tags"] = query_tags

            if self.main_app._save_single_job_file(settings_dict, name_hint=f"tag_batch_{source}"):
                saved_count += 1

        if not saved_count:
            QMessageBox.critical(self, "Queue Error", "Could not save any tag batch jobs.")
            return

        self._log(f"Tag batch queued {saved_count} source jobs.")
        self.main_app.execute_job_queue()
        self.accept()

    def _log(self, message):
        if hasattr(self.main_app, "log_signal"):
            self.main_app.log_signal.emit(message)
