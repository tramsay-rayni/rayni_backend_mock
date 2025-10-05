from django.core.management.base import BaseCommand
from core.models import Instrument, Folder

class Command(BaseCommand):
    help = "Create default folders for all instruments"

    def handle(self, *args, **options):
        default_folders = ["Manuals", "Protocols", "SOPs", "Troubleshooting", "Training", "Maintenance"]

        instruments = Instrument.objects.all()
        for instrument in instruments:
            self.stdout.write(f"Creating folders for {instrument.name}...")
            for folder_name in default_folders:
                folder, created = Folder.objects.get_or_create(
                    instrument=instrument,
                    name=folder_name,
                    parent=None
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Created folder: {folder_name}"))
                else:
                    self.stdout.write(f"  - Folder already exists: {folder_name}")

        self.stdout.write(self.style.SUCCESS(f"\nDone! Processed {instruments.count()} instruments."))
