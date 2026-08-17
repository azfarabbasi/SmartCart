import base64
import io
import os
import uuid

from PIL import Image, ImageOps

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass

IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'heic', 'heif', 'bmp', 'tiff', 'hpec'}
VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov'}

MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20MB raw upload allowance (optimized before saving)
MAX_VIDEO_BYTES = 50 * 1024 * 1024  # 50MB

_IMAGE_SIGNATURES = (
    (b'\x89PNG\r\n\x1a\n', 'png'),
    (b'\xff\xd8\xff', 'jpg'),
    (b'\xff\xd8\xff', 'jpeg'),
    (b'\xff\xd8\xff', 'hpec'),
    (b'GIF87a', 'gif'),
    (b'GIF89a', 'gif'),
    (b'RIFF', 'webp'),
    (b'BM', 'bmp'),
)


def _extension(filename):
    if not filename or '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[1].lower()


def _sniff_ok(header, ext, kind):
    if kind == 'image':
        if ext in ('heic', 'heif', 'hpec'):
            # HEIF/HEIC ISO-BMFF: bytes 4-8 usually contain 'ftyp'
            return (len(header) >= 8 and header[4:8] == b'ftyp') or len(header) > 0
        matching_sig = [sig for sig, sig_ext in _IMAGE_SIGNATURES if sig_ext == ext]
        if matching_sig:
            return any(header.startswith(sig) for sig in matching_sig)
        return True
    # video
    if ext == 'webm':
        return header.startswith(b'\x1a\x45\xdf\xa3')
    if ext in ('mp4', 'mov'):
        return len(header) >= 8 and header[4:8] == b'ftyp'
    return False


def convert_image_to_base64(raw_bytes, ext='jpg', max_dimension=1400, quality=85):
    """Convert raw image bytes (JPG, JPEG, PNG, HEIC, HEIF, WEBP, etc.) to an optimized Base64 data URL."""
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        # Handle color modes
        has_alpha = False
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGBA')
            has_alpha = True
        elif img.mode in ('CMYK', 'P', '1', 'L'):
            img = img.convert('RGB')
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Resize if dimensions exceed max_dimension
        w, h = img.size
        if w > max_dimension or h > max_dimension:
            if w > h:
                new_w = max_dimension
                new_h = max(1, int(h * (max_dimension / w)))
            else:
                new_h = max_dimension
                new_w = max(1, int(w * (max_dimension / h)))
            resample_filter = getattr(Image, 'Resampling', Image).LANCZOS
            img = img.resize((new_w, new_h), resample=resample_filter)

        out_buf = io.BytesIO()
        if has_alpha:
            img.save(out_buf, format='WEBP', quality=quality, method=4)
            mime = 'image/webp'
        else:
            img.save(out_buf, format='JPEG', quality=quality, optimize=True)
            mime = 'image/jpeg'

        b64_str = base64.b64encode(out_buf.getvalue()).decode('utf-8')
        return f"data:{mime};base64,{b64_str}"
    except Exception:
        # Fallback to direct raw base64 encoding if Pillow fails
        mime_map = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'hpec': 'image/jpeg',
            'webp': 'image/webp',
            'gif': 'image/gif',
            'heic': 'image/heic',
            'heif': 'image/heif',
            'bmp': 'image/bmp',
        }
        mime = mime_map.get(ext.lower(), 'image/jpeg')
        b64_str = base64.b64encode(raw_bytes).decode('utf-8')
        return f"data:{mime};base64,{b64_str}"


def validate_upload(file_storage, allow_video=False):
    """Validate an uploaded werkzeug FileStorage."""
    filename = file_storage.filename or ''
    ext = _extension(filename)

    if ext in IMAGE_EXTENSIONS:
        kind = 'image'
        max_bytes = MAX_IMAGE_BYTES
    elif allow_video and ext in VIDEO_EXTENSIONS:
        kind = 'video'
        max_bytes = MAX_VIDEO_BYTES
    else:
        allowed = sorted(IMAGE_EXTENSIONS | (VIDEO_EXTENSIONS if allow_video else set()))
        return False, f"Unsupported file type. Allowed: {', '.join(allowed)}", None, None

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size == 0:
        return False, 'The uploaded file is empty.', None, None
    if size > max_bytes:
        limit_mb = max_bytes // (1024 * 1024)
        return False, f'File too large. Maximum allowed is {limit_mb}MB for {kind}s.', None, None

    header = file_storage.stream.read(16)
    file_storage.stream.seek(0)
    if not _sniff_ok(header, ext, kind):
        return False, 'File content does not match its extension.', None, None

    safe_filename = f'{uuid.uuid4().hex}.{ext}'
    return True, None, safe_filename, kind


def process_upload(file_storage, allow_video=False, max_dimension=1400, quality=85):
    """Validate and convert an uploaded file into a Base64 data URL.

    Returns (ok: bool, error: str|None, data_url: str|None, kind: str|None).
    """
    ok, err, safe_filename, kind = validate_upload(file_storage, allow_video=allow_video)
    if not ok:
        return False, err, None, None

    file_storage.stream.seek(0)
    raw_bytes = file_storage.stream.read()
    ext = _extension(file_storage.filename or '')

    if kind == 'image':
        data_url = convert_image_to_base64(raw_bytes, ext=ext, max_dimension=max_dimension, quality=quality)
        return True, None, data_url, 'image'

    if kind == 'video':
        # Videos can be encoded to base64 data url for direct embedding
        mime_map = {'mp4': 'video/mp4', 'webm': 'video/webm', 'mov': 'video/quicktime'}
        mime = mime_map.get(ext.lower(), 'video/mp4')
        b64_str = base64.b64encode(raw_bytes).decode('utf-8')
        data_url = f"data:{mime};base64,{b64_str}"
        return True, None, data_url, 'video'

    return False, 'Unsupported media type.', None, None


def save_upload(file_storage, folder, safe_filename):
    """Legacy helper: saves file to disk."""
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, safe_filename)
    file_storage.save(dest)
    return dest
