import os
import uuid

IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov'}

MAX_IMAGE_BYTES = 5 * 1024 * 1024   # 5MB
MAX_VIDEO_BYTES = 50 * 1024 * 1024  # 50MB

# First-bytes signatures used to sanity-check that the file content actually
# matches the extension it claims (catches a renamed .exe/.txt masquerading
# as an image or video). Not a full format validator, just a fast forgery check.
_IMAGE_SIGNATURES = (
    (b'\x89PNG\r\n\x1a\n', 'png'),
    (b'\xff\xd8\xff', 'jpg'),
    (b'\xff\xd8\xff', 'jpeg'),
    (b'GIF87a', 'gif'),
    (b'GIF89a', 'gif'),
    (b'RIFF', 'webp'),  # WEBP is RIFF....WEBP; RIFF prefix is a good enough check
)
_VIDEO_SIGNATURES = (
    (b'\x1a\x45\xdf\xa3', 'webm'),
    # mp4/mov are ISO-BMFF: bytes 4-8 are "ftyp"; checked separately below
)


def _extension(filename):
    if '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[1].lower()


def _sniff_ok(header, ext, kind):
    if kind == 'image':
        return any(header.startswith(sig) for sig, sig_ext in _IMAGE_SIGNATURES if sig_ext == ext)
    # video
    if ext == 'webm':
        return header.startswith(b'\x1a\x45\xdf\xa3')
    if ext in ('mp4', 'mov'):
        return len(header) >= 8 and header[4:8] == b'ftyp'
    return False


def validate_upload(file_storage, allow_video=False):
    """Validate an uploaded werkzeug FileStorage.

    Returns (ok: bool, error: str|None, safe_filename: str|None, media_type: str|None).
    Never trusts the original filename beyond its extension; always generates a
    fresh uuid4-based filename to avoid collisions and to stop original names
    (which may contain PII or path-like content) reaching disk.
    """
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


def save_upload(file_storage, folder, safe_filename):
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, safe_filename)
    file_storage.save(dest)
    return dest
