import uuid
from django.core.management.base import BaseCommand
from core.models import Instrument, Folder, Source

class Command(BaseCommand):
    help = "Create sample source documents for all instruments"

    # Sample documents by instrument vendor/type
    SAMPLE_DOCS = {
        "BD": [  # Flow Cytometers
            ("BD FACSAria III User Manual v8.2.pdf", "pdf", "manual", "Manuals", "8.2", ["FACSAria III"], "Complete user manual covering instrument operation, maintenance, and safety procedures."),
            ("Daily Calibration Protocol.pdf", "pdf", "protocol", "Protocols", None, [], "Step-by-step daily calibration procedure using CS&T beads."),
            ("Startup and Shutdown SOP.pdf", "pdf", "sop", "SOPs", "Rev 2024", [], "Standard operating procedure for proper instrument startup and shutdown sequences."),
            ("Biosafety Level 2 Handling SOP.pdf", "pdf", "sop", "SOPs", "Rev 2023-Q4", [], "BSL-2 safety protocols for handling biological samples in the facility."),
            ("Troubleshooting Flow Cell Clogs.pdf", "pdf", "troubleshooting", "Troubleshooting", None, ["FACSAria III", "FACSAria Fusion"], "Common causes and solutions for flow cell blockages."),
            ("Sample Preparation Training.mp4", "video", "training", "Training", None, [], "Video tutorial on proper sample preparation techniques for flow cytometry."),
            ("CS&T Bead Setup Guide.pdf", "pdf", "maintenance", "Maintenance", None, [], "Cytometer setup and tracking bead calibration procedures."),
            ("Common Error Codes Reference.pdf", "pdf", "troubleshooting", "Troubleshooting", "v3.0", [], "Complete error code reference with diagnostic steps."),
        ],
        "Thermo": [  # Mass Spectrometers
            ("Q Exactive Plus Orbitrap Manual v3.1.pdf", "pdf", "manual", "Manuals", "3.1", ["Q Exactive Plus"], "Official user manual for Q Exactive Plus Orbitrap mass spectrometer."),
            ("LC-MS Method Development Protocol.pdf", "pdf", "protocol", "Protocols", None, [], "Guidelines for developing robust LC-MS methods for small molecule analysis."),
            ("Ion Source Cleaning Procedure.pdf", "pdf", "maintenance", "Maintenance", "Rev 2024-01", [], "Detailed H-ESI probe cleaning and maintenance schedule."),
            ("Instrument Tuning Tutorial.mp4", "video", "training", "Training", None, [], "Step-by-step video guide for instrument calibration and tuning."),
            ("Peak Identification Troubleshooting.pdf", "pdf", "troubleshooting", "Troubleshooting", None, ["Q Exactive", "Q Exactive Plus"], "Strategies for resolving poor peak shape and sensitivity issues."),
            ("Sample Injection SOP.pdf", "pdf", "sop", "SOPs", "Rev 2023", [], "Standard procedure for proper sample injection and data acquisition."),
            ("Preventive Maintenance Schedule.pdf", "pdf", "maintenance", "Maintenance", None, [], "Annual and quarterly maintenance tasks to ensure optimal performance."),
        ],
        "Agilent": [  # Various instruments
            ("1260 Infinity II HPLC User Guide.pdf", "pdf", "manual", "Manuals", "v2.0", ["1260 Infinity II"], "Complete user guide for the 1260 Infinity II HPLC system."),
            ("Column Selection and Care.pdf", "pdf", "protocol", "Protocols", None, [], "Best practices for HPLC column selection, installation, and maintenance."),
            ("System Suitability Test SOP.pdf", "pdf", "sop", "SOPs", "Rev 2024", [], "Standard system suitability testing procedure before sample analysis."),
            ("Leak Detection and Repair.pdf", "pdf", "troubleshooting", "Troubleshooting", None, [], "How to identify and fix common leak sources in the fluidic path."),
            ("New User Training Checklist.pdf", "pdf", "training", "Training", None, [], "Comprehensive checklist for training new HPLC operators."),
            ("Pump Seal Replacement Guide.pdf", "pdf", "maintenance", "Maintenance", "v1.2", [], "Instructions for replacing pump seals and testing for proper operation."),
        ],
        "Zeiss": [  # Microscopes
            ("LSM 980 Confocal Manual.pdf", "pdf", "manual", "Manuals", "v5.3", ["LSM 980"], "User manual for LSM 980 confocal laser scanning microscope."),
            ("Live Cell Imaging Protocol.pdf", "pdf", "protocol", "Protocols", None, [], "Protocols for maintaining cell viability during long-term imaging experiments."),
            ("Objective Cleaning SOP.pdf", "pdf", "sop", "SOPs", "Rev 2024", [], "Proper cleaning procedures for microscope objectives and immersion media."),
            ("Alignment and Calibration.pdf", "pdf", "maintenance", "Maintenance", None, [], "Procedures for optical alignment and system calibration."),
            ("Image Acquisition Tutorial.mp4", "video", "training", "Training", None, [], "Introduction to confocal image acquisition and parameter optimization."),
            ("Laser Safety Guidelines.pdf", "pdf", "training", "Training", None, [], "Laser safety protocols and emergency procedures for the facility."),
        ],
        "default": [  # Generic documents for any other vendor
            ("Instrument User Manual.pdf", "pdf", "manual", "Manuals", "v1.0", [], "General user manual and operational guidelines."),
            ("Standard Operating Procedure.pdf", "pdf", "sop", "SOPs", "Rev 2024", [], "Standard operating procedures for routine instrument operation."),
            ("Basic Troubleshooting Guide.pdf", "pdf", "troubleshooting", "Troubleshooting", None, [], "Common issues and solutions for instrument operation."),
            ("New User Training.mp4", "video", "training", "Training", None, [], "Basic training video for new instrument users."),
            ("Maintenance Schedule.pdf", "pdf", "maintenance", "Maintenance", None, [], "Recommended maintenance tasks and schedule."),
        ]
    }

    def handle(self, *args, **options):
        instruments = Instrument.objects.all()
        total_created = 0

        for instrument in instruments:
            self.stdout.write(f"\nProcessing {instrument.vendor} - {instrument.name}...")

            # Get sample docs for this vendor or use default
            docs = self.SAMPLE_DOCS.get(instrument.vendor, self.SAMPLE_DOCS["default"])

            for title, doc_type, category, folder_name, version, model_tags, description in docs:
                # Get or create folder
                folder = Folder.objects.filter(
                    instrument=instrument,
                    name=folder_name,
                    parent=None
                ).first()

                if not folder:
                    folder = Folder.objects.create(
                        instrument=instrument,
                        name=folder_name,
                        parent=None
                    )

                # Check if source already exists
                existing = Source.objects.filter(
                    instrument=instrument,
                    title=title
                ).first()

                if existing:
                    self.stdout.write(f"  - Already exists: {title}")
                    continue

                # Create source
                source = Source.objects.create(
                    instrument=instrument,
                    folder=folder,
                    type=doc_type,
                    title=title,
                    category=category,
                    description=description,
                    version=version,
                    model_tags=model_tags if model_tags else [],
                    storage_uri=f"minio://fake/{uuid.uuid4()}/{title}",
                    status="approved"
                )

                total_created += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ Created: {title}"))

        self.stdout.write(self.style.SUCCESS(f"\n\nDone! Created {total_created} sample documents across {instruments.count()} instruments."))
