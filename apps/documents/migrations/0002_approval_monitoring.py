from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("documents", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="approvalitem",
            name="saby_url",
            field=models.URLField(blank=True, max_length=2000),
        ),
        migrations.AddField(
            model_name="approvalitem",
            name="accepted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="approvalitem",
            name="status",
            field=models.CharField(
                choices=[
                    ("queued", "В очереди"),
                    ("running", "Выполняется"),
                    ("pending", "Ожидает подтверждения"),
                    ("succeeded", "Утверждён"),
                    ("failed", "Ошибка"),
                    ("overdue", "Просрочен"),
                    ("unknown", "Требует проверки"),
                ],
                default="queued",
                max_length=16,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="approvalitem",
            name="unique_active_approval_per_document",
        ),
        migrations.AddConstraint(
            model_name="approvalitem",
            constraint=models.UniqueConstraint(
                condition=Q(status__in=("queued", "running", "pending")),
                fields=("connection", "document_id"),
                name="unique_active_approval_per_document",
            ),
        ),
        migrations.CreateModel(
            name="SabyEventsCursor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("last_event_id", models.CharField(blank=True, max_length=255)),
                ("last_event_datetime", models.CharField(blank=True, max_length=32)),
                ("last_event_document_id", models.CharField(blank=True, max_length=255)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("connection", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="events_cursor", to="accounts.sabyconnection")),
            ],
        ),
    ]
