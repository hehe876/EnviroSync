"""Federation public interface independent of HTTP and CLI."""
from .service import S3Federation
__all__ = ["S3Federation"]
