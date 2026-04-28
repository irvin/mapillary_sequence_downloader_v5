#!/usr/bin/env python3
"""
Download Mapillary images listed in a personal-data takeout images.tsv.

This does not use sequence IDs. It reads img_fbid values from the takeout TSV,
fetches each image's thumb_original_url from the Graph API, and writes the
returned bytes directly to disk.
"""

import argparse
import csv
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

from config import access_token


FIELDS = "id,thumb_original_url,captured_at,camera_type"


def parse_date(value, end_of_day=False):
    if not value:
        return None

    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt)
            if end_of_day:
                dt = dt.replace(hour=23, minute=59, second=59, microsecond=999000)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    raise ValueError(f"Invalid date: {value}. Use YYYYMMDD or YYYY-MM-DD.")


def parse_capture_time(value):
    if not value or value == r"\N":
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def iter_takeout_rows(tsv_path, camera_type=None, start_date=None, end_date=None):
    with open(tsv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if camera_type and row.get("camera_type") != camera_type:
                continue

            captured_at = parse_capture_time(row.get("captured_at"))
            if start_date and (captured_at is None or captured_at < start_date):
                continue
            if end_date and (captured_at is None or captured_at > end_date):
                continue

            yield row


def safe_timestamp(captured_at):
    parsed = parse_capture_time(captured_at)
    if not parsed:
        return "unknown_time"
    return parsed.strftime("%Y%m%d_%H%M%S_%f")[:19]


def output_path_for(row, output_dir):
    captured_at = row.get("captured_at") or ""
    day = captured_at[:10].replace("-", "") if captured_at else "unknown_date"
    filename = f"{safe_timestamp(captured_at)}_{row['img_fbid']}.jpg"
    return os.path.join(output_dir, day, filename)


def request_with_retry(session, url, *, headers=None, params=None, max_retries=3):
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(url, headers=headers, params=params, timeout=60)
            response.raise_for_status()
            return response
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(2 ** (attempt - 1))
    raise last_error


def download_one(row, output_dir, skip_existing=True):
    output_path = output_path_for(row, output_dir)
    if skip_existing and os.path.exists(output_path):
        return ("skipped", row["img_fbid"], output_path)

    headers = {"Authorization": f"OAuth {access_token}"}
    image_id = row["img_fbid"]

    with requests.Session() as session:
        metadata_response = request_with_retry(
            session,
            f"https://graph.mapillary.com/{image_id}",
            headers=headers,
            params={"fields": FIELDS},
        )
        metadata = metadata_response.json()
        image_url = metadata.get("thumb_original_url")
        if not image_url:
            return ("missing_url", image_id, output_path)

        image_response = request_with_retry(session, image_url)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        tmp_path = f"{output_path}.tmp"
        with open(tmp_path, "wb") as f:
            f.write(image_response.content)
        os.replace(tmp_path, output_path)

    return ("downloaded", image_id, output_path)


def main():
    parser = argparse.ArgumentParser(description="Download images from Mapillary takeout images.tsv")
    parser.add_argument("tsv", help="Path to takeout images.tsv")
    parser.add_argument("-o", "--output-dir", default="takeout_downloads",
                        help="Directory for downloaded images")
    parser.add_argument("-f", "--filter", choices=["all", "360", "regular"], default="all",
                        help="Camera type filter (360=spherical, regular=perspective)")
    parser.add_argument("--start-date", help="Only include images captured on or after this date")
    parser.add_argument("--end-date", help="Only include images captured on or before this date")
    parser.add_argument("--limit", type=int, help="Maximum number of images to download")
    parser.add_argument("--workers", type=int, default=4, help="Parallel download workers")
    parser.add_argument("--dry-run", action="store_true", help="Only count matching rows")
    parser.add_argument("--overwrite", action="store_true", help="Re-download existing files")

    args = parser.parse_args()

    start_date = parse_date(args.start_date, end_of_day=False)
    end_date = parse_date(args.end_date, end_of_day=True)

    camera_type = None
    if args.filter == "360":
        camera_type = "spherical"
    elif args.filter == "regular":
        camera_type = "perspective"

    rows = list(iter_takeout_rows(args.tsv, camera_type, start_date, end_date))
    if args.limit is not None:
        rows = rows[:args.limit]

    print(f"Matched images: {len(rows)}")
    if args.dry_run or not rows:
        return

    counts = {"downloaded": 0, "skipped": 0, "missing_url": 0, "error": 0}
    failures_path = os.path.join(args.output_dir, "failures.tsv")
    os.makedirs(args.output_dir, exist_ok=True)

    with open(failures_path, "a", encoding="utf-8") as failures:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(download_one, row, args.output_dir, not args.overwrite): row
                for row in rows
            }
            for i, future in enumerate(as_completed(futures), 1):
                row = futures[future]
                try:
                    status, image_id, path = future.result()
                    counts[status] = counts.get(status, 0) + 1
                    print(f"[{i}/{len(rows)}] {status}: {image_id} -> {path}")
                except Exception as e:
                    counts["error"] += 1
                    failures.write(f"{row.get('img_fbid')}\t{type(e).__name__}\t{e}\n")
                    failures.flush()
                    print(f"[{i}/{len(rows)}] error: {row.get('img_fbid')} ({e})")

    print("Summary:")
    for key in sorted(counts):
        print(f"  {key}: {counts[key]}")


if __name__ == "__main__":
    main()
