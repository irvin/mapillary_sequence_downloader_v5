import requests, json, os
from PIL import Image
import piexif
from io import BytesIO
import time
from datetime import datetime, timezone, timedelta
import logging

# Setup logging
def setup_logging(sequence_id):
    """Setup logging to both console and file"""
    # Create logs directory
    if not os.path.exists("logs"):
        os.makedirs("logs")

    # Generate log filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f"logs/sequence_{sequence_id}_{timestamp}.log"

    # Setup log format
    log_format = '%(asctime)s - %(levelname)s - %(message)s'

    # Clear existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()  # Also output to console
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Starting download for sequence {sequence_id}")
    logger.info(f"Log file: {log_filename}")
    return logger, log_filename

logger = None  # Will be initialized in main function


def add_gps_exif_data(latitude, longitude, image_id, sequence_id=None, image_metadata=None):
    """
    Add comprehensive GPS and EXIF data to image
    """
    def convert_to_degrees(value):
        d = int(value)
        m = int((value - d) * 60)
        s = (value - d - m/60) * 3600
        return d, m, s

    lat_deg = convert_to_degrees(abs(latitude))
    lon_deg = convert_to_degrees(abs(longitude))

    # GPS information - only use original data, avoid computed values
    altitude = None
    # Only use original alt, remove all computed_* altitude fields
    if image_metadata and image_metadata.get('alt'):
        altitude = max(0, int(image_metadata['alt'] * 100))  # Ensure non-negative

    # Use captured_at timestamp if available
    capture_time = datetime.now()

    if image_metadata and image_metadata.get('captured_at'):
        # Log original captured_at value for debugging
        original_captured_at = image_metadata['captured_at']
        logger.info(f"🔍 DEBUG - Original captured_at: {original_captured_at} (type: {type(original_captured_at)})")

        # Try to infer timezone from GPS coordinates
        if latitude and longitude:
            try:
                # Simple timezone inference based on longitude
                # This is a rough approximation - in practice you'd use a proper timezone library
                tz_offset = int(longitude / 15)  # Rough timezone calculation
                logger.info(f"🔍 DEBUG - GPS coordinates: lat={latitude}, lon={longitude}")
                logger.info(f"🔍 DEBUG - Calculated timezone offset: {tz_offset} hours")
                logger.info(f"Inferred timezone offset from GPS: UTC{tz_offset:+d}")
            except Exception as e:
                tz_offset = 0
                logger.warning(f"Could not infer timezone from GPS: {e}, using UTC")
        else:
            tz_offset = 0
            logger.warning("No GPS coordinates available, using UTC")

        # Convert timestamp to seconds and log
        timestamp_sec = original_captured_at / 1000.0
        logger.info(f"🔍 DEBUG - Timestamp in seconds: {timestamp_sec}")
        logger.info(f"🔍 DEBUG - Unix timestamp: {int(timestamp_sec)}")

        # Mapillary timestamp is in local timezone, use local time for EXIF DateTime tags
        if tz_offset != 0:
            tz = timezone(timedelta(hours=tz_offset))
            capture_time = datetime.fromtimestamp(timestamp_sec, tz=tz)  # Use local time for EXIF
            capture_time_utc = capture_time.astimezone(timezone.utc)  # Keep UTC for GPS timestamp
            logger.info(f"🔍 DEBUG - Local timezone: {tz}")
            logger.info(f"🔍 DEBUG - Local time (for EXIF): {capture_time}")
            logger.info(f"🔍 DEBUG - UTC time (for GPS): {capture_time_utc}")
            logger.info(f"Mapillary local time: {capture_time.strftime('%Y-%m-%d %H:%M:%S %Z')} -> UTC: {capture_time_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        else:
            # Assume UTC if no timezone info
            capture_time = datetime.fromtimestamp(timestamp_sec, tz=timezone.utc)
            capture_time_utc = capture_time
            logger.info(f"🔍 DEBUG - Using UTC timezone (no GPS timezone inference)")
            logger.info(f"🔍 DEBUG - UTC time: {capture_time}")
            logger.info(f"Mapillary timestamp (UTC): {capture_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Convert to UTC for GPS timestamp (keep original EXIF behavior)
    gps_time = capture_time_utc.utctimetuple()

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: 'N' if latitude >= 0 else 'S',
        piexif.GPSIFD.GPSLatitude: [(lat_deg[0], 1), (lat_deg[1], 1), (int(lat_deg[2]*100), 100)],
        piexif.GPSIFD.GPSLongitudeRef: 'E' if longitude >= 0 else 'W',
        piexif.GPSIFD.GPSLongitude: [(lon_deg[0], 1), (lon_deg[1], 1), (int(lon_deg[2]*100), 100)],
        piexif.GPSIFD.GPSTimeStamp: [(gps_time.tm_hour, 1), (gps_time.tm_min, 1), (gps_time.tm_sec, 1)],
        piexif.GPSIFD.GPSDateStamp: capture_time_utc.strftime('%Y:%m:%d')
    }

    # Only use original compass angle, avoid computed values
    if image_metadata and image_metadata.get('compass_angle'):
        compass_angle = image_metadata['compass_angle']
        gps_ifd[piexif.GPSIFD.GPSImgDirection] = (int(compass_angle * 100), 100)
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

    # Add timezone offset information (EXIF 2.31)
    if image_metadata and image_metadata.get('captured_at') and latitude and longitude:
        try:
            # Calculate timezone offset from GPS coordinates
            tz_offset = int(longitude / 15)  # Rough timezone calculation
            if tz_offset != 0:
                # Format timezone offset as +HH:MM or -HH:MM
                offset_hours = abs(tz_offset)
                offset_str = f"{'+' if tz_offset >= 0 else '-'}{offset_hours:02d}:00"
                logger.info(f"🔍 DEBUG - Adding timezone offset tags: {offset_str}")

                # Add timezone offset tags (EXIF 2.31)
                # Note: These tags might not be available in older piexif versions
                try:
                    exif_ifd[0x9010] = offset_str  # OffsetTime
                    exif_ifd[0x9011] = offset_str  # OffsetTimeOriginal
                    exif_ifd[0x9012] = offset_str  # OffsetTimeDigitized
                    logger.info(f"🔍 DEBUG - Timezone offset tags added: {offset_str}")
                except Exception as tag_error:
                    logger.warning(f"Timezone offset tags not supported in this piexif version: {tag_error}")
        except Exception as e:
            logger.warning(f"Failed to add timezone offset tags: {e}")

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
        # Record detailed error information
        error_details = {
            'error_type': type(e).__name__,
            'error_message': str(e),
            'latitude': latitude,
            'longitude': longitude,
            'altitude': altitude,
            'image_id': image_id,
            'exif_dict_keys': list(exif_dict.keys()),
            'gps_ifd_size': len(gps_ifd),
            'zeroth_ifd_size': len(zeroth_ifd),
            'exif_ifd_size': len(exif_ifd)
        }

        logger.warning(f"Failed to create EXIF data for image {image_id}: {e}")
        logger.debug(f"Error details: {error_details}")
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

def main(sequence_id, quality=None, specific_images=None):
    """
    Main function to download all images in a sequence or specific images

    Args:
        sequence_id (str): Sequence ID to download
        quality (int, optional): JPEG quality (1-100). If None, saves original quality
        specific_images (list, optional): List of specific image IDs to download. If None, downloads all images
    """
    global logger

    # Setup logging
    logger, log_filename = setup_logging(sequence_id)

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

    # Set up common header for API requests
    header = {'Authorization': f'OAuth {access_token}'}

    # Get image IDs - either all images in sequence or specific images
    if specific_images:
        logger.info(f"Using specific images list: {len(specific_images)} images")
        image_ids = [{'id': img_id} for img_id in specific_images]
    else:
        logger.info(f"Getting image list for sequence {sequence_id}...")
        url = f"https://graph.mapillary.com/image_ids?sequence_id={sequence_id}"

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

    # Initialize error statistics
    error_count = 0
    error_images = []
    exif_error_count = 0
    exif_error_images = []

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
                    # Determine timezone offset from GPS coordinates
                    tz_offset = 0
                    if 'computed_geometry' in img_data and img_data['computed_geometry']:
                        # Try to infer from GPS coordinates
                        coords = img_data['computed_geometry']['coordinates']
                        if coords and len(coords) >= 2:
                            longitude = coords[0]
                            tz_offset = int(longitude / 15)  # Rough timezone calculation

                    # Mapillary timestamp is in local timezone, keep as local time for folder naming
                    timestamp_sec = img_data['captured_at'] / 1000.0
                    logger.info(f"🔍 DEBUG - Folder naming - Original captured_at: {img_data['captured_at']}")
                    logger.info(f"🔍 DEBUG - Folder naming - Timestamp in seconds: {timestamp_sec}")
                    logger.info(f"🔍 DEBUG - Folder naming - Timezone offset: {tz_offset}")

                    if tz_offset != 0:
                        tz = timezone(timedelta(hours=tz_offset))
                        first_image_timestamp = datetime.fromtimestamp(timestamp_sec, tz=tz)
                        logger.info(f"🔍 DEBUG - Folder naming - Using GPS timezone: {tz}")
                    else:
                        # If no timezone info, use local system timezone
                        first_image_timestamp = datetime.fromtimestamp(timestamp_sec)
                        logger.info(f"🔍 DEBUG - Folder naming - Using system timezone")

                    logger.info(f"🔍 DEBUG - Folder naming - Local timestamp: {first_image_timestamp}")
                    # Create folder name with local date and time
                    folder_name = f"{first_image_timestamp.strftime('%Y%m%d_%H%M%S')}_{sequence_id[:8]}"
                    logger.info(f"🔍 DEBUG - Folder naming - Generated folder name: {folder_name}")
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

            # Force use original geometry coordinates, avoid computed drift issues
            if 'geometry' in img_data and img_data['geometry']:
                coords = img_data['geometry']['coordinates']
                logger.info("Using original geometry coordinates (avoiding computed drift)")
            else:
                logger.error("❌ No available original coordinate information")
                continue

            # Add comprehensive GPS EXIF data
            exif_bytes = add_gps_exif_data(
                coords[1],  # latitude
                coords[0],  # longitude
                img_id['id'],
                sequence_id,
                img_data  # Pass all image metadata
            )

            # Check if EXIF creation was successful
            if exif_bytes is None:
                exif_error_count += 1
                exif_error_images.append({
                    'image_id': img_id['id'],
                    'error_type': 'EXIF creation failed',
                    'coordinates': coords,
                    'metadata_keys': list(img_data.keys())
                })
                logger.warning(f"⚠️  EXIF creation failed for image {img_id['id']}")

            # Generate filename based on capture time (use local time for filename only)
            if 'captured_at' in img_data and img_data['captured_at']:
                # Determine timezone offset from GPS coordinates
                tz_offset = 0
                if 'computed_geometry' in img_data and img_data['computed_geometry']:
                    # Try to infer from GPS coordinates
                    coords = img_data['computed_geometry']['coordinates']
                    if coords and len(coords) >= 2:
                        longitude = coords[0]
                        tz_offset = int(longitude / 15)  # Rough timezone calculation

                # Mapillary timestamp is in local timezone, keep as local time for filename
                timestamp_sec = img_data['captured_at'] / 1000.0
                logger.info(f"🔍 DEBUG - Filename naming - Original captured_at: {img_data['captured_at']}")
                logger.info(f"🔍 DEBUG - Filename naming - Timestamp in seconds: {timestamp_sec}")
                logger.info(f"🔍 DEBUG - Filename naming - Timezone offset: {tz_offset}")

                if tz_offset != 0:
                    tz = timezone(timedelta(hours=tz_offset))
                    capture_time_local = datetime.fromtimestamp(timestamp_sec, tz=tz)
                    logger.info(f"🔍 DEBUG - Filename naming - Using GPS timezone: {tz}")
                else:
                    # If no timezone info, use local system timezone
                    capture_time_local = datetime.fromtimestamp(timestamp_sec)
                    logger.info(f"🔍 DEBUG - Filename naming - Using system timezone")

                logger.info(f"🔍 DEBUG - Filename naming - Local timestamp: {capture_time_local}")
                logger.info(f"🔍 DEBUG - Filename naming - Microseconds: {capture_time_local.strftime('%f')}")
                filename = f"{capture_time_local.strftime('%Y%m%d_%H%M%S')}_{capture_time_local.strftime('%f')[:3]}.jpg"
                logger.info(f"🔍 DEBUG - Filename naming - Generated filename: {filename}")
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
            error_count += 1
            error_images.append({
                'image_id': img_id['id'],
                'error_type': type(e).__name__,
                'error_message': str(e),
                'image_index': i
            })
            logger.error(f"❌ Error processing image {img_id['id']}: {e}")
            continue

    # Output error statistics
    logger.info("=" * 80)
    logger.info("📊 Download Statistics")
    logger.info(f"Total images: {len(image_ids)}")
    logger.info(f"Successfully downloaded: {len(image_ids) - error_count}")
    logger.info(f"Download failed: {error_count}")
    logger.info(f"EXIF creation failed: {exif_error_count}")

    if error_images:
        logger.info("\n❌ Failed downloads:")
        for error in error_images:
            logger.info(f"  - Image {error['image_index']}: {error['image_id']} ({error['error_type']}: {error['error_message']})")

    if exif_error_images:
        logger.info("\n⚠️  EXIF creation failed:")
        for error in exif_error_images:
            logger.info(f"  - {error['image_id']} (coordinates: {error['coordinates']})")

    logger.info("🎉 Download completed!")
    logger.info(f"📄 Detailed log saved to: {log_filename}")

    # Output log file path to console
    print(f"\n📄 Detailed log saved to: {log_filename}")

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='Download Mapillary sequence images with EXIF data')
    parser.add_argument('sequence_id', help='Sequence ID to download')
    parser.add_argument('-q', '--quality', type=int,
                       help='JPEG quality (1-100). If not specified, saves original quality')
    parser.add_argument('-i', '--images', nargs='+',
                       help='Specific image IDs to download (space-separated)')
    parser.add_argument('--image-file',
                       help='File containing image IDs (one per line)')

    args = parser.parse_args()

    # Validate quality parameter
    if args.quality is not None and (args.quality < 1 or args.quality > 100):
        print(f"❌ Quality parameter must be between 1-100, current value: {args.quality}")
        sys.exit(1)

    # Handle specific images
    specific_images = None
    if args.images:
        specific_images = args.images
        print(f"📋 Will download specific images: {len(specific_images)} images")
    elif args.image_file:
        try:
            with open(args.image_file, 'r') as f:
                specific_images = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            print(f"📋 Reading image list from file: {len(specific_images)} images")
        except FileNotFoundError:
            print(f"❌ File not found: {args.image_file}")
            sys.exit(1)

    main(args.sequence_id, args.quality, specific_images)
