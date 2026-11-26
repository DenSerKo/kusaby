import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0004_approvalrule_last_checked_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="approvalitem",
            name="rule",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="items",
                to="documents.approvalrule",
            ),
        ),
        migrations.AddConstraint(
            model_name="approvalitem",
            constraint=models.UniqueConstraint(
                condition=Q(rule__isnull=False),
                fields=("rule", "document_id"),
                name="unique_rule_approval_per_document",
            ),
        ),
    ]
