import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("documents", "0002_approval_monitoring"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApprovalRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("is_active", models.BooleanField(default=False)),
                ("interval_minutes", models.PositiveSmallIntegerField(
                    choices=[(5, "Каждые 5 минут"), (15, "Каждые 15 минут"), (30, "Каждые 30 минут"), (60, "Каждый час")],
                    default=5,
                )),
                ("criteria", models.JSONField(blank=True, default=dict)),
                ("next_run_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("connection", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="approval_rules",
                    to="accounts.sabyconnection",
                )),
            ],
            options={"ordering": ("created_at",)},
        ),
        migrations.AddField(
            model_name="approvalrun",
            name="rule",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="runs",
                to="documents.approvalrule",
            ),
        ),
    ]
