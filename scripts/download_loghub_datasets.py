#!/usr/bin/env python3
import urllib.request
import gzip
import shutil
from pathlib import Path
import json

def download_file(url, destination):
    print(f"Downloading from {url}...")
    try:
        urllib.request.urlretrieve(url, destination)
        print(f"✓ Downloaded to {destination}")
        return True
    except Exception as e:
        print(f"✗ Error downloading: {e}")
        return False

def extract_gz(gz_file, output_file):
    print(f"Extracting {gz_file}...")
    try:
        with gzip.open(gz_file, 'rb') as f_in:
            with open(output_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        print(f"✓ Extracted to {output_file}")
        return True
    except Exception as e:
        print(f"✗ Error extracting: {e}")
        return False

def download_hdfs():
    print("\n" + "="*80)
    print("Downloading HDFS Dataset")
    print("="*80)
    
    data_dir = Path("data/datasets/hdfs")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # HDFS_2k dataset (smaller, faster for testing)
    url = "https://raw.githubusercontent.com/logpai/loghub/master/HDFS/HDFS_2k.log"
    log_file = data_dir / "HDFS_2k.log"
    
    if download_file(url, log_file):
        # Create ground truth (simplified - mark ERROR/FATAL as anomalies)
        create_ground_truth_from_logs(log_file, data_dir / "ground_truth.json")
        return True
    return False

def download_bgl():
    print("\n" + "="*80)
    print("Downloading BGL Dataset")
    print("="*80)
    
    data_dir = Path("data/datasets/bgl")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # BGL_2k dataset (smaller, faster for testing)
    url = "https://raw.githubusercontent.com/logpai/loghub/master/BGL/BGL_2k.log"
    log_file = data_dir / "BGL_2k.log"
    
    if download_file(url, log_file):
        create_ground_truth_from_logs(log_file, data_dir / "ground_truth.json")
        return True
    return False

def create_ground_truth_from_logs(log_file, output_file):
    print(f"Creating ground truth labels from {log_file}...")
    
    labels = []
    error_keywords = ['error', 'fatal', 'critical', 'exception', 'failed', 'failure']
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line_lower = line.lower()
            is_anomaly = any(keyword in line_lower for keyword in error_keywords)
            labels.append(is_anomaly)
    
    ground_truth = {
        'labels': labels,
        'total': len(labels),
        'anomalies': sum(labels),
        'normal': len(labels) - sum(labels)
    }
    
    with open(output_file, 'w') as f:
        json.dump(ground_truth, f, indent=2)
    
    print(f"✓ Created ground truth: {sum(labels)}/{len(labels)} anomalies")

def main():
    print("="*80)
    print("LogHub Dataset Downloader")
    print("="*80)
    
    # Download HDFS
    hdfs_success = download_hdfs()
    
    # Download BGL
    bgl_success = download_bgl()
    
    print("\n" + "="*80)
    print("Download Summary")
    print("="*80)
    print(f"HDFS Dataset: {'✓ Success' if hdfs_success else '✗ Failed'}")
    print(f"BGL Dataset: {'✓ Success' if bgl_success else '✗ Failed'}")
    
    if hdfs_success or bgl_success:
        print("\n✓ Datasets ready for analysis!")
        print("\nYou can now run:")
        if hdfs_success:
            print("  python3 main.py evaluate --log-file data/datasets/hdfs/HDFS_2k.log --ground-truth data/datasets/hdfs/ground_truth.json")
        if bgl_success:
            print("  python3 main.py evaluate --log-file data/datasets/bgl/BGL_2k.log --ground-truth data/datasets/bgl/ground_truth.json")
    else:
        print("\n✗ Dataset download failed")

if __name__ == "__main__":
    main()
