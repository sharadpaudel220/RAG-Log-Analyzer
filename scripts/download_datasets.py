#!/usr/bin/env python3
import os
import urllib.request
import tarfile
import zipfile
from pathlib import Path

def download_file(url, destination):
    print(f"Downloading {url}...")
    urllib.request.urlretrieve(url, destination)
    print(f"Downloaded to {destination}")

def extract_archive(archive_path, extract_to):
    print(f"Extracting {archive_path}...")
    
    if archive_path.endswith('.tar.gz') or archive_path.endswith('.tgz'):
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(extract_to)
    elif archive_path.endswith('.zip'):
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
    
    print(f"Extracted to {extract_to}")

def download_hdfs_dataset():
    data_dir = Path("data/datasets/hdfs")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    print("HDFS Dataset Download Instructions:")
    print("=" * 80)
    print("The HDFS dataset can be downloaded from:")
    print("https://github.com/logpai/loghub")
    print("\nPlease download HDFS logs and place them in:")
    print(f"  {data_dir.absolute()}")
    print("\nExpected file: HDFS.log or HDFS_2k.log")
    print("=" * 80)

def download_bgl_dataset():
    data_dir = Path("data/datasets/bgl")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    print("BGL Dataset Download Instructions:")
    print("=" * 80)
    print("The BGL dataset can be downloaded from:")
    print("https://github.com/logpai/loghub")
    print("\nPlease download BGL logs and place them in:")
    print(f"  {data_dir.absolute()}")
    print("\nExpected file: BGL.log or BGL_2k.log")
    print("=" * 80)

def create_sample_logs():
    sample_dir = Path("data/datasets/sample")
    sample_dir.mkdir(parents=True, exist_ok=True)
    
    sample_logs = [
        "2024-01-15 10:23:45 INFO [DataNode] Received block blk_123456789 from /10.0.0.1:50010",
        "2024-01-15 10:23:46 INFO [DataNode] PacketResponder: received block blk_123456789",
        "2024-01-15 10:23:47 ERROR [DataNode] Exception in receiveBlock for block blk_987654321",
        "2024-01-15 10:23:48 FATAL [DataNode] Out of memory error while processing block",
        "2024-01-15 10:23:49 WARN [NameNode] Connection timeout to DataNode at /10.0.0.2:50010",
        "2024-01-15 10:23:50 ERROR [NameNode] Failed to connect to DataNode /10.0.0.2:50010",
        "2024-01-15 10:23:51 INFO [DataNode] Successfully stored block blk_111222333",
        "2024-01-15 10:23:52 CRITICAL [DataNode] Disk space exhausted on /data/hadoop",
        "2024-01-15 10:23:53 ERROR [NameNode] Authentication failed for user hadoop",
        "2024-01-15 10:23:54 INFO [DataNode] Heartbeat sent to NameNode",
        "2024-01-15 10:23:55 ERROR [DataNode] Block blk_444555666 is corrupt",
        "2024-01-15 10:23:56 WARN [NameNode] Replica not found for block blk_777888999",
        "2024-01-15 10:23:57 INFO [DataNode] Block received: blk_123123123",
        "2024-01-15 10:23:58 ERROR [DataNode] Connection refused by NameNode",
        "2024-01-15 10:23:59 FATAL [NameNode] Service unavailable - backend down",
    ]
    
    sample_file = sample_dir / "sample_logs.log"
    with open(sample_file, 'w') as f:
        for log in sample_logs:
            f.write(log + '\n')
    
    print(f"Created sample logs at {sample_file}")
    
    ground_truth = {
        'labels': [False, False, True, True, True, True, False, True, True, False, True, True, False, True, True]
    }
    
    import json
    gt_file = sample_dir / "ground_truth.json"
    with open(gt_file, 'w') as f:
        json.dump(ground_truth, f, indent=2)
    
    print(f"Created ground truth at {gt_file}")

def main():
    print("Log Analyzer Dataset Setup")
    print("=" * 80)
    
    create_sample_logs()
    print()
    
    download_hdfs_dataset()
    print()
    
    download_bgl_dataset()
    print()
    
    print("Dataset setup complete!")
    print("\nYou can now run the system with sample logs:")
    print("  python main.py analyze --log-file data/datasets/sample/sample_logs.log")

if __name__ == "__main__":
    main()
