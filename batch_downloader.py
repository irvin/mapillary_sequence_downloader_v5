#!/usr/bin/env python3
"""
Mapillary Batch Sequence Downloader
下載多個 sequences 的批次程式
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
    """從檔案讀取 sequence IDs"""
    sequences = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                seq_id = line.strip()
                if seq_id and not seq_id.startswith('#'):  # 忽略空行和註解
                    sequences.append(seq_id)
        logger.info(f"從 {filename} 讀取到 {len(sequences)} 個 sequences")
        return sequences
    except FileNotFoundError:
        logger.error(f"找不到檔案: {filename}")
        return []
    except Exception as e:
        logger.error(f"讀取檔案錯誤: {e}")
        return []

def download_sequences(sequence_ids, delay=1.0):
    """批次下載 sequences"""
    total = len(sequence_ids)
    successful = 0
    failed = 0

    logger.info(f"開始批次下載 {total} 個 sequences")

    for i, sequence_id in enumerate(sequence_ids, 1):
        logger.info(f"處理 sequence {i}/{total}: {sequence_id}")

        try:
            # 修改 config 中的 sequence_id
            import config
            original_sequence_id = config.sequence_id
            config.sequence_id = sequence_id

            # 下載單個 sequence
            download_single_sequence()

            # 恢復原始 sequence_id
            config.sequence_id = original_sequence_id

            successful += 1
            logger.info(f"✅ Sequence {sequence_id} 下載完成")

        except Exception as e:
            failed += 1
            logger.error(f"❌ Sequence {sequence_id} 下載失敗: {e}")

        # 添加延遲避免 API 限制
        if i < total:  # 最後一個不需要延遲
            logger.info(f"等待 {delay} 秒...")
            time.sleep(delay)

    logger.info(f"批次下載完成: 成功 {successful} 個, 失敗 {failed} 個")

def main():
    """主程式"""
    if len(sys.argv) != 2:
        print("使用方法: python3 batch_downloader.py <sequences_file>")
        print("範例: python3 batch_downloader.py sequences.txt")
        print("\nsequences.txt 格式:")
        print("# 這是註解行")
        print("gEMwF50mdNXOlW7qJUaiRv")
        print("another_sequence_id")
        print("yet_another_sequence_id")
        sys.exit(1)

    sequences_file = sys.argv[1]

    # 讀取 sequences
    sequences = read_sequences_from_file(sequences_file)

    if not sequences:
        logger.error("沒有找到任何 sequences")
        sys.exit(1)

    # 確認是否繼續
    print(f"準備下載 {len(sequences)} 個 sequences:")
    for i, seq in enumerate(sequences, 1):
        print(f"  {i}. {seq}")

    confirm = input("\n是否繼續? (y/N): ").strip().lower()
    if confirm != 'y':
        print("取消下載")
        sys.exit(0)

    # 開始下載
    download_sequences(sequences)

if __name__ == "__main__":
    main()
