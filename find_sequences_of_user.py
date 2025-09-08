#!/usr/bin/env python3
"""
Get All Sequences for a User
Search for all sequences of a user using creator_username
"""

import requests
import time
import logging
from config import access_token

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_all_user_sequences(username, max_pages=None):
    """Get all sequences for specified user"""
    header = {'Authorization': f'OAuth {access_token}'}
    sequences = set()
    all_images = []

    logger.info(f"Starting search for all sequences of user {username}...")

    # First page
    url = f'https://graph.mapillary.com/images?fields=id,sequence,creator,created_at&creator_username={username}&limit=100'

    page = 1
    while url and (max_pages is None or page <= max_pages):
        logger.info(f"Fetching page {page}...")

        try:
            r = requests.get(url, headers=header, timeout=30)
            r.raise_for_status()
            data = r.json()

            images = data.get('data', [])
            logger.info(f"Found {len(images)} images")

            # Extract sequences
            for img in images:
                all_images.append(img)
                if 'sequence' in img and img['sequence']:
                    sequences.add(img['sequence'])

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
    return list(sequences), all_images

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

def save_sequences_to_file(sequences, username, filename=None):
    """Save sequences to file"""
    if filename is None:
        filename = f"sequences_{username}.txt"

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# Found Sequences (Total: {len(sequences)})\n")
            f.write(f"# Search User: {username}\n")
            f.write(f"# Search Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            for seq in sorted(sequences):
                f.write(f"{seq}\n")

        logger.info(f"Sequences saved to {filename}")
        return filename
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        return None

def main():
    """Main program"""
    print("=== Mapillary User Sequences Finder ===")
    print("Search for all sequences of a user using creator_username")
    print()

    # Get username
    username = input("Enter username to search: ").strip()
    if not username:
        print("Username cannot be empty")
        return

    # Ask about page limit
    max_pages_input = input("Maximum search pages (leave empty to search all): ").strip()
    max_pages = None
    if max_pages_input:
        try:
            max_pages = int(max_pages_input)
        except ValueError:
            print("Invalid page number, will search all pages")

    print(f"\nStarting search for sequences of user '{username}'...")
    if max_pages:
        print(f"Maximum {max_pages} pages")
    print()

    # Search sequences
    sequences, images = get_all_user_sequences(username, max_pages)

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

    # Save to file
    filename = save_sequences_to_file(sequences, username)
    if filename:
        print(f"\n✅ Sequences saved to {filename}")
        print(f"\nYou can use the following command for batch download:")
        print(f"python3 batch_downloader.py {filename}")

    print(f"\nSearch completed!")

if __name__ == "__main__":
    main()
