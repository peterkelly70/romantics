#!/usr/bin/env python3
import sys, os, shutil
from PyQt6 import QtWidgets, QtCore

class FileCopyWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ROM File Manager")
        self.resize(800, 600)
        self.source_directory = os.getcwd()  # Change if you wish to use a different source directory
        self.extensions = ["All", ".chd", ".iso", ".bin", ".n64", ".rom"]
        self.init_ui()
    
    def init_ui(self):
        # Use a QSplitter to create two resizable panels: source (left) and destination (right)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)
        
        # =============================
        # Left Panel: Source Files
        # =============================
        self.source_panel = QtWidgets.QWidget()
        source_layout = QtWidgets.QVBoxLayout(self.source_panel)
        
        # Extension filter drop-down
        filter_layout = QtWidgets.QHBoxLayout()
        filter_label = QtWidgets.QLabel("Filter by extension:")
        self.extension_combo = QtWidgets.QComboBox()
        self.extension_combo.addItems(self.extensions)
        self.extension_combo.currentIndexChanged.connect(self.load_source_files)
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.extension_combo)
        source_layout.addLayout(filter_layout)
        
        # File list (checkable items for selection; arrow keys and space bar will work automatically)
        self.source_list = QtWidgets.QListWidget()
        self.source_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        source_layout.addWidget(self.source_list)
        splitter.addWidget(self.source_panel)
        
        # =============================
        # Right Panel: Destination Info
        # =============================
        self.dest_panel = QtWidgets.QWidget()
        dest_layout = QtWidgets.QVBoxLayout(self.dest_panel)
        
        # Destination directory selection
        dest_dir_layout = QtWidgets.QHBoxLayout()
        dest_label = QtWidgets.QLabel("Destination Directory:")
        self.dest_edit = QtWidgets.QLineEdit()
        self.dest_browse = QtWidgets.QPushButton("Browse")
        self.dest_browse.clicked.connect(self.select_destination)
        dest_dir_layout.addWidget(dest_label)
        dest_dir_layout.addWidget(self.dest_edit)
        dest_dir_layout.addWidget(self.dest_browse)
        dest_layout.addLayout(dest_dir_layout)
        
        # Free space display
        self.free_space_label = QtWidgets.QLabel("Free space: N/A")
        dest_layout.addWidget(self.free_space_label)
        
        # Log of copied/skipped files
        self.dest_list = QtWidgets.QListWidget()
        self.dest_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        dest_layout.addWidget(self.dest_list)
        
        # Copy button
        self.copy_button = QtWidgets.QPushButton("Copy Selected Files")
        self.copy_button.clicked.connect(self.copy_files)
        dest_layout.addWidget(self.copy_button)
        
        splitter.addWidget(self.dest_panel)
        splitter.setSizes([400, 400])
        
        # Initially load the source files list
        self.load_source_files()
    
    def load_source_files(self):
        """Load files from the source directory filtered by extension."""
        self.source_list.clear()
        selected_ext = self.extension_combo.currentText()
        for filename in os.listdir(self.source_directory):
            if selected_ext != "All" and not filename.lower().endswith(selected_ext.lower()):
                continue
            full_path = os.path.join(self.source_directory, filename)
            if os.path.isfile(full_path):
                size = os.path.getsize(full_path)
                size_str = self.human_readable_size(size)
                item = QtWidgets.QListWidgetItem(f"{filename} ({size_str})")
                item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.CheckState.Unchecked)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, full_path)
                self.source_list.addItem(item)
    
    def human_readable_size(self, size, decimal_places=2):
        """Convert bytes into a human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.{decimal_places}f} {unit}"
            size /= 1024.0
        return f"{size:.{decimal_places}f} PB"
    
    def select_destination(self):
        """Open a dialog to choose the destination directory."""
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Destination Directory")
        if directory:
            self.dest_edit.setText(directory)
            self.update_free_space()
    
    def update_free_space(self):
        """Update the free space label based on the selected destination."""
        dest_dir = self.dest_edit.text().strip()
        if dest_dir and os.path.isdir(dest_dir):
            usage = shutil.disk_usage(dest_dir)
            free = self.human_readable_size(usage.free)
            self.free_space_label.setText(f"Free space: {free}")
        else:
            self.free_space_label.setText("Free space: N/A")
    
    def is_duplicate(self, source_path, dest_dir):
        """
        Deduplication check: returns True if a file with the same name and size exists
        in the destination. This function can be enhanced (e.g., using hash comparisons).
        """
        dest_file = os.path.join(dest_dir, os.path.basename(source_path))
        if os.path.exists(dest_file) and os.path.getsize(dest_file) == os.path.getsize(source_path):
            return True
        return False
    
    def copy_files(self):
        """Copy all checked files to the destination after deduplication and free space checks."""
        dest_dir = self.dest_edit.text().strip()
        if not dest_dir or not os.path.isdir(dest_dir):
            QtWidgets.QMessageBox.warning(self, "Error", "Please select a valid destination directory.")
            return
        for index in range(self.source_list.count()):
            item = self.source_list.item(index)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                source_path = item.data(QtCore.Qt.ItemDataRole.UserRole)
                file_size = os.path.getsize(source_path)
                
                # Check deduplication
                if self.is_duplicate(source_path, dest_dir):
                    self.dest_list.addItem(f"Skipped duplicate: {os.path.basename(source_path)}")
                    continue
                
                # Check available free space
                usage = shutil.disk_usage(dest_dir)
                if usage.free < file_size:
                    QtWidgets.QMessageBox.warning(self, "Error",
                        f"Not enough free space to copy {os.path.basename(source_path)}.")
                    continue
                
                dest_path = os.path.join(dest_dir, os.path.basename(source_path))
                try:
                    # --- Hook for metadata scraping (placeholder) ---
                    metadata = self.scrape_metadata(source_path)
                    # For later: use metadata to integrate with systems like Batocera, EmulationStation, Garlic OS, etc.
                    
                    # Proceed with file copy
                    shutil.copy2(source_path, dest_path)
                    self.dest_list.addItem(f"Copied: {os.path.basename(source_path)}")
                    
                    # Optionally disable the source item after a successful copy
                    item.setCheckState(QtCore.Qt.CheckState.Unchecked)
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
                    self.update_free_space()
                except Exception as e:
                    QtWidgets.QMessageBox.warning(self, "Error",
                        f"Failed to copy {os.path.basename(source_path)}: {e}")
    
    def scrape_metadata(self, file_path):
        """
        Placeholder for metadata scraping functionality.
        Later expansion could integrate with various ROM metadata providers
        for systems like Batocera, EmulationStation, Garlic OS, etc.
        """
        print(f"Scraping metadata for {file_path}...")  # Debug output
        return {}  # Currently returns an empty dict

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = FileCopyWindow()
    window.show()
    sys.exit(app.exec())
