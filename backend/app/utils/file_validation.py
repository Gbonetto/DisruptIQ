"""
File Validation Utilities
Strict MIME type and content validation for uploaded files
"""

import structlog
from typing import Tuple, Optional
import mimetypes
from pathlib import Path

logger = structlog.get_logger()

# Whitelist of allowed MIME types (SECURITY: explicit whitelist)
ALLOWED_MIME_TYPES = {
    # Documents
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/msword",  # .doc
    "text/plain",
    # Images
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
    "image/bmp",
    "image/gif",
    "image/webp",
}

# Mapping of MIME types to allowed extensions
MIME_TO_EXTENSIONS = {
    "application/pdf": [".pdf"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    "application/msword": [".doc"],
    "text/plain": [".txt"],
    "image/png": [".png"],
    "image/jpeg": [".jpg", ".jpeg"],
    "image/jpg": [".jpg", ".jpeg"],
    "image/tiff": [".tiff", ".tif"],
    "image/bmp": [".bmp"],
    "image/gif": [".gif"],
    "image/webp": [".webp"],
}

# Maximum file sizes per type (in bytes)
MAX_FILE_SIZES = {
    "application/pdf": 25 * 1024 * 1024,  # 25 MB for PDFs
    "image/png": 10 * 1024 * 1024,  # 10 MB for images
    "image/jpeg": 10 * 1024 * 1024,
    "image/jpg": 10 * 1024 * 1024,
    "image/tiff": 15 * 1024 * 1024,  # TIFF can be larger
    "image/bmp": 10 * 1024 * 1024,
    "image/gif": 5 * 1024 * 1024,
    "image/webp": 10 * 1024 * 1024,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": 10 * 1024 * 1024,
    "application/msword": 10 * 1024 * 1024,
    "text/plain": 5 * 1024 * 1024,
}

# Default max size if not specified
DEFAULT_MAX_SIZE = 10 * 1024 * 1024  # 10 MB


def validate_mime_type(content_type: str) -> bool:
    """
    Validate that content_type is in the allowed whitelist

    Args:
        content_type: MIME type from uploaded file

    Returns:
        True if allowed, False otherwise
    """
    # Normalize (some browsers send "image/jpg" instead of "image/jpeg")
    content_type = content_type.lower().strip()

    return content_type in ALLOWED_MIME_TYPES


def validate_file_extension(filename: str, content_type: str) -> bool:
    """
    Validate that file extension matches the declared MIME type

    Security: Prevents MIME type spoofing (e.g., .exe renamed to .pdf)

    Args:
        filename: Original filename
        content_type: Declared MIME type

    Returns:
        True if extension matches MIME type, False otherwise
    """
    extension = Path(filename).suffix.lower()

    if not extension:
        logger.warning("file_no_extension", filename=filename)
        return False

    # Check if this MIME type has allowed extensions
    if content_type not in MIME_TO_EXTENSIONS:
        logger.warning(
            "mime_type_no_extensions",
            content_type=content_type,
            filename=filename
        )
        return False

    allowed_extensions = MIME_TO_EXTENSIONS[content_type]

    if extension not in allowed_extensions:
        logger.warning(
            "extension_mime_mismatch",
            filename=filename,
            extension=extension,
            content_type=content_type,
            allowed_extensions=allowed_extensions
        )
        return False

    return True


def validate_file_size(file_size: int, content_type: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that file size is within allowed limits for its type

    Args:
        file_size: Size of file in bytes
        content_type: MIME type

    Returns:
        Tuple of (is_valid, error_message)
    """
    max_size = MAX_FILE_SIZES.get(content_type, DEFAULT_MAX_SIZE)

    if file_size > max_size:
        max_size_mb = max_size / 1024 / 1024
        actual_size_mb = file_size / 1024 / 1024
        error_msg = (
            f"File too large: {actual_size_mb:.2f} MB. "
            f"Maximum allowed for {content_type}: {max_size_mb:.2f} MB"
        )
        logger.warning(
            "file_size_exceeded",
            file_size=file_size,
            max_size=max_size,
            content_type=content_type
        )
        return False, error_msg

    return True, None


def validate_file_content(file_content: bytes, declared_mime: str, filename: str) -> Tuple[bool, Optional[str]]:
    """
    Validate file content matches declared MIME type

    Uses magic bytes detection to prevent MIME type spoofing

    Note: Requires python-magic library
    Try to use it if available, but fallback gracefully

    Args:
        file_content: Raw file bytes
        declared_mime: MIME type declared by client
        filename: Original filename

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        import magic

        # Detect actual MIME type from file content
        detected_mime = magic.from_buffer(file_content, mime=True)

        logger.info(
            "mime_detection",
            filename=filename,
            declared_mime=declared_mime,
            detected_mime=detected_mime
        )

        # Normalize MIME types (some variations are acceptable)
        normalized_declared = declared_mime.lower().strip()
        normalized_detected = detected_mime.lower().strip()

        # Special cases: some MIME types have acceptable variations
        mime_variations = {
            "image/jpg": "image/jpeg",
            "image/jpeg": "image/jpeg",
            "text/x-c": "text/plain",
            "text/x-python": "text/plain",
        }

        normalized_declared = mime_variations.get(normalized_declared, normalized_declared)
        normalized_detected = mime_variations.get(normalized_detected, normalized_detected)

        # Check if detected MIME matches declared
        if normalized_detected != normalized_declared:
            error_msg = (
                f"MIME type mismatch: file content is '{detected_mime}' "
                f"but declared as '{declared_mime}'. Possible file tampering."
            )
            logger.warning(
                "mime_type_mismatch",
                filename=filename,
                declared_mime=declared_mime,
                detected_mime=detected_mime
            )
            return False, error_msg

        return True, None

    except ImportError:
        # python-magic not installed, skip content validation
        logger.warning(
            "python_magic_not_available",
            message="Install python-magic for enhanced MIME validation: pip install python-magic"
        )
        return True, None  # Fallback: allow upload if python-magic not available

    except Exception as e:
        logger.error(
            "mime_validation_error",
            filename=filename,
            error=str(e)
        )
        # On error, be permissive but log
        return True, None


def validate_upload(
    filename: str,
    content_type: str,
    file_content: bytes
) -> Tuple[bool, Optional[str]]:
    """
    Complete upload validation pipeline

    Validates:
    1. MIME type is in whitelist
    2. File extension matches MIME type
    3. File size is within limits
    4. File content matches declared MIME (if python-magic available)

    Args:
        filename: Original filename
        content_type: Declared MIME type
        file_content: Raw file bytes

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Step 1: Validate MIME type whitelist
    if not validate_mime_type(content_type):
        return False, f"File type not allowed: {content_type}"

    # Step 2: Validate extension matches MIME
    if not validate_file_extension(filename, content_type):
        return False, f"File extension does not match MIME type: {content_type}"

    # Step 3: Validate file size
    size_valid, size_error = validate_file_size(len(file_content), content_type)
    if not size_valid:
        return False, size_error

    # Step 4: Validate content (magic bytes)
    content_valid, content_error = validate_file_content(file_content, content_type, filename)
    if not content_valid:
        return False, content_error

    # All validations passed
    logger.info(
        "file_validation_passed",
        filename=filename,
        content_type=content_type,
        size=len(file_content)
    )

    return True, None
