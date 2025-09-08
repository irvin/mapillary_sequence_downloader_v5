import requests, json, os
from PIL import Image
import piexif
from io import BytesIO
import time
from datetime import datetime
import logging

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

    # Add compass angle if available (using computed_compass_angle for GPSImgDirection as it's more accurate)
    if image_metadata and image_metadata.get('computed_compass_angle'):
        computed_compass_angle = image_metadata['computed_compass_angle']
        gps_ifd[piexif.GPSIFD.GPSImgDirection] = (int(computed_compass_angle * 100), 100)
        gps_ifd[piexif.GPSIFD.GPSImgDirectionRef] = 'T'  # True direction

    # Add original compass angle as additional info (not used for main direction)
    # if image_metadata and image_metadata.get('compass_angle'):
    #     compass_angle = image_metadata['compass_angle']
    #     gps_ifd[piexif.GPSIFD.GPSDestBearing] = (int(compass_angle * 100), 100)
    #     gps_ifd[piexif.GPSIFD.GPSDestBearingRef] = 'T'  # True direction

    # Only add altitude information if available
    if altitude is not None:
        gps_ifd[piexif.GPSIFD.GPSAltitudeRef] = 0  # Above sea level
        gps_ifd[piexif.GPSIFD.GPSAltitude] = (altitude, 100)

    # Basic image information - only use if available from metadata
    camera_make = None
    camera_model = None

    if image_metadata:
        camera_make = image_metadata.get('camera_make')
        camera_model = image_metadata.get('camera_model')

    # Get image dimensions - only use if available from metadata
    image_width = None
    image_height = None
    if image_metadata:
        image_width = image_metadata.get('width')
        image_height = image_metadata.get('height')

    # Determine image orientation based on dimensions
    # 1 = normal, 3 = 180°, 6 = 90° clockwise, 8 = 90° counter-clockwise
    orientation = 1  # default normal orientation
    if image_width and image_height and image_width > 0 and image_height > 0:
        if image_width > image_height:
            orientation = 1  # landscape
        else:
            orientation = 6  # portrait (90° clockwise)

    # Use standard DPI for digital images (72 DPI is the standard for digital cameras)
    dpi = 72

    zeroth_ifd = {
        piexif.ImageIFD.Software: 'Mapillary Sequence Downloader v5',
        piexif.ImageIFD.DateTime: capture_time.strftime('%Y:%m:%d %H:%M:%S'),
        piexif.ImageIFD.XResolution: (dpi, 1),
        piexif.ImageIFD.YResolution: (dpi, 1),
        piexif.ImageIFD.ResolutionUnit: 2,  # Inches
        piexif.ImageIFD.Orientation: orientation,
    }

    # Only add camera information if available from metadata
    if camera_make:
        zeroth_ifd[piexif.ImageIFD.Make] = camera_make
    if camera_model:
        zeroth_ifd[piexif.ImageIFD.Model] = camera_model

    # Camera information (with microsecond precision)
    exif_ifd = {
        piexif.ExifIFD.DateTimeOriginal: capture_time.strftime('%Y:%m:%d %H:%M:%S.%f')[:-3],  # Keep milliseconds
        piexif.ExifIFD.DateTimeDigitized: capture_time.strftime('%Y:%m:%d %H:%M:%S.%f')[:-3],  # Keep milliseconds
    }

    # Add camera settings if available from metadata
    if image_metadata:
        # Add focal length if available
        if image_metadata.get('focal_length'):
            exif_ifd[piexif.ExifIFD.FocalLength] = (int(image_metadata['focal_length'] * 100), 100)

        # Calculate focal length from camera_parameters if available
        elif image_metadata.get('camera_parameters') and image_width and image_height:
            # camera_parameters[0] is focal length in relative units
            # Convert to pixels: focal_length_pixels = relative_focal_length * max(width, height)
            relative_focal_length = image_metadata['camera_parameters'][0]
            focal_length_pixels = relative_focal_length * max(image_width, image_height)
            # Convert to mm (assuming 35mm equivalent sensor)
            # This is an approximation - actual conversion depends on sensor size
            focal_length_mm = focal_length_pixels * 0.036  # 36mm sensor width approximation
            exif_ifd[piexif.ExifIFD.FocalLength] = (int(focal_length_mm * 100), 100)

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
    if image_width and image_height and image_width > 0 and image_height > 0:
        exif_ifd[piexif.ExifIFD.PixelXDimension] = image_width
        exif_ifd[piexif.ExifIFD.PixelYDimension] = image_height
        # Also add to zeroth IFD for better compatibility
        zeroth_ifd[piexif.ImageIFD.ImageWidth] = image_width
        zeroth_ifd[piexif.ImageIFD.ImageLength] = image_height

    # Add Mapillary-specific information to UserComment (only data without standard EXIF fields)
    mapillary_info = f"Mapillary Image ID: {image_id}"
    if sequence_id:
        mapillary_info += f" | Sequence: {sequence_id}"
    if image_metadata and image_metadata.get('creator_username'):
        mapillary_info += f" | Creator: {image_metadata['creator_username']}"
    if image_metadata and image_metadata.get('camera_type'):
        mapillary_info += f" | Camera Type: {image_metadata['camera_type']}"
    if image_metadata and image_metadata.get('atomic_scale'):
        mapillary_info += f" | Atomic Scale: {image_metadata['atomic_scale']}"
    if image_metadata and image_metadata.get('camera_parameters'):
        params = image_metadata['camera_parameters']
        # Only include principal point parameters (not focal length as it's now in EXIF)
        mapillary_info += f" | Principal Point: [{params[1]:.3f}, {params[2]:.3f}]"
    if image_metadata and image_metadata.get('mesh'):
        mapillary_info += f" | Mesh ID: {image_metadata['mesh']['id']}"
    if image_metadata and image_metadata.get('sfm_cluster'):
        mapillary_info += f" | SfM Cluster: {image_metadata['sfm_cluster']['id']}"
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

def main(sequence_id, quality=None):
    """
    Main function to download all images in a sequence

    Args:
        sequence_id (str): Sequence ID to download
        quality (int, optional): JPEG quality (1-100). If None, saves original quality
    """
    # Get access_token from config file
    try:
        from config import access_token
    except ImportError:
        logger.error("❌ config.py file not found!")
        logger.error("Please create config.py file and set your access_token")
        logger.error("You can copy config.example.py to config.py as a template")
        exit(1)

    if not access_token:
        logger.error("access_token is required in config.py")
        exit(1)

    if not sequence_id:
        logger.error("sequence_id is required")
        exit(1)

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

    # Determine output directory name based on first image's timestamp
    output_dir = None
    first_image_timestamp = None

    # Process each image and download
    for i, img_id in enumerate(image_ids, 1):
        try:
            logger.info(f"Processing image {i}/{len(image_ids)}: {img_id['id']}")

            # Get comprehensive image information with additional fields
            fields = [
                'thumb_original_url', 'geometry', 'captured_at', 'compass_angle', 'camera_type',
                'computed_altitude', 'computed_compass_angle', 'sequence', 'camera_parameters',
                'atomic_scale', 'computed_geometry', 'mesh', 'sfm_cluster'
            ]
            image_url = f"https://graph.mapillary.com/{img_id['id']}?fields={','.join(fields)}"
            img_r = requests.get(image_url, headers=header, timeout=30)
            img_r.raise_for_status()
            img_data = img_r.json()

            # Set output directory name based on first image's timestamp
            if output_dir is None:
                if 'captured_at' in img_data and img_data['captured_at']:
                    timestamp_sec = img_data['captured_at'] / 1000.0
                    first_image_timestamp = datetime.fromtimestamp(timestamp_sec)
                    # Create folder name with date and time
                    folder_name = f"{first_image_timestamp.strftime('%Y%m%d_%H%M%S')}_{sequence_id[:8]}"
                else:
                    # Fallback to sequence ID if no timestamp
                    folder_name = sequence_id
                output_dir = f"downloads/{folder_name}"
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                    logger.info(f"Created output directory: {output_dir}")

            # Download image
            image_get_url = img_data['thumb_original_url']
            logger.info(f"Downloading image...")
            image_data = download_image_with_retry(image_get_url)

            # Process image and add EXIF data
            image = Image.open(BytesIO(image_data))

            # Get actual image dimensions from the downloaded image
            actual_width, actual_height = image.size
            logger.info(f"Image dimensions: {actual_width}x{actual_height}")

            # Update image metadata with actual dimensions
            img_data['width'] = actual_width
            img_data['height'] = actual_height

            # Use computed_geometry if available (more accurate), otherwise use geometry
            if 'computed_geometry' in img_data and img_data['computed_geometry']:
                coords = img_data['computed_geometry']['coordinates']
                logger.info("Using computed_geometry for more accurate GPS coordinates")
            else:
                coords = img_data['geometry']['coordinates']
                logger.info("Using standard geometry for GPS coordinates")

            # Add comprehensive GPS EXIF data
            exif_bytes = add_gps_exif_data(
                coords[1],  # latitude
                coords[0],  # longitude
                img_id['id'],
                sequence_id,
                img_data  # Pass all image metadata
            )

            # Generate filename based on capture time
            if 'captured_at' in img_data and img_data['captured_at']:
                timestamp_sec = img_data['captured_at'] / 1000.0
                capture_time = datetime.fromtimestamp(timestamp_sec)
                filename = f"{capture_time.strftime('%Y%m%d_%H%M%S')}_{capture_time.strftime('%f')[:3]}.jpg"
            else:
                filename = f"{img_id['id']}.jpg"

            # Save image
            output_path = f"{output_dir}/{filename}"
            if exif_bytes:
                if quality is not None:
                    image.save(output_path, exif=exif_bytes, quality=quality)
                    logger.info(f"✅ Image saved with GPS EXIF data (quality {quality}): {output_path}")
                else:
                    image.save(output_path, exif=exif_bytes)
                    logger.info(f"✅ Image saved with GPS EXIF data (original quality): {output_path}")
            else:
                if quality is not None:
                    image.save(output_path, quality=quality)
                    logger.info(f"✅ Image saved (quality {quality}): {output_path}")
                else:
                    image.save(output_path)
                    logger.info(f"✅ Image saved (original quality): {output_path}")

            # Add delay to avoid rate limiting
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"❌ Error processing image {img_id['id']}: {e}")
            continue

    logger.info("🎉 Download completed!")

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='Download Mapillary sequence images with EXIF data')
    parser.add_argument('sequence_id', help='Sequence ID to download')
    parser.add_argument('-q', '--quality', type=int, choices=range(1, 101),
                       help='JPEG quality (1-100). If not specified, saves original quality')

    args = parser.parse_args()
    main(args.sequence_id, args.quality)
