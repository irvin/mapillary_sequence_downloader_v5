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

def add_gps_exif_data(latitude, longitude, image_id, sequence_id=None, image_metadata=None):
    """
    Add comprehensive GPS and EXIF data to image
    """
    def convert_to_degrees(value):
        d = int(value)
        m = int((value - d) * 60)
        s = (value - d - m/60) * 3600
        return d, m, s

    lat_deg = convert_to_degrees(latitude)
    lon_deg = convert_to_degrees(longitude)

    # GPS information - only use if available from metadata
    altitude = None
    if image_metadata and image_metadata.get('alt'):
        altitude = int(image_metadata['alt'] * 100)
    elif image_metadata and image_metadata.get('computed_alt'):
        altitude = int(image_metadata['computed_alt'] * 100)
    elif image_metadata and image_metadata.get('computed_altitude'):
        altitude = int(image_metadata['computed_altitude'] * 100)

    # Use captured_at timestamp if available
    capture_time = datetime.now()
    if image_metadata and image_metadata.get('captured_at'):
        capture_time = datetime.fromtimestamp(image_metadata['captured_at'] / 1000)

    # Convert to UTC for GPS timestamp
    gps_time = capture_time.utctimetuple()

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: 'N' if latitude >= 0 else 'S',
        piexif.GPSIFD.GPSLatitude: [(lat_deg[0], 1), (lat_deg[1], 1), (int(lat_deg[2]*100), 100)],
        piexif.GPSIFD.GPSLongitudeRef: 'E' if longitude >= 0 else 'W',
        piexif.GPSIFD.GPSLongitude: [(lon_deg[0], 1), (lon_deg[1], 1), (int(lon_deg[2]*100), 100)],
        piexif.GPSIFD.GPSTimeStamp: [(gps_time.tm_hour, 1), (gps_time.tm_min, 1), (gps_time.tm_sec, 1)],
        piexif.GPSIFD.GPSDateStamp: capture_time.strftime('%Y:%m:%d')
    }

    # Only add altitude information if available
    if altitude is not None:
        gps_ifd[piexif.GPSIFD.GPSAltitudeRef] = 0  # Above sea level
        gps_ifd[piexif.GPSIFD.GPSAltitude] = (altitude, 100)

    # Basic image information
    camera_make = 'Unknown'
    camera_model = 'Unknown'

    if image_metadata:
        camera_make = image_metadata.get('camera_make', camera_make)
        camera_model = image_metadata.get('camera_model', camera_model)

    # Get image dimensions
    image_width = 0
    image_height = 0
    if image_metadata:
        image_width = image_metadata.get('width', 0)
        image_height = image_metadata.get('height', 0)

    # Determine image orientation based on dimensions
    # 1 = normal, 3 = 180°, 6 = 90° clockwise, 8 = 90° counter-clockwise
    orientation = 1  # default normal orientation
    if image_width > 0 and image_height > 0:
        if image_width > image_height:
            orientation = 1  # landscape
        else:
            orientation = 6  # portrait (90° clockwise)

    # Use standard DPI for digital images (72 DPI is the standard for digital cameras)
    dpi = 72

    zeroth_ifd = {
        piexif.ImageIFD.Make: camera_make,
        piexif.ImageIFD.Model: camera_model,
        piexif.ImageIFD.Software: 'Mapillary Sequence Downloader v4',
        piexif.ImageIFD.DateTime: capture_time.strftime('%Y:%m:%d %H:%M:%S'),
        piexif.ImageIFD.XResolution: (dpi, 1),
        piexif.ImageIFD.YResolution: (dpi, 1),
        piexif.ImageIFD.ResolutionUnit: 2,  # Inches
        piexif.ImageIFD.Orientation: orientation,
    }

    # Camera information
    exif_ifd = {
        piexif.ExifIFD.DateTimeOriginal: capture_time.strftime('%Y:%m:%d %H:%M:%S'),
        piexif.ExifIFD.DateTimeDigitized: capture_time.strftime('%Y:%m:%d %H:%M:%S'),
    }

    # Add camera settings if available from metadata
    if image_metadata:
        # Add focal length if available
        if image_metadata.get('focal_length'):
            exif_ifd[piexif.ExifIFD.FocalLength] = (int(image_metadata['focal_length'] * 100), 100)

        # Add ISO if available
        if image_metadata.get('iso'):
            exif_ifd[piexif.ExifIFD.ISOSpeedRatings] = image_metadata['iso']

        # Add exposure time if available
        if image_metadata.get('exposure_time'):
            exif_ifd[piexif.ExifIFD.ExposureTime] = (int(image_metadata['exposure_time'] * 1000000), 1000000)

        # Add aperture if available
        if image_metadata.get('aperture'):
            exif_ifd[piexif.ExifIFD.FNumber] = (int(image_metadata['aperture'] * 100), 100)

    # Add image dimensions if available
    if image_width > 0 and image_height > 0:
        exif_ifd[piexif.ExifIFD.PixelXDimension] = image_width
        exif_ifd[piexif.ExifIFD.PixelYDimension] = image_height
        # Also add to zeroth IFD for better compatibility
        zeroth_ifd[piexif.ImageIFD.ImageWidth] = image_width
        zeroth_ifd[piexif.ImageIFD.ImageLength] = image_height

    # Add comprehensive Mapillary information to UserComment
    mapillary_info = f"Mapillary Image ID: {image_id}"
    if sequence_id:
        mapillary_info += f" | Sequence: {sequence_id}"
    if image_metadata and image_metadata.get('creator_username'):
        mapillary_info += f" | Creator: {image_metadata['creator_username']}"
    if image_metadata and image_metadata.get('camera_type'):
        mapillary_info += f" | Camera Type: {image_metadata['camera_type']}"
    if image_metadata and image_metadata.get('compass_angle'):
        mapillary_info += f" | Compass: {image_metadata['compass_angle']}°"
    if image_metadata and image_metadata.get('computed_compass_angle'):
        mapillary_info += f" | Computed Compass: {image_metadata['computed_compass_angle']}°"
    if image_metadata and image_metadata.get('computed_altitude'):
        mapillary_info += f" | Computed Alt: {image_metadata['computed_altitude']}m"
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

            # Get basic image information with minimal fields to avoid 500 errors
            fields = [
                'thumb_original_url', 'geometry', 'captured_at', 'compass_angle', 'camera_type', 'computed_altitude', 'computed_compass_angle', 'sequence'
            ]
            image_url = f"https://graph.mapillary.com/{img_id['id']}?fields={','.join(fields)}"
            img_r = requests.get(image_url, headers=header, timeout=30)
            img_r.raise_for_status()
            img_data = img_r.json()

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

            # Get actual image dimensions from the downloaded image
            actual_width, actual_height = image.size
            logger.info(f"Image dimensions: {actual_width}x{actual_height}")

            # Update image metadata with actual dimensions
            img_data['width'] = actual_width
            img_data['height'] = actual_height

            # Add comprehensive GPS EXIF data
            exif_bytes = add_gps_exif_data(
                img_data['geometry']['coordinates'][1],  # latitude
                img_data['geometry']['coordinates'][0],  # longitude
                img_id['id'],
                sequence_id,
                img_data  # Pass all image metadata
            )

            # Save image
            output_path = f"{output_dir}/{img_id['id']}.jpg"
            if exif_bytes:
                image.save(output_path, exif=exif_bytes, quality=95)
                logger.info(f"✅ Image saved with GPS EXIF data: {output_path}")
            else:
                image.save(output_path, quality=95)
                logger.info(f"✅ Image saved (no EXIF data): {output_path}")

            # Add delay to avoid rate limiting
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"❌ Error processing image {img_id['id']}: {e}")
            continue

    logger.info("🎉 Download completed!")

if __name__ == "__main__":
    main()
