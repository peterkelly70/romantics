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
import fnmatch

class FileCopyWindow(QtWidgets.QMainWindow):
    """Main window for the file copy application."""
    def __init__(self):
        super().__init__()
        
        # Initialize directories with defaults, fallback to current directory
        default_source = "/media/thoth/Jalpaite/ROMS/"
        default_dest = "/media/peter/"
        current_dir = os.getcwd()
        
        # Try default source, fallback to current directory
        self.source_directory = (
            default_source if os.path.exists(default_source) else current_dir
        )
        
        # Try default destination, fallback to current directory
        self.dest_directory = (
            default_dest if os.path.exists(default_dest) else current_dir
        )
        
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
        
        self._space_pressed = False  # Track space key state
        
    def setup_ui(self):
        """Set up the user interface."""
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QVBoxLayout(central_widget)
        
        # Lists layout - side by side
        lists_layout = QtWidgets.QHBoxLayout()
        
        # Source group
        source_group = QtWidgets.QGroupBox("Source")
        source_layout = QtWidgets.QVBoxLayout(source_group)
        
        # Source path
        source_path_layout = QtWidgets.QHBoxLayout()
        self.source_path = QtWidgets.QLineEdit()
        self.source_path.setReadOnly(True)
        source_path_layout.addWidget(self.source_path)
        
        source_browse = QtWidgets.QPushButton("Browse")
        source_browse.clicked.connect(lambda: self.browse_directory("source"))
        source_path_layout.addWidget(source_browse)
        source_layout.addLayout(source_path_layout)
        
        # Source list with select all and pattern toggles
        source_list_layout = QtWidgets.QVBoxLayout()
        source_toggle_layout = QtWidgets.QHBoxLayout()
        
        self.source_toggle = QtWidgets.QCheckBox("Select All")
        self.source_toggle.stateChanged.connect(self.toggle_source_selection)
        source_toggle_layout.addWidget(self.source_toggle)
        
        self.pattern_button = QtWidgets.QPushButton("Select by Pattern")
        self.pattern_button.clicked.connect(self.select_by_pattern)
        source_toggle_layout.addWidget(self.pattern_button)
        
        source_toggle_layout.addStretch()
        source_list_layout.addLayout(source_toggle_layout)
        
        self.source_list = QtWidgets.QListWidget()
        self.source_list.itemChanged.connect(self.on_source_item_changed)
        self.source_list.setSelectionMode(QtWidgets.QListWidget.SelectionMode.ExtendedSelection)
        self.source_list.installEventFilter(self)  # Install event filter for keyboard handling
        source_list_layout.addWidget(self.source_list)
        source_layout.addLayout(source_list_layout)
        
        # Extension filter
        filter_layout = QtWidgets.QHBoxLayout()
        filter_layout.addWidget(QtWidgets.QLabel("Filter:"))
        self.extension_combo = QtWidgets.QComboBox()
        self.extension_combo.addItems(self.extensions)
        self.extension_combo.currentTextChanged.connect(self.load_source_files)
        filter_layout.addWidget(self.extension_combo)
        filter_layout.addStretch()
        source_layout.addLayout(filter_layout)
        
        # Size indicator
        self.size_label = QtWidgets.QLabel("Selected: 0 B")
        source_layout.addWidget(self.size_label)
        
        source_group.setLayout(source_layout)
        lists_layout.addWidget(source_group)
        
        # Destination group
        dest_group = QtWidgets.QGroupBox("Destination")
        dest_layout = QtWidgets.QVBoxLayout(dest_group)
        
        dest_path_layout = QtWidgets.QHBoxLayout()
        self.dest_path = QtWidgets.QLineEdit()
        self.dest_path.setText(self.dest_directory)
        self.dest_path.textChanged.connect(self.dest_path_changed)
        dest_browse = QtWidgets.QPushButton("Browse")
        dest_browse.clicked.connect(lambda: self.browse_directory("dest"))
        dest_path_layout.addWidget(self.dest_path)
        dest_path_layout.addWidget(dest_browse)
        dest_layout.addLayout(dest_path_layout)
        
        # Destination list with select all toggle
        dest_list_layout = QtWidgets.QVBoxLayout()
        dest_toggle_layout = QtWidgets.QHBoxLayout()
        self.dest_toggle = QtWidgets.QCheckBox("Select All")
        dest_toggle_layout.addWidget(self.dest_toggle)
        dest_toggle_layout.addStretch()
        dest_list_layout.addLayout(dest_toggle_layout)
        
        self.dest_list = QtWidgets.QListWidget()
        self.dest_list.setSelectionMode(QtWidgets.QListWidget.SelectionMode.ExtendedSelection)
        dest_list_layout.addWidget(self.dest_list)
        dest_layout.addLayout(dest_list_layout)
        
        def toggle_dest_selection(state):
            for i in range(self.dest_list.count()):
                item = self.dest_list.item(i)
                item.setCheckState(
                    QtCore.Qt.CheckState.Checked if state 
                    else QtCore.Qt.CheckState.Unchecked
                )
            
        self.dest_toggle.stateChanged.connect(toggle_dest_selection)
        
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
        
        delete_button = QtWidgets.QPushButton("Delete Selected")
        delete_button.clicked.connect(self.delete_selected_files)
        action_layout.addWidget(delete_button)
        
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
        self.source_toggle.setChecked(False)  # Reset toggle state
        
        if not os.path.exists(self.source_directory):
            self.source_path.setText("")
            return
            
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
            
        self.update_size_indicator()

    def load_dest_files(self):
        """Load files from destination directory."""
        self.dest_list.clear()
        self.dest_toggle.setChecked(False)  # Reset toggle state
        
        if not os.path.exists(self.dest_directory):
            self.dest_path.setText("")
            return
            
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

    def get_selected_files(self, list_widget):
        """Get list of selected files from a list widget."""
        selected = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                file_path = item.data(QtCore.Qt.ItemDataRole.UserRole)
                selected.append(file_path)
        return selected

    def update_size_indicator(self):
        """Update the selected files size indicator."""
        selected_files = self.get_selected_files(self.source_list)
        total_size = sum(os.path.getsize(f) for f in selected_files)
        self.size_label.setText(f"Selected: {self.human_readable_size(total_size)}")

    def find_duplicates(self):
        """Find duplicate files based on content hash."""
        selected_files = self.get_selected_files(self.source_list)
        
        if not selected_files:
            QtWidgets.QMessageBox.warning(
                self, "Warning", 
                "Please select files to check for duplicates."
            )
            return
            
        # Initialize progress dialog
        progress = QtWidgets.QProgressDialog("Scanning files...", "Cancel", 0, len(selected_files), self)
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        
        # Scan for duplicates
        duplicates = {}
        current = 0
        
        for file_path in selected_files:
            if progress.wasCanceled():
                break
                
            try:
                file_hash = self.get_file_hash(file_path)
                if file_hash in duplicates:
                    duplicates[file_hash].append(file_path)
                else:
                    duplicates[file_hash] = [file_path]
                    
            except OSError as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error",
                    str(e)
                )
                
            current += 1
            progress.setValue(current)
            
        progress.close()
        
        # Filter out non-duplicates
        duplicates = {k: v for k, v in duplicates.items() if len(v) > 1}
        
        if duplicates:
            self.handle_duplicates(duplicates)
        else:
            QtWidgets.QMessageBox.information(
                self, "No Duplicates",
                "No duplicate files were found."
            )

    def get_file_hash(self, file_path):
        """Calculate MD5 hash of a file."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except OSError as e:
            raise OSError(f"Could not read {os.path.basename(file_path)}: {str(e)}")

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
        
        # Add tree widget for grouped display
        tree = QtWidgets.QTreeWidget()
        tree.setHeaderLabels(["File", "Size", "Modified", "Path", "Delete"])
        tree.setAlternatingRowColors(True)
        layout.addWidget(tree)
        
        # Populate tree with duplicate groups
        for hash_value, files in duplicates.items():
            # Sort files by modification time (newest first)
            files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
            
            # Create group item
            group = QtWidgets.QTreeWidgetItem(tree)
            group.setText(0, f"Duplicate Group ({len(files)} files)")
            group.setExpanded(True)
            
            # Add select all checkbox for group
            group_checkbox = QtWidgets.QCheckBox()
            tree.setItemWidget(group, 4, group_checkbox)
            
            # Add files to group
            group_items = []
            for i, file_path in enumerate(files):
                item = QtWidgets.QTreeWidgetItem(group)
                
                # Get file info
                stats = os.stat(file_path)
                size = self.human_readable_size(stats.st_size)
                mtime = datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                
                # Set item data
                item.setText(0, os.path.basename(file_path))
                item.setText(1, size)
                item.setText(2, mtime)
                item.setText(3, os.path.dirname(file_path))
                
                # Add checkbox (auto-select all except newest)
                checkbox = QtWidgets.QCheckBox()
                checkbox.setChecked(i > 0)  # Select all except the first (newest) file
                tree.setItemWidget(item, 4, checkbox)
                
                # Store full path
                item.setData(0, QtCore.Qt.ItemDataRole.UserRole, file_path)
                group_items.append((item, checkbox))
                
                # Set colors based on keep/delete status
                def update_colors(state):
                    if state:
                        # Red background with black text for files to delete
                        for col in range(4):
                            item.setBackground(col, QtGui.QColor(255, 200, 200))
                            item.setForeground(col, QtGui.QColor(0, 0, 0))
                    else:
                        # Green background with black text for files to keep
                        for col in range(4):
                            item.setBackground(col, QtGui.QColor(200, 255, 200))
                            item.setForeground(col, QtGui.QColor(0, 0, 0))
                            
                # Set initial colors
                update_colors(checkbox.isChecked())
                
                # Update colors when checkbox changes
                checkbox.stateChanged.connect(update_colors)
            
            # Connect group checkbox to control all items in group
            def update_group_items(state):
                for item, cb in group_items:
                    cb.setChecked(state)
            group_checkbox.stateChanged.connect(update_group_items)
        
        # Add select/deselect all button
        select_layout = QtWidgets.QHBoxLayout()
        select_all = QtWidgets.QPushButton("Select All")
        deselect_all = QtWidgets.QPushButton("Deselect All")
        invert_selection = QtWidgets.QPushButton("Invert Selection")
        
        def update_selection(checked):
            root = tree.invisibleRootItem()
            for i in range(root.childCount()):
                group = root.child(i)
                group_widget = tree.itemWidget(group, 4)
                if group_widget:
                    group_widget.setChecked(checked)
                for j in range(group.childCount()):
                    item = group.child(j)
                    widget = tree.itemWidget(item, 4)
                    if widget:
                        widget.setChecked(checked)
                        
        def invert_current_selection():
            root = tree.invisibleRootItem()
            for i in range(root.childCount()):
                group = root.child(i)
                for j in range(group.childCount()):
                    item = group.child(j)
                    widget = tree.itemWidget(item, 4)
                    if widget:
                        widget.setChecked(not widget.isChecked())
        
        select_all.clicked.connect(lambda: update_selection(True))
        deselect_all.clicked.connect(lambda: update_selection(False))
        invert_selection.clicked.connect(invert_current_selection)
        
        select_layout.addWidget(select_all)
        select_layout.addWidget(deselect_all)
        select_layout.addWidget(invert_selection)
        layout.addLayout(select_layout)
        
        # Add buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        delete_button = QtWidgets.QPushButton("Delete Selected")
        delete_button.clicked.connect(lambda: self.process_duplicates_tree(tree, "remove", dialog))
        button_layout.addWidget(delete_button)
        
        move_button = QtWidgets.QPushButton("Move Selected")
        move_button.clicked.connect(lambda: self.process_duplicates_tree(tree, "move", dialog))
        button_layout.addWidget(move_button)
        
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Show dialog
        dialog.resize(800, 600)
        dialog.exec()
        
    def process_duplicates_tree(self, tree, action, dialog):
        """Process selected duplicate files from tree widget."""
        selected_files = []
        root = tree.invisibleRootItem()
        
        # Collect selected files
        for i in range(root.childCount()):
            group = root.child(i)
            for j in range(group.childCount()):
                item = group.child(j)
                checkbox = tree.itemWidget(item, 4)
                if checkbox and checkbox.isChecked():
                    file_path = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                    selected_files.append(file_path)
                    
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

    class CopyWorker(QtCore.QThread):
        """Worker thread for copying files."""
        progress = QtCore.pyqtSignal(int)
        finished = QtCore.pyqtSignal()
        error = QtCore.pyqtSignal(str)
        
        def __init__(self, files, dest_dir):
            super().__init__()
            self.files = files
            self.dest_dir = dest_dir
            self.cancelled = False
            
        def run(self):
            """Copy files to destination directory."""
            try:
                total = len(self.files)
                for i, (src, _) in enumerate(self.files):
                    if self.cancelled:
                        break
                        
                    try:
                        dest = os.path.join(self.dest_dir, os.path.basename(src))
                        shutil.copy2(src, dest)
                        self.progress.emit(int((i + 1) * 100 / total))
                    except OSError as e:
                        self.error.emit(f"Error copying {os.path.basename(src)}: {str(e)}")
                        
            finally:
                self.finished.emit()
                
        def cancel(self):
            """Cancel the copy operation."""
            self.cancelled = True

    class CopyProgressDialog(QtWidgets.QDialog):
        """Dialog showing copy progress."""
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Copying Files")
            self.setModal(True)
            self.setup_ui()
            
        def setup_ui(self):
            """Set up the progress dialog UI."""
            layout = QtWidgets.QVBoxLayout(self)
            
            # Progress bar
            self.progress_bar = QtWidgets.QProgressBar()
            self.progress_bar.setRange(0, 100)
            layout.addWidget(self.progress_bar)
            
            # Cancel button
            button_layout = QtWidgets.QHBoxLayout()
            self.cancel_button = QtWidgets.QPushButton("Cancel")
            button_layout.addStretch()
            button_layout.addWidget(self.cancel_button)
            layout.addLayout(button_layout)
            
        def update_progress(self, value):
            """Update progress bar value."""
            self.progress_bar.setValue(value)

    def copy_selected_files(self):
        """Copy selected files to destination."""
        selected_files = self.get_selected_files(self.source_list)
        
        if not selected_files:
            QtWidgets.QMessageBox.warning(
                self, "Warning", 
                "Please select files to copy."
            )
            return
            
        if not self.dest_directory:
            QtWidgets.QMessageBox.warning(
                self, "Warning",
                "Please select a destination directory."
            )
            return
            
        # Prepare files list with sizes
        files_to_copy = []
        for file_path in selected_files:
            try:
                size = os.path.getsize(file_path)
                files_to_copy.append((file_path, size))
            except OSError as e:
                QtWidgets.QMessageBox.critical(
                    self, "Error",
                    f"Could not access {os.path.basename(file_path)}: {str(e)}"
                )
                return
                
        # Create and set up worker
        self.copy_worker = self.CopyWorker(files_to_copy, self.dest_directory)
        
        # Create and show progress dialog
        progress_dialog = self.CopyProgressDialog(self)
        
        # Connect signals
        self.copy_worker.progress.connect(progress_dialog.update_progress)
        self.copy_worker.finished.connect(progress_dialog.accept)
        self.copy_worker.error.connect(lambda msg: QtWidgets.QMessageBox.critical(self, "Error", msg))
        progress_dialog.cancel_button.clicked.connect(self.copy_worker.cancel)
        
        # Start copying in background
        self.copy_worker.start()
        
        # Show dialog and wait
        progress_dialog.exec()
        
        # Clean up
        if self.copy_worker:
            self.copy_worker.wait()  # Wait for thread to finish
            self.copy_worker.deleteLater()  # Clean up the worker
            self.copy_worker = None
            
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
        """Open directory browser dialog."""
        # Get current path from the appropriate text box
        current_path = self.source_path.text() if target == "source" else self.dest_path.text()
        
        # If path doesn't exist, start from parent directory that does exist
        while current_path and not os.path.exists(current_path):
            current_path = os.path.dirname(current_path)
            
        # If no valid path found, use current directory
        if not current_path:
            current_path = os.getcwd()
            
        dialog = QtWidgets.QFileDialog()
        dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
        dialog.setOption(QtWidgets.QFileDialog.Option.ShowDirsOnly, True)
        dialog.setDirectory(current_path)
        
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

    def show_clean_results(self, num_changes, errors):
        """Show results of cleaning operation."""
        if errors:
            msg = f"Cleaned {num_changes - len(errors)} files, {len(errors)} errors occurred."
        else:
            msg = f"Cleaned {num_changes} files."
        QtWidgets.QMessageBox.information(self, "Clean Names", msg)

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
        """Show dialog for renaming files."""
        # Get selected files
        selected_files = []
        for i in range(self.source_list.count()):
            item = self.source_list.item(i)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                file_path = item.data(QtCore.Qt.ItemDataRole.UserRole)
                selected_files.append(file_path)
                
        if not selected_files:
            QtWidgets.QMessageBox.warning(
                self, "No Files Selected",
                "Please select files to rename."
            )
            return
            
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Rename Files")
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Add description
        layout.addWidget(QtWidgets.QLabel("Search and Replace Pattern:"))
        
        # Add search pattern input
        search_layout = QtWidgets.QHBoxLayout()
        search_layout.addWidget(QtWidgets.QLabel("Search:"))
        search_pattern = QtWidgets.QLineEdit()
        search_layout.addWidget(search_pattern)
        layout.addLayout(search_layout)
        
        # Add replace pattern input
        replace_layout = QtWidgets.QHBoxLayout()
        replace_layout.addWidget(QtWidgets.QLabel("Replace:"))
        replace_pattern = QtWidgets.QLineEdit()
        replace_layout.addWidget(replace_pattern)
        layout.addLayout(replace_layout)
        
        # Add preview list
        preview_list = QtWidgets.QListWidget()
        layout.addWidget(QtWidgets.QLabel("Preview:"))
        layout.addWidget(preview_list)
        
        def update_preview():
            preview_list.clear()
            search_text = search_pattern.text()
            replace_text = replace_pattern.text()
            
            for file_path in selected_files:
                old_name = os.path.basename(file_path)
                new_name = old_name.replace(search_text, replace_text) if search_text else old_name
                item = QtWidgets.QListWidgetItem(f"{old_name} → {new_name}")
                preview_list.addItem(item)
                
        search_pattern.textChanged.connect(update_preview)
        replace_pattern.textChanged.connect(update_preview)
        update_preview()
        
        # Add buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | 
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        
        def do_rename():
            search_text = search_pattern.text()
            replace_text = replace_pattern.text()
            
            if not search_text:
                QtWidgets.QMessageBox.warning(
                    dialog, "Invalid Pattern",
                    "Please enter a search pattern."
                )
                return
                
            for file_path in selected_files:
                try:
                    directory = os.path.dirname(file_path)
                    old_name = os.path.basename(file_path)
                    new_name = old_name.replace(search_text, replace_text)
                    new_path = os.path.join(directory, new_name)
                    
                    if os.path.exists(new_path) and new_path != file_path:
                        QtWidgets.QMessageBox.warning(
                            dialog, "Error",
                            f"Cannot rename {old_name}: {new_name} already exists."
                        )
                        continue
                        
                    os.rename(file_path, new_path)
                except OSError as e:
                    QtWidgets.QMessageBox.warning(
                        dialog, "Error",
                        f"Could not rename {old_name}: {str(e)}"
                    )
                    
            self.load_source_files()
            dialog.accept()
            
        button_box.accepted.connect(do_rename)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.setMinimumWidth(500)
        dialog.exec()

    def select_by_pattern(self):
        """Select files matching a regex pattern."""
        pattern, ok = QtWidgets.QInputDialog.getText(
            self, "Select by Pattern",
            "Enter regex pattern (e.g. [0-9]+ for numbers):"
        )
        
        if ok and pattern:
            try:
                regex = re.compile(pattern)
                # Track if any items matched
                matched = False
                
                for i in range(self.source_list.count()):
                    item = self.source_list.item(i)
                    filename = os.path.basename(item.data(QtCore.Qt.ItemDataRole.UserRole))
                    if regex.search(filename):
                        item.setCheckState(QtCore.Qt.CheckState.Checked)
                        matched = True
                    else:
                        item.setCheckState(QtCore.Qt.CheckState.Unchecked)
                
                if not matched:
                    QtWidgets.QMessageBox.information(
                        self, "No Matches",
                        f"No files matched the pattern: {pattern}"
                    )
            except re.error as e:
                QtWidgets.QMessageBox.critical(
                    self, "Invalid Pattern",
                    f"Invalid regex pattern: {str(e)}"
                )

    def toggle_source_selection(self, state):
        """Toggle selection of all source files."""
        for i in range(self.source_list.count()):
            item = self.source_list.item(i)
            item.setCheckState(
                QtCore.Qt.CheckState.Checked if state 
                else QtCore.Qt.CheckState.Unchecked
            )
        self.update_size_indicator()

    def eventFilter(self, obj, event):
        """Handle keyboard events for quick selection."""
        if obj == self.source_list:
            if event.type() == QtCore.QEvent.Type.KeyPress:
                # Handle Delete key
                if event.key() == QtCore.Qt.Key.Key_Delete:
                    self.delete_selected_files()
                    return True
                
                # Track space key state
                if event.key() == QtCore.Qt.Key.Key_Space:
                    self._space_pressed = True
                
                # Handle arrow keys while space is held
                if self._space_pressed and event.key() in (QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Down):
                    current_item = self.source_list.currentItem()
                    if current_item:
                        # Toggle current item's check state
                        current_state = current_item.checkState()
                        new_state = QtCore.Qt.CheckState.Unchecked if current_state == QtCore.Qt.CheckState.Checked \
                            else QtCore.Qt.CheckState.Checked
                        current_item.setCheckState(new_state)
                        
                        # Move to next/previous item
                        current_row = self.source_list.row(current_item)
                        next_row = current_row + (1 if event.key() == QtCore.Qt.Key.Key_Down else -1)
                        if 0 <= next_row < self.source_list.count():
                            self.source_list.setCurrentRow(next_row)
                            # Ensure the item is visible
                            self.source_list.scrollToItem(self.source_list.item(next_row))
                        
                        return True  # Event handled
                        
            elif event.type() == QtCore.QEvent.Type.KeyRelease:
                # Reset space key state
                if event.key() == QtCore.Qt.Key.Key_Space:
                    self._space_pressed = False
                    
        return super().eventFilter(obj, event)

    def on_source_item_changed(self, item):
        """Handle source item checkbox changes."""
        self.update_size_indicator()
        # Update toggle state based on all items
        all_checked = all(
            self.source_list.item(i).checkState() == QtCore.Qt.CheckState.Checked
            for i in range(self.source_list.count())
        )
        self.source_toggle.setChecked(all_checked)

    def delete_selected_files(self):
        """Delete selected files from source directory."""
        selected_files = self.get_selected_files(self.source_list)
        
        if not selected_files:
            QtWidgets.QMessageBox.warning(
                self, "Warning", 
                "Please select files to delete."
            )
            return
            
        # Show custom confirmation dialog
        dialog = DeleteConfirmDialog(selected_files, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            errors = []
            for file_path in selected_files:
                try:
                    os.remove(file_path)
                except OSError as e:
                    errors.append(f"Could not delete {os.path.basename(file_path)}: {str(e)}")
            
            # Show any errors in a scrollable dialog
            if errors:
                error_dialog = QtWidgets.QDialog(self)
                error_dialog.setWindowTitle("Deletion Errors")
                error_dialog.setModal(True)
                error_dialog.resize(500, 300)
                
                layout = QtWidgets.QVBoxLayout(error_dialog)
                
                error_label = QtWidgets.QLabel("Errors occurred while deleting files:")
                layout.addWidget(error_label)
                
                error_text = QtWidgets.QTextEdit()
                error_text.setReadOnly(True)
                error_text.setText("\n".join(errors))
                layout.addWidget(error_text)
                
                button_box = QtWidgets.QDialogButtonBox(
                    QtWidgets.QDialogButtonBox.StandardButton.Ok
                )
                button_box.accepted.connect(error_dialog.accept)
                layout.addWidget(button_box)
                
                error_dialog.exec()
            
            # Refresh the source list
            self.load_source_files()

class DeleteConfirmDialog(QtWidgets.QDialog):
    """Custom dialog for confirming file deletion with scrollable area."""
    def __init__(self, files, parent=None):
        super().__init__(parent)
        self.files = files
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the confirmation dialog UI."""
        self.setWindowTitle("Confirm Delete")
        self.setModal(True)
        self.resize(500, 400)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Warning label
        warning = QtWidgets.QLabel("Are you sure you want to delete these files?")
        warning.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(warning)
        
        # Scrollable text area
        self.text_area = QtWidgets.QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setText("\n".join(os.path.basename(f) for f in self.files))
        layout.addWidget(self.text_area)
        
        # File count
        count_label = QtWidgets.QLabel(f"Total files: {len(self.files)}")
        layout.addWidget(count_label)
        
        # Buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Yes | 
            QtWidgets.QDialogButtonBox.StandardButton.No
        )
        
        button_box.button(QtWidgets.QDialogButtonBox.StandardButton.No).setDefault(True)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    
    # Set application icon
    icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QtGui.QIcon(icon_path))
    
    window = FileCopyWindow()
    window.show()
    sys.exit(app.exec())
