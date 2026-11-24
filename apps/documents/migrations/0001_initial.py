import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApprovalRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trigger", models.CharField(choices=[("manual", "Ручной запуск"), ("automatic", "Автоматический запуск")], max_length=16)),
                ("status", models.CharField(choices=[("queued", "В очереди"), ("running", "Выполняется"), ("completed", "Завершён"), ("failed", "Ошибка")], default="queued", max_length=16)),
                ("criteria", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("connection", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approval_runs", to="accounts.sabyconnection")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="approval_runs", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="ApprovalItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("document_id", models.CharField(max_length=255)),
                ("status", models.CharField(choices=[("queued", "В очереди"), ("running", "Выполняется"), ("succeeded", "Утверждён"), ("failed", "Ошибка"), ("unknown", "Требует проверки")], default="queued", max_length=16)),
                ("message", models.TextField(blank=True)),
                ("details", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("connection", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="approval_items", to="accounts.sabyconnection")),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="documents.approvalrun")),
            ],
        ),
        migrations.AddConstraint(
            model_name="approvalitem",
            constraint=models.UniqueConstraint(
                condition=Q(status__in=("queued", "running")),
                fields=("connection", "document_id"),
                name="unique_active_approval_per_document",
            ),
        ),
    ]
