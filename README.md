# Mapillary Sequence Downloader v5

A Python script for downloading Mapillary sequence images and adding GPS EXIF data.

> **🤖 AI-Generated Project**  
> This project was created and enhanced using [Cursor AI](https://cursor.sh/)

## Features

- 🗺️ Download all images from a Mapillary sequence
- 📍 Automatically add GPS coordinates to EXIF data
- 📊 Detailed progress tracking and logging
- 🔄 Automatic retry mechanism
- ⚡ Rate limiting protection

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
- `sequence_id`: The sequence ID to download

### 3. Run Script

```bash
python3 sequence_downloader.py
```

## File Structure

```
mapillary_sequence_downloader_v4/
├── sequence_downloader.py        # Main script
├── config.py                     # Config file (not uploaded to git)
├── config.example.py             # Example config file
├── .gitignore                    # Git ignore file
└── downloads/                    # Downloaded images directory
    └── {sequence_id}/
        ├── {image_id1}.jpg
        ├── {image_id2}.jpg
        └── ...
```

## Notes

- `config.py` file contains sensitive information and won't be uploaded to git
- Make sure your API token has sufficient permissions
- Be aware of API rate limits when downloading large numbers of images
