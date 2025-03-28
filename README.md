# rom-antics

**rom-antics** is a GUI-based ROM management tool built with PyQt6. It provides an intuitive two-panel interface for managing your ROM files—enabling you to filter, select, deduplicate, and copy your ROMs from a source directory to a destination directory. Future plans include metadata scraping to support platforms like Batocera, EmulationStation, Garlic OS, and more.

## Overview

**rom-antics** features:

- **Two-Panel Layout:**  
  - **Left Panel (Source):**  
    - Displays ROM files from the source directory.
    - Offers a drop-down menu to filter files by common ROM extensions (e.g., `.chd`, `.iso`, `.bin`, `.n64`, `.rom`).
    - Allows you to select files using checkboxes (navigable with arrow keys and space bar).
    
  - **Right Panel (Destination):**  
    - Lets you choose the destination directory.
    - Displays available free disk space, updating in real time.
    - Logs the status of copied or skipped files.

- **Deduplication:**  
  The application checks for duplicates by comparing file names and sizes in the destination directory. (This can be enhanced later with hash-based comparisons.)

- **Metadata Hooks:**  
  Placeholder functions are included for future integration with metadata scraping, which can enrich ROM installations across different platforms.

## Features

- **File Filtering:**  
  Easily filter files by extension using the drop-down menu.

- **Interactive Selection:**  
  Use the keyboard (arrow keys and space bar) or mouse to select files for copying.

- **Free Space Monitoring:**  
  The destination panel displays the current free space, ensuring you don't run out of room during file transfers.

- **Deduplication:**  
  Prevents copying duplicate files based on filename and size.

- **Future Expandability:**  
  Hooks for metadata scraping will allow integration with various ROM management systems (e.g., Batocera, EmulationStation, Garlic OS).

## Requirements

- Python 3.x  
- PyQt6

## Installation

1. **Clone the Repository:**
   ```bash
   git clone <repository-url>
   cd rom-antics
