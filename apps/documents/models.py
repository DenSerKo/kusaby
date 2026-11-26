from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ApprovalRule(models.Model):
    class Interval(models.IntegerChoices):
        FIVE_MINUTES = 5, "Каждые 5 минут"
        FIFTEEN_MINUTES = 15, "Каждые 15 минут"
        THIRTY_MINUTES = 30, "Каждые 30 минут"
        SIXTY_MINUTES = 60, "Каждый час"

    connection = models.ForeignKey(
        "accounts.SabyConnection",
        on_delete=models.CASCADE,
        related_name="approval_rules",
    )
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    interval_minutes = models.PositiveSmallIntegerField(
        choices=Interval.choices,
        default=Interval.FIVE_MINUTES,
    )
    criteria = models.JSONField(default=dict, blank=True)
    next_run_at = models.DateTimeField(default=timezone.now)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self) -> str:
        return self.name


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
    rule = models.ForeignKey(
        ApprovalRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runs",
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
    rule = models.ForeignKey(
        ApprovalRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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
            models.UniqueConstraint(
                fields=("rule", "document_id"),
                condition=Q(rule__isnull=False),
                name="unique_rule_approval_per_document",
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
