import requests, json, os
from PIL import Image
import piexif
from io import BytesIO
import time
from datetime import datetime
import logging

# Load parameters from config file
try:
    from config import access_token, sequence_id
except ImportError:
    print("❌ config.py file not found!")
    print("Please create config.py file and set your access_token and sequence_id")
    exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def add_gps_exif_data(latitude, longitude, image_id, sequence_id=None):
    """
    Add GPS and basic EXIF data to image
    """
    def convert_to_degrees(value):
        d = int(value)
        m = int((value - d) * 60)
        s = (value - d - m/60) * 3600
        return d, m, s

    lat_deg = convert_to_degrees(latitude)
    lon_deg = convert_to_degrees(longitude)

    # GPS information
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: 'N' if latitude >= 0 else 'S',
        piexif.GPSIFD.GPSLatitude: [(lat_deg[0], 1), (lat_deg[1], 1), (int(lat_deg[2]*100), 100)],
        piexif.GPSIFD.GPSLongitudeRef: 'E' if longitude >= 0 else 'W',
        piexif.GPSIFD.GPSLongitude: [(lon_deg[0], 1), (lon_deg[1], 1), (int(lon_deg[2]*100), 100)],
        piexif.GPSIFD.GPSAltitudeRef: 0,  # Above sea level
        piexif.GPSIFD.GPSAltitude: (0, 1),  # Default altitude
        piexif.GPSIFD.GPSTimeStamp: [(0, 1), (0, 1), (0, 1)],
        piexif.GPSIFD.GPSDateStamp: datetime.now().strftime('%Y:%m:%d')
    }

    # Basic image information
    zeroth_ifd = {
        piexif.ImageIFD.Make: 'Mapillary',
        piexif.ImageIFD.Model: 'Street View Camera',
        piexif.ImageIFD.Software: 'Mapillary Sequence Downloader v4',
        piexif.ImageIFD.DateTime: datetime.now().strftime('%Y:%m:%d %H:%M:%S'),
        piexif.ImageIFD.XResolution: (72, 1),
        piexif.ImageIFD.YResolution: (72, 1),
        piexif.ImageIFD.ResolutionUnit: 2,
        piexif.ImageIFD.Orientation: 1,
    }

    # Camera information
    exif_ifd = {
        piexif.ExifIFD.DateTimeOriginal: datetime.now().strftime('%Y:%m:%d %H:%M:%S'),
        piexif.ExifIFD.DateTimeDigitized: datetime.now().strftime('%Y:%m:%d %H:%M:%S'),
    }

    # Add Mapillary specific information to UserComment
    mapillary_info = f"Mapillary Image ID: {image_id}"
    if sequence_id:
        mapillary_info += f" | Sequence: {sequence_id}"
    mapillary_info += f" | Downloaded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    exif_ifd[piexif.ExifIFD.UserComment] = mapillary_info.encode('utf-8')

    exif_dict = {
        "0th": zeroth_ifd,
        "Exif": exif_ifd,
        "GPS": gps_ifd,
        "1st": {},
        "thumbnail": None
    }

    try:
        exif_bytes = piexif.dump(exif_dict)
        return exif_bytes
    except Exception as e:
        logger.warning(f"Failed to create EXIF data: {e}")
        return None

def get_image_detections(image_id, access_token):
    """
    Get image detection data (traffic signs, objects, etc.)
    """
    try:
        detections_url = f"https://graph.mapillary.com/{image_id}/detections"
        headers = {'Authorization': f'OAuth {access_token}'}
        response = requests.get(detections_url, headers=headers, timeout=10)

        if response.status_code == 200:
            return response.json().get('data', [])
        else:
            logger.warning(f"Failed to get detection data for {image_id}: {response.status_code}")
            return []
    except Exception as e:
        logger.warning(f"Error getting detection data: {e}")
        return []

def download_image_with_retry(url, max_retries=3):
    """
    Download image with retry mechanism
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.warning(f"Failed to download image (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise e

def main():
    if not os.path.exists("downloads"):
        os.makedirs("downloads")


    # Get all image IDs in the sequence
    logger.info(f"Getting image list for sequence {sequence_id}...")
    url = f"https://graph.mapillary.com/image_ids?sequence_id={sequence_id}"
    header = {'Authorization': f'OAuth {access_token}'}

    try:
        r = requests.get(url, headers=header, timeout=30)
        r.raise_for_status()
        data = r.json()
        image_ids = data.get("data", [])
        logger.info(f"Found {len(image_ids)} images")
    except Exception as e:
        logger.error(f"Failed to get image list: {e}")
        return

    # Process each image and download
    for i, img_id in enumerate(image_ids, 1):
        try:
            logger.info(f"Processing image {i}/{len(image_ids)}: {img_id['id']}")

            # Get basic image information
            fields = ['thumb_original_url', 'geometry']
            image_url = f"https://graph.mapillary.com/{img_id['id']}?fields={','.join(fields)}"
            img_r = requests.get(image_url, headers=header, timeout=30)
            img_r.raise_for_status()
            img_data = img_r.json()

            # Get detection data
            detections = get_image_detections(img_id['id'], access_token)

            # Download image
            image_get_url = img_data['thumb_original_url']
            logger.info(f"Downloading image...")
            image_data = download_image_with_retry(image_get_url)

            # Create output directory
            output_dir = f"downloads/{sequence_id}"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            # Process image and add EXIF data
            image = Image.open(BytesIO(image_data))

            # Add GPS EXIF data
            exif_bytes = add_gps_exif_data(
                img_data['geometry']['coordinates'][1],  # latitude
                img_data['geometry']['coordinates'][0],  # longitude
                img_id['id'],
                sequence_id
            )

            # Save image
            output_path = f"{output_dir}/{img_id['id']}.jpg"
            if exif_bytes:
                image.save(output_path, exif=exif_bytes, quality=95)
                logger.info(f"✅ Image saved with GPS EXIF data: {output_path}")
            else:
                image.save(output_path, quality=95)
                logger.info(f"✅ Image saved (no EXIF data): {output_path}")

            # Log detected objects
            if detections:
                detection_types = [d.get('value', 'unknown') for d in detections]
                logger.info(f"🔍 Detected {len(detections)} objects: {', '.join(set(detection_types))}")

            # Add delay to avoid rate limiting
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"❌ Error processing image {img_id['id']}: {e}")
            continue

    logger.info("🎉 Download completed!")

if __name__ == "__main__":
    main()
