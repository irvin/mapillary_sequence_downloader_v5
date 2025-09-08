#!/usr/bin/env python3
"""
Mapillary Batch Sequence Downloader
Batch downloader for multiple sequences
"""

import os
import sys
import time
import logging
from sequence_downloader import main as download_single_sequence

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def read_sequences_from_file(filename):
    """Read sequence IDs from file"""
    sequences = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                seq_id = line.strip()
                if seq_id and not seq_id.startswith('#'):  # Skip empty lines and comments
                    sequences.append(seq_id)
        logger.info(f"Read {len(sequences)} sequences from {filename}")
        return sequences
    except FileNotFoundError:
        logger.error(f"File not found: {filename}")
        return []
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return []

def download_sequences(sequence_ids, delay=1.0, quality=None):
    """Batch download sequences"""
    total = len(sequence_ids)
    successful = 0
    failed = 0

    logger.info(f"Starting batch download of {total} sequences")

    for i, sequence_id in enumerate(sequence_ids, 1):
        logger.info(f"Processing sequence {i}/{total}: {sequence_id}")

        try:
            # Download single sequence with quality parameter
            download_single_sequence(sequence_id, quality)

            successful += 1
            logger.info(f"✅ Sequence {sequence_id} download completed")

        except Exception as e:
            failed += 1
            logger.error(f"❌ Sequence {sequence_id} download failed: {e}")

        # Add delay to avoid API limits
        if i < total:  # No delay for the last one
            logger.info(f"Waiting {delay} seconds...")
            time.sleep(delay)

    logger.info(f"Batch download completed: {successful} successful, {failed} failed")

def main():
    """Main program"""
    import argparse

    parser = argparse.ArgumentParser(description='Batch download Mapillary sequences')
    parser.add_argument('sequences_file', help='File containing sequence IDs')
    parser.add_argument('-q', '--quality', type=int, choices=range(1, 101),
                       help='JPEG quality (1-100). If not specified, saves original quality')

    args = parser.parse_args()

    # Check if config.py exists
    if not os.path.exists("config.py"):
        logger.error("❌ config.py file not found!")
        logger.error("Please create config.py file and set your access_token")
        logger.error("You can copy config.example.py to config.py as a template")
        sys.exit(1)

    sequences_file = args.sequences_file

    # Read sequences
    sequences = read_sequences_from_file(sequences_file)

    if not sequences:
        logger.error("No sequences found")
        sys.exit(1)

    # Confirm before proceeding
    print(f"Ready to download {len(sequences)} sequences:")
    for i, seq in enumerate(sequences, 1):
        print(f"  {i}. {seq}")

    confirm = input("\nContinue? (y/N): ").strip().lower()
    if confirm != 'y':
        print("Download cancelled")
        sys.exit(0)

    # Start download
    download_sequences(sequences, quality=args.quality)

if __name__ == "__main__":
    main()
