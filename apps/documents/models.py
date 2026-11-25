from django.conf import settings
from django.db import models
from django.db.models import Q


class ApprovalRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "В очереди"
        RUNNING = "running", "Выполняется"
        PENDING = "pending", "Ожидает подтверждения"
        COMPLETED = "completed", "Завершён"
        FAILED = "failed", "Ошибка"

    class Trigger(models.TextChoices):
        MANUAL = "manual", "Ручной запуск"
        AUTOMATIC = "automatic", "Автоматический запуск"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="approval_runs",
    )
    connection = models.ForeignKey(
        "accounts.SabyConnection",
        on_delete=models.SET_NULL,
        null=True,
        related_name="approval_runs",
    )
    trigger = models.CharField(max_length=16, choices=Trigger.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    criteria = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)


class ApprovalItem(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "В очереди"
        RUNNING = "running", "Выполняется"
        PENDING = "pending", "Ожидает подтверждения"
        SUCCEEDED = "succeeded", "Утверждён"
        FAILED = "failed", "Ошибка"
        OVERDUE = "overdue", "Просрочен"
        UNKNOWN = "unknown", "Требует проверки"

    run = models.ForeignKey(
        ApprovalRun,
        on_delete=models.CASCADE,
        related_name="items",
    )
    connection = models.ForeignKey(
        "accounts.SabyConnection",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_items",
    )
    document_id = models.CharField(max_length=255)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    message = models.TextField(blank=True)
    details = models.TextField(blank=True)
    saby_url = models.URLField(max_length=2000, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("connection", "document_id"),
                condition=Q(status__in=("queued", "running", "pending")),
                name="unique_active_approval_per_document",
            ),
        ]


class SabyEventsCursor(models.Model):
    """Контрольная точка общей синхронизации событий одного подключения Saby."""

    connection = models.OneToOneField(
        "accounts.SabyConnection",
        on_delete=models.CASCADE,
        related_name="events_cursor",
    )
    last_event_id = models.CharField(max_length=255, blank=True)
    last_event_datetime = models.CharField(max_length=32, blank=True)
    last_event_document_id = models.CharField(max_length=255, blank=True)
    last_organization = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
