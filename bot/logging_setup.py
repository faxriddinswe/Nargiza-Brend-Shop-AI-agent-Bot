"""Log sozlamalari: JSON formatda, standart `logging` ustida structlog.

Qoida: log'ga hech qachon token, parol, telefon raqami yoki mijoz ismi yozilmaydi.
Telefonni maskalash yordamchisi 1-bosqichda (`utils/phone.py`) qo'shiladi.
"""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(level: str = "INFO") -> None:
    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(ensure_ascii=False),
            ],
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
