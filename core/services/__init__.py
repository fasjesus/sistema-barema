try:
    from .pdf_service import PDFService
except ImportError:
    PDFService = None

try:
    from .notification_service import NotificationService
except ImportError:
    NotificationService = None

try:
    from .certificate_service import CertificateProcessor
except ImportError:
    CertificateProcessor = None

from .validation_processor import (
    ActivityRule,
    ActivityValidationResult,
    BasicCertificatePreValidator,
    CertificateDataExtractor,
    CertificateValidationProcessor,
    CertificateValidationResult,
    ExtractedCertificateData,
    StudentContext,
)
