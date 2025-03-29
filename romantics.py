#!/usr/bin/env python3
import os
import sys
import re
import time
import hashlib
import shutil
from datetime import datetime
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import QThread, pyqtSignal, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
import mimetypes
from PIL import Image
import mutagen
import ffmpeg

class FileCopyWindow(QtWidgets.QMainWindow):
    """Main window for the file copy application."""
    def __init__(self):
        super().__init__()
        
        # Initialize directories
        self.source_directory = ""
        self.dest_directory = ""
        self.destination_free_space = 0
        self.extensions = ["All", ".mp3", ".flac", ".wav", ".m4a", ".ogg"]
        
        # Initialize UI
        self.setup_ui()
        
        # Set application icon
        icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))
        
        # Setup completion sound
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        sound_path = os.path.join(os.path.dirname(__file__), 'assets', 'jobsdone.mp3')
        if os.path.exists(sound_path):
            self.media_player.setSource(QUrl.fromLocalFile(sound_path))
        
        # Sound preference
        self.sound_enabled = True
        
        # Size tracking
        self.total_selected_size = 0
        
        # Common ROM filename patterns
        self.rom_patterns = [
            r'\([^)]*\)',           # Matches (USA), (Europe), etc.
            r'\[[^\]]*\]',          # Matches [!], [b], etc.
            r'\{[^}]*\}',           # Matches {M3}, {CV}, etc.
            r'[._-]v\d+(\.\d+)*',   # Matches version numbers
            r'(Rev|Version|v)\s*\d+',# Matches Rev1, Version 2, etc.
            r'\s*\([^\)]*\d{4}\)',  # Matches release years
            r'\s*-\s*\d{4}',        # Matches year after dash
            r'([\[\(].*?[\]\)])',   # Matches any bracketed content
            r'\s+(Disc|CD)\s*\d+',  # Matches disc/CD numbers
        ]
        self.rom_regex = re.compile('|'.join(self.rom_patterns), re.IGNORECASE)
        
    def setup_ui(self):
        """Set up the user interface."""
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QVBoxLayout(central_widget)
        
        # Lists layout - side by side
        lists_layout = QtWidgets.QHBoxLayout()
        
        # Source group
        source_group = QtWidgets.QGroupBox("Source")
        source_layout = QtWidgets.QVBoxLayout()
        
        source_path_layout = QtWidgets.QHBoxLayout()
        self.source_path = QtWidgets.QLineEdit()
        self.source_path.setText(self.source_directory)
        self.source_path.textChanged.connect(self.source_path_changed)
        source_browse = QtWidgets.QPushButton("Browse")
        source_browse.clicked.connect(lambda: self.browse_directory("source"))
        source_path_layout.addWidget(self.source_path)
        source_path_layout.addWidget(source_browse)
        source_layout.addLayout(source_path_layout)
        
        # Extension filter
        filter_layout = QtWidgets.QHBoxLayout()
        filter_layout.addWidget(QtWidgets.QLabel("Filter:"))
        self.extension_combo = QtWidgets.QComboBox()
        self.extension_combo.addItems(self.extensions)
        self.extension_combo.currentTextChanged.connect(self.load_source_files)
        filter_layout.addWidget(self.extension_combo)
        source_layout.addLayout(filter_layout)
        
        self.source_list = QtWidgets.QListWidget()
        self.source_list.setSelectionMode(QtWidgets.QListWidget.SelectionMode.ExtendedSelection)
        self.source_list.itemSelectionChanged.connect(self.update_size_indicator)
        source_layout.addWidget(self.source_list)
        
        # Source info layout
        source_info_layout = QtWidgets.QHBoxLayout()
        self.selected_size_label = QtWidgets.QLabel("Selected: 0 B")
        source_info_layout.addWidget(self.selected_size_label)
        source_layout.addLayout(source_info_layout)
        
        source_group.setLayout(source_layout)
        lists_layout.addWidget(source_group)
        
        # Destination group
        dest_group = QtWidgets.QGroupBox("Destination")
        dest_layout = QtWidgets.QVBoxLayout()
        
        dest_path_layout = QtWidgets.QHBoxLayout()
        self.dest_path = QtWidgets.QLineEdit()
        self.dest_path.setText(self.dest_directory)
        self.dest_path.textChanged.connect(self.dest_path_changed)
        dest_browse = QtWidgets.QPushButton("Browse")
        dest_browse.clicked.connect(lambda: self.browse_directory("dest"))
        dest_path_layout.addWidget(self.dest_path)
        dest_path_layout.addWidget(dest_browse)
        dest_layout.addLayout(dest_path_layout)
        
        self.dest_list = QtWidgets.QListWidget()
        self.dest_list.setSelectionMode(QtWidgets.QListWidget.SelectionMode.ExtendedSelection)
        dest_layout.addWidget(self.dest_list)
        
        # Destination info layout
        dest_info_layout = QtWidgets.QHBoxLayout()
        self.free_space_label = QtWidgets.QLabel("Free space: Calculating...")
        dest_info_layout.addWidget(self.free_space_label)
        dest_layout.addLayout(dest_info_layout)
        
        dest_group.setLayout(dest_layout)
        lists_layout.addWidget(dest_group)
        
        # Add lists layout to main layout
        layout.addLayout(lists_layout)
        
        # Action buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        # Target selection
        target_group = QtWidgets.QGroupBox("Apply to")
        target_layout = QtWidgets.QVBoxLayout()
        self.clean_source = QtWidgets.QCheckBox("Source")
        self.clean_dest = QtWidgets.QCheckBox("Destination")
        target_layout.addWidget(self.clean_source)
        target_layout.addWidget(self.clean_dest)
        target_group.setLayout(target_layout)
        button_layout.addWidget(target_group)
        
        # Action buttons
        action_group = QtWidgets.QGroupBox("Actions")
        action_layout = QtWidgets.QVBoxLayout()
        
        copy_button = QtWidgets.QPushButton("Copy Selected")
        copy_button.clicked.connect(self.copy_selected_files)
        action_layout.addWidget(copy_button)
        
        clean_button = QtWidgets.QPushButton("Clean Names")
        clean_button.clicked.connect(self.clean_selected_directory)
        action_layout.addWidget(clean_button)
        
        rename_button = QtWidgets.QPushButton("Rename")
        rename_button.clicked.connect(self.show_rename_dialog)
        action_layout.addWidget(rename_button)
        
        find_dupes_button = QtWidgets.QPushButton("Find Duplicates")
        find_dupes_button.clicked.connect(self.find_duplicates)
        action_layout.addWidget(find_dupes_button)
        
        action_group.setLayout(action_layout)
        button_layout.addWidget(action_group)
        
        layout.addLayout(button_layout)
        
        # Load initial files
        self.load_source_files()
        self.load_dest_files()
        self.update_free_space()

    def load_source_files(self):
        """Load files from source directory."""
        self.source_list.clear()
        
        try:
            extension = self.extension_combo.currentText()
            files = os.listdir(self.source_directory)
            
            for filename in sorted(files):
                if extension == "All" or filename.lower().endswith(extension.lower()):
                    file_path = os.path.join(self.source_directory, filename)
                    if os.path.isfile(file_path):
                        item = QtWidgets.QListWidgetItem(filename)
                        item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                        item.setCheckState(QtCore.Qt.CheckState.Unchecked)
                        item.setData(QtCore.Qt.ItemDataRole.UserRole, file_path)
                        self.source_list.addItem(item)
                        
        except OSError as e:
            QtWidgets.QMessageBox.warning(
                self, "Error",
                f"Could not load source directory: {str(e)}"
            )
            
        self.update_size_indicator()  # Update the UI

    def load_dest_files(self):
        """Load files from destination directory."""
        self.dest_list.clear()
        
        try:
            files = os.listdir(self.dest_directory)
            
            for filename in sorted(files):
                file_path = os.path.join(self.dest_directory, filename)
                if os.path.isfile(file_path):
                    item = QtWidgets.QListWidgetItem(filename)
                    item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(QtCore.Qt.CheckState.Unchecked)
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, file_path)
                    self.dest_list.addItem(item)
                    
        except OSError as e:
            QtWidgets.QMessageBox.warning(
                self, "Error",
                f"Could not load destination directory: {str(e)}"
            )

    def update_free_space(self):
        """Update free space indicator for destination directory."""
        try:
            if os.path.exists(self.dest_directory):
                _, _, free = shutil.disk_usage(self.dest_directory)
                self.destination_free_space = free
                free_text = self.human_readable_size(free)
                self.free_space_label.setText(f"Free space: {free_text}")
        except OSError:
            self.free_space_label.setText("Free space: Error")
            self.destination_free_space = 0

    def get_free_space(self, path):
        """Get free space in bytes for the given path."""
        try:
            return shutil.disk_usage(path).free
        except OSError:
            return 0

    def human_readable_size(self, size):
        """Convert size in bytes to human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def browse_directory(self, target):
        """Open a directory browser dialog."""
        dialog = QtWidgets.QFileDialog()
        dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
        dialog.setOption(QtWidgets.QFileDialog.Option.ShowDirsOnly, True)
        
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            selected_dir = dialog.selectedFiles()[0]
            if target == "source":
                self.source_directory = selected_dir
                self.source_path.setText(selected_dir)
                self.load_source_files()
            else:
                self.dest_directory = selected_dir
                self.dest_path.setText(selected_dir)
                self.load_dest_files()
                self.update_free_space()

    def clean_selected_directory(self):
        """Clean filenames in selected directories."""
        if not (self.clean_source.isChecked() or self.clean_dest.isChecked()):
            QtWidgets.QMessageBox.warning(self, "Warning", "Please select at least one directory to clean")
            return
            
        changes = []
        errors = []
        
        if self.clean_source.isChecked():
            changes.extend(self.get_files_to_clean(self.source_list, self.source_directory))
            
        if self.clean_dest.isChecked():
            changes.extend(self.get_files_to_clean(self.dest_list, self.dest_directory))
            
        if not changes:
            QtWidgets.QMessageBox.information(self, "Clean Names", "No files need cleaning.")
            return
            
        # Show confirmation dialog
        msg = self.build_clean_message(changes)
        if not self.confirm_clean(msg):
            return
            
        # Apply changes and refresh
        errors = self.apply_clean_changes(changes)
        
        # Refresh lists
        if self.clean_source.isChecked():
            self.load_source_files()
        if self.clean_dest.isChecked():
            self.load_dest_files()
            self.update_free_space()
            
        self.show_clean_results(len(changes), errors)
            
    def build_clean_message(self, changes):
        """Build message showing files to be renamed."""
        msg = "The following files will be renamed:\n\n"
        for _, _, old_name, new_name in changes[:10]:
            msg += f"{old_name} → {new_name}\n"
        if len(changes) > 10:
            msg += f"\n...and {len(changes) - 10} more files"
        return msg
        
    def confirm_clean(self, msg):
        """Show confirmation dialog and return user's choice."""
        response = QtWidgets.QMessageBox.question(
            self, "Confirm Rename",
            msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        return response == QtWidgets.QMessageBox.StandardButton.Yes
        
    def apply_clean_changes(self, changes):
        """Apply renaming changes and collect errors."""
        errors = []
        for old_path, new_path, old_name, _ in changes:
            try:
                os.rename(old_path, new_path)
            except OSError as e:
                errors.append(f"Error renaming {old_name}: {str(e)}")
        return errors
        
    def get_files_to_clean(self, list_widget, directory):
        """Get list of files that need cleaning."""
        changes = []
        for index in range(list_widget.count()):
            item = list_widget.item(index)
            old_path = item.data(QtCore.Qt.ItemDataRole.UserRole)
            old_name = os.path.basename(old_path)
            new_name = self.clean_filename(old_name)
            
            if new_name != old_name:
                new_path = os.path.join(directory, new_name)
                changes.append((old_path, new_path, old_name, new_name))
        return changes

    def find_duplicates(self):
        """Find duplicate files based on content hash."""
        # Initialize progress dialog
        progress = QtWidgets.QProgressDialog("Scanning files...", "Cancel", 0, 0, self)
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        
        # Get list of files to scan
        files_to_scan = []
        if self.clean_source.isChecked():
            for i in range(self.source_list.count()):
                item = self.source_list.item(i)
                files_to_scan.append(item.data(QtCore.Qt.ItemDataRole.UserRole))
                
        if self.clean_dest.isChecked():
            for i in range(self.dest_list.count()):
                item = self.dest_list.item(i)
                files_to_scan.append(item.data(QtCore.Qt.ItemDataRole.UserRole))
                
        if not files_to_scan:
            QtWidgets.QMessageBox.warning(
                self, "Warning",
                "No directories selected for duplicate scanning"
            )
            return
            
        # Set up progress dialog
        progress.setMaximum(len(files_to_scan))
        
        # Scan for duplicates
        duplicates = {}
        files_processed = 0
        
        for file_path in files_to_scan:
            if progress.wasCanceled():
                break
                
            progress.setValue(files_processed)
            progress.setLabelText(f"Scanning: {os.path.basename(file_path)}")
            
            try:
                file_hash = self.get_file_hash(file_path)
                if file_hash in duplicates:
                    duplicates[file_hash].append(file_path)
                else:
                    duplicates[file_hash] = [file_path]
                    
            except OSError as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error",
                    f"Could not scan {file_path}: {str(e)}"
                )
                
            files_processed += 1
            
        progress.close()
        
        # Filter out unique files
        duplicates = {k: v for k, v in duplicates.items() if len(v) > 1}
        
        # Show results dialog
        self.handle_duplicates(duplicates)

    def handle_duplicates(self, duplicates):
        """Show dialog to handle duplicate files."""
        if not duplicates:
            QtWidgets.QMessageBox.information(
                self, "No Duplicates",
                "No duplicate files were found."
            )
            return
            
        # Create dialog
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Duplicate Files Found")
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Add list widget
        list_widget = QtWidgets.QListWidget()
        for hash_value, files in duplicates.items():
            for file_path in files:
                item = QtWidgets.QListWidgetItem(file_path)
                item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.CheckState.Checked)
                list_widget.addItem(item)
        layout.addWidget(list_widget)
        
        # Add buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        remove_button = QtWidgets.QPushButton("Remove Selected")
        remove_button.clicked.connect(lambda: self.process_duplicates(list_widget, "remove", dialog))
        button_layout.addWidget(remove_button)
        
        move_button = QtWidgets.QPushButton("Move Selected")
        move_button.clicked.connect(lambda: self.process_duplicates(list_widget, "move", dialog))
        button_layout.addWidget(move_button)
        
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Show dialog
        dialog.resize(600, 400)
        dialog.exec()
        
    def process_duplicates(self, list_widget, action, dialog):
        """Process selected duplicate files."""
        selected_files = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                selected_files.append(item.text())
                
        if not selected_files:
            QtWidgets.QMessageBox.warning(
                self, "Warning",
                "No files selected"
            )
            return
            
        if action == "remove":
            msg = f"Are you sure you want to remove {len(selected_files)} file(s)?"
            if QtWidgets.QMessageBox.question(
                self, "Confirm Removal",
                msg,
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            ) == QtWidgets.QMessageBox.StandardButton.Yes:
                for file_path in selected_files:
                    try:
                        os.remove(file_path)
                    except OSError as e:
                        QtWidgets.QMessageBox.warning(
                            self, "Error",
                            f"Could not remove {file_path}: {str(e)}"
                        )
                dialog.accept()
                
        elif action == "move":
            dest_dir = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                "Select Destination Directory",
                "",
                QtWidgets.QFileDialog.Option.ShowDirsOnly
            )
            
            if dest_dir:
                for file_path in selected_files:
                    try:
                        shutil.move(file_path, os.path.join(dest_dir, os.path.basename(file_path)))
                    except OSError as e:
                        QtWidgets.QMessageBox.warning(
                            self, "Error",
                            f"Could not move {file_path}: {str(e)}"
                        )
                dialog.accept()
                
        # Refresh lists
        self.load_source_files()
        self.load_dest_files()

    def get_file_hash(self, filepath):
        """Calculate SHA256 hash of file contents."""
        import hashlib
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    class CopyProgressDialog(QtWidgets.QDialog):
        """Dialog showing copy progress."""
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Copying Files")
            self.setModal(True)
            layout = QtWidgets.QVBoxLayout(self)
            
            # Current file progress
            self.current_file_label = QtWidgets.QLabel("Preparing...")
            layout.addWidget(self.current_file_label)
            
            self.file_progress = QtWidgets.QProgressBar()
            layout.addWidget(self.file_progress)
            
            self.file_speed_label = QtWidgets.QLabel("Speed: 0 B/s")
            layout.addWidget(self.file_speed_label)
            
            # Overall progress
            self.total_progress = QtWidgets.QProgressBar()
            layout.addWidget(self.total_progress)
            
            self.total_files_label = QtWidgets.QLabel("Files: 0/0")
            layout.addWidget(self.total_files_label)
            
            # Cancel button
            self.cancel_button = QtWidgets.QPushButton("Cancel")
            layout.addWidget(self.cancel_button)
            
            self.resize(400, 200)
            
        def update_file_progress(self, current, total, speed):
            """Update current file progress."""
            self.file_progress.setMaximum(total)
            self.file_progress.setValue(current)
            self.file_speed_label.setText(f"Speed: {speed}/s")
            
        def update_total_progress(self, copied, total, current_file):
            """Update overall progress."""
            self.total_progress.setMaximum(total)
            self.total_progress.setValue(copied)
            self.current_file_label.setText(f"Copying: {current_file}")
            
        def update_file_count(self, copied, total):
            """Update file count."""
            self.total_files_label.setText(f"Files: {copied}/{total}")

    class CopyWorker(QtCore.QThread):
        """Worker thread for copying files."""
        file_progress = pyqtSignal(int, int, str)  # current bytes, total bytes, speed
        total_progress = pyqtSignal(int, int, str)  # copied bytes, total bytes, current file
        file_count = pyqtSignal(int, int)  # copied files, total files
        finished = pyqtSignal()
        error = pyqtSignal(str)
        
        def __init__(self, files, dest_dir):
            super().__init__()
            self.files = files  # List of (path, size) tuples
            self.dest_dir = dest_dir
            self.canceled = False
            self.total_size = sum(size for _, size in files)
            self.total_copied = 0
            self.files_copied = 0
            
        def get_unique_dest_path(self, src_path):
            """Get a unique destination path, appending numbers if needed."""
            filename = os.path.basename(src_path)
            dest_path = os.path.join(self.dest_dir, filename)
            
            if os.path.exists(dest_path):
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(dest_path):
                    new_name = f"{base}_{counter}{ext}"
                    dest_path = os.path.join(self.dest_dir, new_name)
                    counter += 1
            
            return dest_path
            
        def copy_file_with_progress(self, src_path, dest_path, file_size):
            """Copy a single file with progress updates."""
            file_copied = 0
            last_update = time.time()
            last_bytes = 0
            
            try:
                with open(src_path, 'rb') as src, open(dest_path, 'wb') as dst:
                    while chunk := src.read(65536):  # 64KB chunks
                        if self.canceled:
                            dst.close()
                            os.remove(dest_path)
                            return False
                            
                        dst.write(chunk)
                        chunk_size = len(chunk)
                        file_copied += chunk_size
                        self.total_copied += chunk_size
                        
                        # Update progress every 100ms
                        now = time.time()
                        if now - last_update >= 0.1:
                            speed = (file_copied - last_bytes) / (now - last_update)
                            speed_str = self.format_speed(speed)
                            filename = os.path.basename(src_path)
                            
                            self.file_progress.emit(file_copied, file_size, speed_str)
                            self.total_progress.emit(self.total_copied, self.total_size, filename)
                            
                            last_update = now
                            last_bytes = file_copied
                
                return True
                
            except OSError as e:
                self.error.emit(f"Error copying {os.path.basename(src_path)}: {str(e)}")
                if os.path.exists(dest_path):
                    try:
                        os.remove(dest_path)
                    except OSError:
                        pass
                return False
                
        def format_speed(self, bytes_per_sec):
            """Format transfer speed in human readable format."""
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_per_sec < 1024:
                    return f"{bytes_per_sec:.1f} {unit}"
                bytes_per_sec /= 1024
            return f"{bytes_per_sec:.1f} TB"
            
        def run(self):
            """Copy files in a separate thread."""
            for src_path, file_size in self.files:
                if self.canceled:
                    break
                    
                dest_path = self.get_unique_dest_path(src_path)
                
                if self.copy_file_with_progress(src_path, dest_path, file_size):
                    self.files_copied += 1
                    self.file_count.emit(self.files_copied, len(self.files))
                else:
                    return
            
            if not self.canceled:
                self.finished.emit()
        
        def cancel(self):
            """Cancel the copy operation."""
            self.canceled = True

    def copy_selected_files(self):
        """Copy selected files to destination."""
        selected_items = self.source_list.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.warning(self, "Warning", "No files selected")
            return
            
        # Calculate total size
        files_to_copy = []
        total_size = 0
        for item in selected_items:
            file_path = item.data(QtCore.Qt.ItemDataRole.UserRole)
            try:
                size = os.path.getsize(file_path)
                total_size += size
                files_to_copy.append((file_path, size))
            except OSError as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error",
                    f"Could not access file {os.path.basename(file_path)}: {str(e)}"
                )
                return
                
        # Check destination space
        if total_size > self.destination_free_space:
            QtWidgets.QMessageBox.critical(
                self, "Error",
                "Not enough space in destination directory"
            )
            return
            
        # Create and start copy worker
        self.copy_worker = CopyWorker(files_to_copy, self.dest_directory)
        self.copy_progress = CopyProgressDialog(self)
        
        # Connect signals
        self.copy_worker.file_progress.connect(self.copy_progress.update_file_progress)
        self.copy_worker.total_progress.connect(self.copy_progress.update_total_progress)
        self.copy_worker.file_count.connect(self.copy_progress.update_file_count)
        self.copy_worker.finished.connect(self.copy_progress.accept)
        self.copy_worker.error.connect(lambda msg: QtWidgets.QMessageBox.critical(self, "Error", msg))
        self.copy_progress.cancel_button.clicked.connect(self.copy_worker.cancel)
        
        # Start copying
        self.copy_worker.start()
        self.copy_progress.exec()
        
        # Refresh lists after copy
        self.load_source_files()
        self.load_dest_files()
        self.update_free_space()

    def scrape_metadata(self, file_path):
        """Extract metadata from a file."""
        metadata = {}
        try:
            # Get basic metadata first
            stat = os.stat(file_path)
            metadata.update({
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "type": mimetypes.guess_type(file_path)[0] or "unknown"
            })
            
            # Get extension-specific metadata
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.gif']:
                self._add_image_metadata(file_path, metadata)
            elif ext in ['.mp3', '.wav', '.flac']:
                self._add_audio_metadata(file_path, metadata)
            elif ext in ['.mp4', '.avi', '.mkv']:
                self._add_video_metadata(file_path, metadata)
                
            return metadata
            
        except Exception as e:
            return {"error": str(e)}
            
    def _add_image_metadata(self, file_path, metadata):
        """Add image-specific metadata."""
        with Image.open(file_path) as img:
            metadata.update({
                "dimensions": f"{img.width}x{img.height}",
                "format": img.format,
                "mode": img.mode
            })
            
            if hasattr(img, '_getexif') and img._getexif():
                exif = img._getexif()
                if exif:
                    metadata.update(self._parse_exif(exif))
                    
    def _add_audio_metadata(self, file_path, metadata):
        """Add audio-specific metadata."""
        audio = mutagen.File(file_path)
        if audio:
            metadata.update({
                "duration": str(datetime.timedelta(seconds=int(audio.info.length))),
                "bitrate": f"{int(audio.info.bitrate / 1000)}kbps"
            })
            
            if hasattr(audio, 'tags'):
                metadata.update(self._parse_audio_tags(audio.tags))
                
    def _add_video_metadata(self, file_path, metadata):
        """Add video-specific metadata."""
        probe = ffmpeg.probe(file_path)
        if probe:
            video_stream = next(
                (stream for stream in probe['streams'] if stream['codec_type'] == 'video'),
                None
            )
            
            if video_stream:
                metadata.update({
                    "dimensions": f"{video_stream.get('width', 'unknown')}x{video_stream.get('height', 'unknown')}",
                    "duration": str(datetime.timedelta(seconds=int(float(probe['format'].get('duration', 0))))),
                    "codec": video_stream.get('codec_name', 'unknown'),
                    "fps": eval(video_stream.get('r_frame_rate', '0/1'))
                })
    
    def clean_filename(self, filename):
        """Clean a filename by making it lowercase, replacing spaces with dots, and removing special chars."""
        base, ext = os.path.splitext(filename)
        
        base = base.lower()
        ext = ext.lower()
        
        base = base.replace(' ', '.')
        
        base = re.sub(r'[^a-z0-9.-]', '', base)
        
        base = re.sub(r'\.+', '.', base)
        
        base = base.strip('.')
        
        return f"{base}{ext}"

    def update_size_indicator(self):
        """Update the selected size indicator."""
        total_size = 0
        for item in self.source_list.selectedItems():
            try:
                file_path = item.data(QtCore.Qt.ItemDataRole.UserRole)
                total_size += os.path.getsize(file_path)
            except OSError:
                continue
                
        size_text = self.human_readable_size(total_size)
        self.selected_size_label.setText(f"Selected: {size_text}")

    def source_path_changed(self, path):
        """Handle source path text changes."""
        self.source_directory = path
        self.load_source_files()
        
    def dest_path_changed(self, path):
        """Handle destination path text changes."""
        self.dest_directory = path
        self.load_dest_files()
        self.update_free_space()

    def show_rename_dialog(self):
        """Show dialog for renaming files with regex pattern."""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Rename Files")
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Rename type selection
        type_group = QtWidgets.QButtonGroup(dialog)
        single_radio = QtWidgets.QRadioButton("Rename Single File")
        pattern_radio = QtWidgets.QRadioButton("Rename Using Pattern")
        single_radio.setChecked(True)
        type_group.addButton(single_radio)
        type_group.addButton(pattern_radio)
        
        layout.addWidget(single_radio)
        layout.addWidget(pattern_radio)
        
        # Pattern inputs
        pattern_widget = QtWidgets.QWidget()
        pattern_layout = QtWidgets.QFormLayout(pattern_widget)
        
        search_pattern = QtWidgets.QLineEdit()
        replace_pattern = QtWidgets.QLineEdit()
        
        pattern_layout.addRow("Search Pattern:", search_pattern)
        pattern_layout.addRow("Replace Pattern:", replace_pattern)
        
        # Single file input
        single_widget = QtWidgets.QWidget()
        single_layout = QtWidgets.QFormLayout(single_widget)
        new_name = QtWidgets.QLineEdit()
        single_layout.addRow("New Name:", new_name)
        
        layout.addWidget(single_widget)
        layout.addWidget(pattern_widget)
        pattern_widget.hide()
        
        # Connect radio buttons
        single_radio.toggled.connect(lambda checked: (
            single_widget.setVisible(checked),
            pattern_widget.setVisible(not checked)
        ))
        
        # Buttons
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            if single_radio.isChecked():
                if new_name.text():
                    self.rename_selected_file(new_name.text())
            else:
                if search_pattern.text():
                    self.rename_files_pattern(search_pattern.text(), replace_pattern.text())

    def rename_files_pattern(self, search_pattern, replace_pattern):
        """Rename multiple files using regex pattern."""
        def rename_in_list(list_widget, directory):
            """Rename files in the specified list."""
            selected_items = list_widget.selectedItems()
            if not selected_items:
                return
                
            for item in selected_items:
                old_path = item.data(QtCore.Qt.ItemDataRole.UserRole)
                old_name = os.path.basename(old_path)
                try:
                    new_name = re.sub(search_pattern, replace_pattern, old_name)
                    if new_name != old_name:
                        new_path = os.path.join(directory, new_name)
                        if not os.path.exists(new_path):
                            os.rename(old_path, new_path)
                except (OSError, re.error) as e:
                    QtWidgets.QMessageBox.critical(
                        self, "Error",
                        f"Error renaming {old_name}: {str(e)}"
                    )
        
        if self.clean_source.isChecked():
            rename_in_list(self.source_list, self.source_directory)
            self.load_source_files()
            
        if self.clean_dest.isChecked():
            rename_in_list(self.dest_list, self.dest_directory)
            self.load_dest_files()

    def rename_selected_file(self, new_name=None):
        """Rename a selected file in either source or destination."""
        if self.clean_source.isChecked():
            list_widget = self.source_list
            directory = self.source_directory
        elif self.clean_dest.isChecked():
            list_widget = self.dest_list
            directory = self.dest_directory
        else:
            QtWidgets.QMessageBox.warning(self, "Warning", "Please select a directory to rename")
            return
            
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.warning(self, "Warning", "Please select a file to rename")
            return
            
        if len(selected_items) > 1:
            QtWidgets.QMessageBox.warning(self, "Warning", "Please select only one file to rename")
            return
            
        item = selected_items[0]
        old_path = item.data(QtCore.Qt.ItemDataRole.UserRole)
        old_name = os.path.basename(old_path)
        
        if new_name is None:
            new_name, ok = QtWidgets.QInputDialog.getText(
                self, "Rename File", "New name:", 
                QtWidgets.QLineEdit.EchoMode.Normal, old_name
            )
            
            if not ok or not new_name:
                return
            
        try:
            new_path = os.path.join(directory, new_name)
            if os.path.exists(new_path):
                QtWidgets.QMessageBox.warning(self, "Error", "A file with that name already exists")
                return
                
            os.rename(old_path, new_path)
            if self.clean_source.isChecked():
                self.load_source_files()
            else:
                self.load_dest_files()
                self.update_free_space()
                
        except OSError as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Could not rename file: {str(e)}")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    
    # Set application icon
    icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QtGui.QIcon(icon_path))
    
    window = FileCopyWindow()
    window.show()
    sys.exit(app.exec())
