from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0003_approvalrule"),
    ]

    operations = [
        migrations.AddField(
            model_name="approvalrule",
            name="last_checked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
