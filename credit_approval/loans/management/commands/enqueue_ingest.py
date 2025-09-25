from django.core.management.base import BaseCommand
from loans.tasks import ingest_excel_data

class Command(BaseCommand):
    help = "Enqueue ingestion of excel data via Celery"

    def handle(self, *args, **options):
        ingest_excel_data.delay()
        self.stdout.write(self.style.SUCCESS("Ingest task enqueued"))
