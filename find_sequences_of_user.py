#!/usr/bin/env python3
"""
Mapillary User Sequences Finder

Features:
- Search for all Mapillary sequences of a specified user
- Support camera type filtering (perspective photos or 360-degree spherical photos)
- Group sequences by date and write to file in real-time

Writing Logic:
1. Record the first found date and its sequences
2. Continue recording sequences for the current date
3. When a new date is discovered:
   a. Write the currently recorded data
   b. Clear the recorded data
   c. Start recording the new date and its sequences
4. If search is completed, write the currently recorded data
5. If search is not completed, return to step 2

Output Format:
- File header contains search parameters (user, time, page limit, camera type filter)
- Sequences grouped by date, sorted by timestamp within each date (newest first)
- Each date block separated by empty lines

Usage:
python3 find_sequences_of_user.py <username> [-p <max_pages>] [-f <filter>]

Parameters:
- username: Mapillary username to search for
- -p, --max-pages: Maximum number of pages to search (optional, search all if not specified)
- -f, --filter: Camera type filter (all/360/regular, default is all)
  - all: Search all types
  - 360: Search only 360-degree photos (spherical)
  - regular: Search only perspective photos

Examples:
python3 find_sequences_of_user.py username -p 50 -f regular
python3 find_sequences_of_user.py username -f 360
"""

import requests
import time
import logging
from datetime import datetime
from config import access_token

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def write_file_header(filename, username, max_pages, camera_type_filter):
    """Write file header with search parameters"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# Search Mapillary Sequences by User\n")
            f.write(f"# User: {username}\n")
            f.write(f"# Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Max Pages: {max_pages if max_pages else 'All'}\n")
            f.write(f"# Image Type Filter: {camera_type_filter if camera_type_filter else 'All'}\n\n")
        return True
    except Exception as e:
        logger.error(f"Error writing file header: {e}")
        return False

def write_sequences_for_date(date, sequences, sequence_timestamps, filename):
    """Write sequences for a single date to file"""
    try:
        with open(filename, 'a', encoding='utf-8') as f:
            f.write(f"# {date}\n")

            # Sort sequences by timestamp (newest first)
            if sequence_timestamps:
                sorted_sequences = sorted(sequences,
                                        key=lambda seq: sequence_timestamps.get(seq, 0),
                                        reverse=True)
            else:
                sorted_sequences = sorted(sequences)

            for seq in sorted_sequences:
                f.write(f"{seq}\n")
            f.write("\n")  # Add empty line after date

        logger.info(f"✅ Written date {date} with {len(sequences)} sequences")
        return True
    except Exception as e:
        logger.error(f"Error writing date {date} to file: {e}")
        return False

def get_all_user_sequences(username, max_pages=None, camera_type_filter=None, output_file=None):
    """Get all sequences for specified user with optional camera type filtering"""
    header = {'Authorization': f'OAuth {access_token}'}
    sequence_timestamps = {}  # Store timestamp for each sequence
    current_date = None  # Track current date being processed
    current_sequences = set()  # Track sequences for current date
    total_sequences = 0  # Count total sequences found

    logger.info(f"Starting search for all sequences of user {username}...")
    if camera_type_filter:
        logger.info(f"Filtering for camera type: {camera_type_filter}")

    # First page - include camera_type in fields
    url = f'https://graph.mapillary.com/images?fields=id,sequence,creator,created_at,camera_type,captured_at&creator_username={username}&limit=100'

    page = 1
    while url and (max_pages is None or page <= max_pages):
        logger.info(f"Fetching page {page}...")

        try:
            r = requests.get(url, headers=header, timeout=30)
            r.raise_for_status()
            data = r.json()

            images = data.get('data', [])
            logger.info(f"Found {len(images)} images")


            # Process sequences for current page
            for img in images:
                # Apply camera type filter if specified
                if camera_type_filter:
                    img_camera_type = img.get('camera_type', '')
                    if camera_type_filter.lower() not in img_camera_type.lower():
                        continue

                if 'sequence' in img and img['sequence']:
                    seq_id = img['sequence']

                    # Group sequence by date and store timestamp
                    timestamp = None
                    if 'captured_at' in img and img['captured_at']:
                        timestamp = img['captured_at']
                    elif 'created_at' in img and img['created_at']:
                        timestamp = img['created_at']

                    if timestamp:
                        # Store the latest timestamp for this sequence
                        if seq_id not in sequence_timestamps or timestamp > sequence_timestamps[seq_id]:
                            sequence_timestamps[seq_id] = timestamp

                        # Convert timestamp to date string (YYYYMMDD format)
                        img_date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y%m%d')

                        # 1. Record the first found date
                        if current_date is None:
                            current_date = img_date
                            current_sequences = set()
                            logger.info(f"📅 Found first date: {img_date}")

                        # 2. Continue recording sequences for the current date
                        if img_date == current_date:
                            current_sequences.add(seq_id)
                        # 3. When a new date is discovered
                        elif img_date != current_date:
                            logger.info(f"📅 Found new date: {img_date}")
                            # a. Write the currently recorded data
                            if output_file and current_date and current_sequences:
                                write_sequences_for_date(
                                    current_date,
                                    current_sequences,
                                    sequence_timestamps,
                                    output_file
                                )
                                total_sequences += len(current_sequences)

                            # b. Clear the recorded data
                            # c. Start recording the new date and its sequences
                            current_date = img_date
                            current_sequences = {seq_id}

            # Check if there's a next page
            if 'paging' in data and 'next' in data['paging']:
                url = data['paging']['next']
                page += 1
                time.sleep(0.5)  # Avoid API limits
            else:
                url = None
                logger.info("Reached the last page")

        except Exception as e:
            logger.error(f"Error fetching page {page}: {e}")
            break

    # 4. If search is completed, write the currently recorded data
    if output_file and current_date and current_sequences:
        write_sequences_for_date(
            current_date,
            current_sequences,
            sequence_timestamps,
            output_file
        )
        logger.info(f"✅ Written final date {current_date}")
        total_sequences += len(current_sequences)

    return total_sequences, sequence_timestamps

def main():
    """Main program"""
    import argparse

    parser = argparse.ArgumentParser(description='Find all sequences for a Mapillary user')
    parser.add_argument('username', nargs='?', help='Username to search for')
    parser.add_argument('-p', '--max-pages', type=int, help='Maximum number of pages to search')
    parser.add_argument('-f', '--filter', choices=['all', '360', 'regular'],
                       default='all', help='Filter by camera type (360=spherical, regular=perspective)')

    args = parser.parse_args()

    logger.info("=== Mapillary User Sequences Finder ===")
    logger.info("Search for all sequences of a user using creator_username")
    logger.info("")

    # Get username
    if args.username:
        username = args.username
    else:
        username = input("Enter username to search: ").strip()
        if not username:
            print("Username cannot be empty")
            return

    # Get page limit
    max_pages = args.max_pages
    if max_pages is None:
        max_pages_input = input("Maximum search pages (leave empty to search all): ").strip()
        if max_pages_input:
            try:
                max_pages = int(max_pages_input)
            except ValueError:
                print("Invalid page number, will search all pages")
                max_pages = None

    # Get camera type filter
    camera_type_filter = None
    if args.filter == '360':
        camera_type_filter = "spherical"
    elif args.filter == 'regular':
        camera_type_filter = "perspective"

    logger.info(f"Starting search for sequences of user '{username}'...")
    if max_pages:
        logger.info(f"Maximum {max_pages} pages")
    if camera_type_filter:
        logger.info(f"Filtering for camera type: {camera_type_filter}")
    logger.info("")

    # Prepare output file
    output_file = f"sequences_{username}.txt"

    # Write file header
    if not write_file_header(output_file, username, max_pages, camera_type_filter):
        print(f"❌ Error preparing output file")
        return

    logger.info(f"📝 Output file prepared: {output_file}")

    # Search sequences with real-time file writing
    total_sequences, sequence_timestamps = get_all_user_sequences(
        username, max_pages, camera_type_filter, output_file
    )

    if total_sequences == 0:
        logger.info("No sequences found")
        return

    # Show results
    logger.info("=== Search Results ===")
    logger.info(f"Found {total_sequences} sequences")
    logger.info(f"✅ All sequences saved to {output_file}")
    logger.info(f"You can use the following command for batch download:")
    logger.info(f"python3 batch_downloader.py {output_file}")

if __name__ == "__main__":
    main()