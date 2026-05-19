"""Notification subsystem — rule evaluation + channel dispatch."""
from app.notify.dispatcher import dispatch_event, eval_filter
from app.notify.smtp import SMTPConfig, send_email

__all__ = ["dispatch_event", "eval_filter", "SMTPConfig", "send_email"]
