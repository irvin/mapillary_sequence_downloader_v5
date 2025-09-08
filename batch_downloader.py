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

def download_sequences(sequence_ids, delay=1.0):
    """Batch download sequences"""
    total = len(sequence_ids)
    successful = 0
    failed = 0

    logger.info(f"Starting batch download of {total} sequences")

    for i, sequence_id in enumerate(sequence_ids, 1):
        logger.info(f"Processing sequence {i}/{total}: {sequence_id}")

        try:
            # Download single sequence, only pass sequence_id
            download_single_sequence(sequence_id)

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
    if len(sys.argv) != 2:
        print("Usage: python3 batch_downloader.py <sequences_file>")
        print("Example: python3 batch_downloader.py sequences.txt")
        print("\nsequences.txt format:")
        print("# This is a comment line")
        print("gEMwF50mdNXOlW7qJUaiRv")
        print("another_sequence_id")
        print("yet_another_sequence_id")
        sys.exit(1)

    # Check if config.py exists
    if not os.path.exists("config.py"):
        logger.error("❌ config.py file not found!")
        logger.error("Please create config.py file and set your access_token")
        logger.error("You can copy config.example.py to config.py as a template")
        sys.exit(1)

    sequences_file = sys.argv[1]

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
    download_sequences(sequences)

if __name__ == "__main__":
    main()
