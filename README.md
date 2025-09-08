# Mapillary Sequence Downloader v5

A comprehensive Python toolkit for downloading Mapillary sequence images with enhanced EXIF data and batch processing capabilities.

> **🤖 AI-Generated Project**  
> This project was created and enhanced using [Cursor AI](https://cursor.sh/)

## Features

- 🗺️ Download all images from Mapillary sequences
- 📍 Automatically add comprehensive GPS and camera EXIF data
- 📊 Detailed progress tracking and logging
- 🔄 Automatic retry mechanism with rate limiting
- ⚡ Batch download multiple sequences
- 🔍 Find all sequences for a specific user
- 📅 Time-based folder and filename organization
- 🌍 Enhanced GPS accuracy using computed geometry
- 📷 Complete camera metadata extraction

## Installation & Setup

### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv mapillary_env

# Activate virtual environment
source mapillary_env/bin/activate  # macOS/Linux
# or
mapillary_env\Scripts\activate     # Windows

# Install packages
pip install requests pillow piexif vt2geojson
```

### 2. Configure Settings

```bash
# Copy example config file
cp config.example.py config.py

# Edit config file with your data
nano config.py
```

Set in `config.py`:

- `access_token`: Your Mapillary API access token

## Usage

### 1. Download a Single Sequence

```bash
python3 sequence_downloader.py <sequence_id> [-q QUALITY]
```

**Examples:**

```bash
# Download with original quality (default)
python3 sequence_downloader.py 3NpXMDuHm9IZQ1vBW6q4T0

# Download with specific quality (1-100)
python3 sequence_downloader.py 3NpXMDuHm9IZQ1vBW6q4T0 -q 95
```

### 2. Find All Sequences for a User

```bash
python3 find_sequences_of_user.py
```

This will:

- Search for all sequences belonging to a specific username
- Display detailed analysis of each sequence
- Save sequence IDs to a text file for batch processing

### 3. Batch Download Multiple Sequences

```bash
python3 batch_downloader.py <sequences_file> [-q QUALITY]
```

**Examples:**

```bash
# Batch download with original quality (default)
python3 batch_downloader.py sequences_irvinfly.txt

# Batch download with specific quality
python3 batch_downloader.py sequences_irvinfly.txt -q 95
```

### 4. Complete Workflow

```bash
# 1. Find all sequences for a user
python3 find_sequences_of_user.py

# 2. Batch download all found sequences
python3 batch_downloader.py sequences_irvinfly.txt
```

## File Structure

```text
mapillary_sequence_downloader_v4/
├── sequence_downloader.py        # Main download script
├── find_sequences_of_user.py     # User sequence finder
├── batch_downloader.py           # Batch download script
├── config.py                     # Config file (not uploaded to git)
├── config.example.py             # Example config file
├── .gitignore                    # Git ignore file
├── sequences_*.txt               # Generated sequence lists
└── downloads/                    # Downloaded images directory
    ├── 20250728_180730_3NpXMDuH/    # Time-based folder names
    │   ├── 20250728_180730_120.jpg  # Time-based filenames
    │   ├── 20250728_180731_109.jpg
    │   └── ...
    └── 20250728_180800_steh5jB/
        ├── 20250728_180800_001.jpg
        └── ...
```

## EXIF Data Enhancement

The script automatically adds comprehensive EXIF data to downloaded images:

### GPS Data

- **GPS Coordinates**: Latitude, longitude with high precision
- **GPS Altitude**: Elevation data when available
- **GPS Timestamp**: Precise capture time with millisecond accuracy
- **GPS Direction**: Camera heading using computed compass angle
- **GPS Reference**: Proper coordinate system references

### Camera Data

- **Camera Make/Model**: From Mapillary metadata
- **Focal Length**: Calculated from camera parameters
- **Image Dimensions**: Actual pixel dimensions
- **Orientation**: Proper image orientation
- **Date/Time**: Original capture time with millisecond precision

### Enhanced Features

- **Computed Geometry**: Uses Mapillary's post-processed GPS for higher accuracy
- **3D Reconstruction Data**: Includes mesh, atomic scale, and SfM cluster data
- **Compass Angles**: Both original and computed compass angles
- **Camera Parameters**: Complete camera calibration data

## Output Organization

### Folder Naming

- **Format**: `YYYYMMDD_HHMMSS_SequenceID`
- **Example**: `20250728_180730_3NpXMDuH`

### File Naming

- **Format**: `YYYYMMDD_HHMMSS_milliseconds.jpg`
- **Example**: `20250728_180730_120.jpg`

## Image Quality Options

- **Default**: Images are saved with original quality (no compression)
- **Optional**: Use `-q` or `--quality` parameter to specify JPEG quality (1-100)
- **Quality 95**: Good balance between file size and quality
- **Quality 100**: Maximum quality (larger file size)

## Notes

- `config.py` file contains sensitive information and won't be uploaded to git
- Make sure your API token has sufficient permissions
- Be aware of API rate limits when downloading large numbers of images
- Original quality is recommended for archival purposes
