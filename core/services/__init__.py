try:
    from .pdf_service import PDFService
except ImportError:
    PDFService = None

try:
    from .notification_service import NotificationService
except ImportError:
    NotificationService = None

try:
    from .analise_barema_service import AnaliseBaremaService
except ImportError:
    AnaliseBaremaService = None

try:
    from .certificate_service import CertificateProcessor
except ImportError:
    CertificateProcessor = None

from .validation_processor import (
    AIValidationResult,
    ActivityRule,
    ActivityValidationResult,
    BasicCertificatePreValidator,
    CertificateAIDataExtractor,
    CertificateAIPreValidator,
    CertificateAIPromptOptimizer,
    CertificateDataExtractor,
    CertificateValidationProcessor,
    CertificateValidationResult,
    ExtractedCertificateData,
    OpenAICompatibleAIClient,
    StudentContext,
    build_ai_client_from_env,
)
