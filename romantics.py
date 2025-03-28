#!/usr/bin/env python3
import sys, os, shutil
from PyQt6 import QtWidgets, QtCore

class FileCopyWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ROM File Manager")
        self.resize(800, 600)
        self.source_directory = "/media/thoth/Jalpaite/ROMS/"  # Set default source directory
        self.dest_directory = "/media/thoth/Jalpaite/ROMS/"    # Set default destination directory
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
        
        # Source directory selection
        source_dir_layout = QtWidgets.QHBoxLayout()
        source_label = QtWidgets.QLabel("Source Directory:")
        self.source_edit = QtWidgets.QLineEdit(self.source_directory)
        self.source_browse = QtWidgets.QPushButton("Browse")
        self.source_browse.clicked.connect(self.select_source)
        source_dir_layout.addWidget(source_label)
        source_dir_layout.addWidget(self.source_edit)
        source_dir_layout.addWidget(self.source_browse)
        source_layout.addLayout(source_dir_layout)
        
        # Sort options
        sort_layout = QtWidgets.QHBoxLayout()
        sort_label = QtWidgets.QLabel("Sort by:")
        self.sort_combo = QtWidgets.QComboBox()
        self.sort_combo.addItems(["Name", "Size"])
        self.sort_combo.currentIndexChanged.connect(self.load_source_files)
        sort_layout.addWidget(sort_label)
        sort_layout.addWidget(self.sort_combo)
        source_layout.addLayout(sort_layout)
        
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
        self.dest_edit = QtWidgets.QLineEdit(self.dest_directory)  # Set default path
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
        
        # Update source directory from the line edit
        self.source_directory = self.source_edit.text()
        
        try:
            # Collect files and their info
            files_info = []
            for filename in os.listdir(self.source_directory):
                if selected_ext != "All" and not filename.lower().endswith(selected_ext.lower()):
                    continue
                full_path = os.path.join(self.source_directory, filename)
                if os.path.isfile(full_path):
                    size = os.path.getsize(full_path)
                    files_info.append({
                        'name': filename,
                        'size': size,
                        'size_str': self.human_readable_size(size),
                        'path': full_path
                    })
            
            # Sort files based on selected criteria
            sort_by = self.sort_combo.currentText()
            if sort_by == "Name":
                files_info.sort(key=lambda x: x['name'].lower())
            else:  # Sort by size
                files_info.sort(key=lambda x: x['size'], reverse=True)
            
            # Add sorted files to the list
            for file_info in files_info:
                item = QtWidgets.QListWidgetItem(f"{file_info['name']} ({file_info['size_str']})")
                item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.CheckState.Unchecked)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, file_info['path'])
                self.source_list.addItem(item)
                
        except (FileNotFoundError, PermissionError) as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Cannot access directory: {str(e)}")
    
    def human_readable_size(self, size, decimal_places=2):
        """Convert bytes into a human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.{decimal_places}f} {unit}"
            size /= 1024.0
        return f"{size:.{decimal_places}f} PB"
    
    def select_destination(self):
        """Open directory selection dialog for destination."""
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Destination Directory")
        if directory:
            self.dest_edit.setText(directory)
            self.update_free_space()
            
    def select_source(self):
        """Open directory selection dialog for source."""
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Source Directory", self.source_directory)
        if directory:
            self.source_edit.setText(directory)
            self.source_directory = directory
            self.load_source_files()
    
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
        """Copy selected files to the destination directory."""
        # Update destination directory from the line edit
        self.dest_directory = self.dest_edit.text()
        
        # Create destination directory if it doesn't exist
        try:
            os.makedirs(self.dest_directory, exist_ok=True)
        except PermissionError:
            QtWidgets.QMessageBox.critical(self, "Error", "Permission denied: Cannot create destination directory")
            return
            
        selected_items = []
        for i in range(self.source_list.count()):
            item = self.source_list.item(i)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                selected_items.append(item)
        
        if not selected_items:
            QtWidgets.QMessageBox.warning(self, "Warning", "No files selected")
            return
            
        # Calculate total size and check available space
        total_size = sum(os.path.getsize(item.data(QtCore.Qt.ItemDataRole.UserRole)) for item in selected_items)
        free_space = shutil.disk_usage(self.dest_directory).free
        
        if total_size > free_space:
            QtWidgets.QMessageBox.critical(self, "Error", "Not enough free space in destination directory")
            return
            
        # Copy files
        for item in selected_items:
            source_path = item.data(QtCore.Qt.ItemDataRole.UserRole)
            filename = os.path.basename(source_path)
            dest_path = os.path.join(self.dest_directory, filename)
            
            try:
                if os.path.exists(dest_path):
                    response = QtWidgets.QMessageBox.question(
                        self,
                        "File exists",
                        f"File {filename} already exists. Do you want to overwrite it?",
                        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
                    )
                    if response == QtWidgets.QMessageBox.StandardButton.No:
                        self.dest_list.addItem(f"Skipped: {filename} (already exists)")
                        continue
                        
                shutil.copy2(source_path, dest_path)
                self.dest_list.addItem(f"Copied: {filename}")
            except (IOError, PermissionError) as e:
                self.dest_list.addItem(f"Error copying {filename}: {str(e)}")
                
        self.update_free_space()
    
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
