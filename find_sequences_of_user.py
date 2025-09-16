#!/usr/bin/env python3
"""
Get All Sequences for a User
Search for all sequences of a user using creator_username
"""

import requests
import time
import logging
from datetime import datetime
from collections import defaultdict
from config import access_token

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_all_user_sequences(username, max_pages=None, camera_type_filter=None, output_file=None):
    """Get all sequences for specified user with optional camera type filtering"""
    header = {'Authorization': f'OAuth {access_token}'}
    sequences = set()
    all_images = []
    new_sequences = set()  # Track new sequences found in current page
    sequences_by_date = defaultdict(set)  # Group sequences by date

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

            # Reset new sequences for this page
            new_sequences.clear()

            # Extract sequences with optional camera type filtering
            for img in images:
                # Apply camera type filter if specified
                if camera_type_filter:
                    img_camera_type = img.get('camera_type', '')
                    if camera_type_filter.lower() not in img_camera_type.lower():
                        continue

                all_images.append(img)
                if 'sequence' in img and img['sequence']:
                    seq_id = img['sequence']
                    if seq_id not in sequences:
                        sequences.add(seq_id)
                        new_sequences.add(seq_id)

                    # Group sequence by date
                    # Try captured_at first, then created_at
                    timestamp = None
                    if 'captured_at' in img and img['captured_at']:
                        timestamp = img['captured_at']
                    elif 'created_at' in img and img['created_at']:
                        timestamp = img['created_at']

                    if timestamp:
                        # Convert timestamp to date string (YYYYMMDD format)
                        img_date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y%m%d')
                        sequences_by_date[img_date].add(seq_id)

            # Log new sequences found
            if new_sequences:
                logger.info(f"Found {len(new_sequences)} new sequences in page {page}")

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

    logger.info(f"Search completed, found {len(all_images)} images, {len(sequences)} sequences")
    return list(sequences), all_images, sequences_by_date

def analyze_sequences(sequences, images):
    """Analyze sequences information"""
    logger.info("\n=== Sequences Analysis ===")

    # Sort sequences by time
    sequence_info = {}
    for img in images:
        if 'sequence' in img and img['sequence']:
            seq_id = img['sequence']
            if seq_id not in sequence_info:
                sequence_info[seq_id] = {
                    'image_count': 0,
                    'first_image': None,
                    'last_image': None,
                    'created_at': None
                }

            sequence_info[seq_id]['image_count'] += 1

            # Record time information
            if 'created_at' in img:
                img_time = img['created_at']
                if sequence_info[seq_id]['first_image'] is None or img_time < sequence_info[seq_id]['first_image']:
                    sequence_info[seq_id]['first_image'] = img_time
                if sequence_info[seq_id]['last_image'] is None or img_time > sequence_info[seq_id]['last_image']:
                    sequence_info[seq_id]['last_image'] = img_time
                    sequence_info[seq_id]['created_at'] = img_time

    # Show top 10 sequences information
    sorted_sequences = sorted(sequence_info.items(), key=lambda x: x[1]['created_at'] or 0, reverse=True)

    logger.info(f"Top 10 sequences information:")
    for i, (seq_id, info) in enumerate(sorted_sequences[:10], 1):
        logger.info(f"{i:2d}. {seq_id}")
        logger.info(f"    Image count: {info['image_count']}")
        if info['created_at']:
            from datetime import datetime
            dt = datetime.fromtimestamp(info['created_at'] / 1000)
            logger.info(f"    Latest image: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("")

def save_sequences_to_file_by_date(sequences_by_date, username, filename=None, max_pages=None, camera_type_filter=None, filter_type=None):
    """Save sequences to file grouped by date"""
    if filename is None:
        filename = f"sequences_{username}.txt"

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            total_sequences = sum(len(seqs) for seqs in sequences_by_date.values())
            f.write(f"# Found Sequences (Total: {total_sequences})\n")
            f.write(f"# Search User: {username}\n")
            f.write(f"# Search Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Max Pages: {max_pages if max_pages else 'All'}\n")
            f.write(f"# Camera Type Filter: {camera_type_filter if camera_type_filter else 'All'}\n")
            f.write(f"# Filter Type: {filter_type if filter_type else 'all'}\n\n")

            # Sort dates in descending order (newest first)
            for date in sorted(sequences_by_date.keys(), reverse=True):
                f.write(f"# {date}\n")
                for seq in sorted(sequences_by_date[date]):
                    f.write(f"{seq}\n")
                f.write("\n")  # Add empty line between dates

        logger.info(f"Sequences saved to {filename}")
        return filename
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        return None

def main():
    """Main program"""
    import argparse

    parser = argparse.ArgumentParser(description='Find all sequences for a Mapillary user')
    parser.add_argument('username', nargs='?', help='Username to search for')
    parser.add_argument('-p', '--max-pages', type=int, help='Maximum number of pages to search')
    parser.add_argument('-f', '--filter', choices=['all', '360', 'regular'],
                       default='all', help='Filter by camera type (360=spherical, regular=perspective)')

    args = parser.parse_args()

    print("=== Mapillary User Sequences Finder ===")
    print("Search for all sequences of a user using creator_username")
    print()

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

    # Interactive filter selection if not specified via command line
    if camera_type_filter is None and args.filter == 'all':
        print("\nCamera type filter options:")
        print("1. All photos (default)")
        print("2. 360 photos only")
        print("3. Regular photos only")

        filter_choice = input("Choose filter (1-3, default=1): ").strip()

        if filter_choice == "2":
            camera_type_filter = "spherical"
        elif filter_choice == "3":
            camera_type_filter = "perspective"

    print(f"\nStarting search for sequences of user '{username}'...")
    if max_pages:
        print(f"Maximum {max_pages} pages")
    if camera_type_filter:
        print(f"Filtering for camera type: {camera_type_filter}")
    print()

    # Prepare output file
    output_file = f"sequences_{username}.txt"

    # Clear existing file and add header
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# Found Sequences (Search in progress...)\n")
            f.write(f"# Search User: {username}\n")
            f.write(f"# Search Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Max Pages: {max_pages if max_pages else 'All'}\n")
            f.write(f"# Camera Type Filter: {camera_type_filter if camera_type_filter else 'All'}\n")
            f.write(f"# Filter Type: {args.filter}\n\n")
        print(f"📝 Output file prepared: {output_file}")
    except Exception as e:
        logger.error(f"Error preparing output file: {e}")
        print(f"❌ Error preparing output file: {e}")
        return

    # Search sequences with real-time file writing
    sequences, images, sequences_by_date = get_all_user_sequences(username, max_pages, camera_type_filter, output_file)

    if not sequences:
        print("No sequences found")
        return

    # Show results
    print(f"\n=== Search Results ===")
    print(f"Found {len(sequences)} sequences:")
    for i, seq in enumerate(sorted(sequences), 1):
        print(f"{i:2d}. {seq}")

    # Analyze sequences
    analyze_sequences(sequences, images)

    # Save sequences grouped by date
    try:
        save_sequences_to_file_by_date(sequences_by_date, username, output_file, max_pages, camera_type_filter, args.filter)
        print(f"\n✅ All sequences saved to {output_file} (grouped by date)")
        print(f"\nYou can use the following command for batch download:")
        print(f"python3 batch_downloader.py {output_file}")
    except Exception as e:
        logger.error(f"Error saving sequences by date: {e}")
        print(f"\n❌ Error saving sequences by date: {e}")

    print(f"\nSearch completed!")

if __name__ == "__main__":
    main()
