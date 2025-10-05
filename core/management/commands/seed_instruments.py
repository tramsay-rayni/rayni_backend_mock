"""
Django management command to seed the database with realistic scientific laboratory instruments.

Usage:
    python manage.py seed_instruments [--clear]

Options:
    --clear    Delete all existing instruments before seeding
"""
from django.core.management.base import BaseCommand
from core.models import Instrument, Source, Folder, AccessGrant
import uuid


class Command(BaseCommand):
    help = 'Seeds the database with realistic scientific laboratory instruments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing instruments before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing existing instruments...'))
            Instrument.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✓ Cleared all instruments'))

        instruments_data = [
            {
                'name': 'BD FACSymphony',
                'vendor': 'BD Biosciences',
                'models_arr': ['A1', 'A3', 'A5'],
                'visibility': 'public',
                'description': 'High-parameter flow cytometer for cell analysis and sorting with up to 50 parameters'
            },
            {
                'name': 'Orbitrap Fusion',
                'vendor': 'Thermo Fisher Scientific',
                'models_arr': ['Lumos', 'Tribrid'],
                'visibility': 'restricted',
                'description': 'High-resolution mass spectrometer for proteomics and metabolomics research'
            },
            {
                'name': 'QuantStudio Real-Time PCR',
                'vendor': 'Thermo Fisher Scientific',
                'models_arr': ['3', '5', '7 Pro'],
                'visibility': 'public',
                'description': 'Real-time PCR system for gene expression analysis and genotyping'
            },
            {
                'name': 'LSM 980',
                'vendor': 'Zeiss',
                'models_arr': ['Airyscan 2', 'with ELYRA 7'],
                'visibility': 'restricted',
                'description': 'Confocal laser scanning microscope with super-resolution imaging capabilities'
            },
            {
                'name': 'Agilent 1290 Infinity II',
                'vendor': 'Agilent Technologies',
                'models_arr': ['LC System', 'Prime LC'],
                'visibility': 'public',
                'description': 'Ultra-high-performance liquid chromatography system for complex sample separation'
            },
            {
                'name': 'Centrifuge 5910 Ri',
                'vendor': 'Eppendorf',
                'models_arr': ['5910', '5920'],
                'visibility': 'public',
                'description': 'High-capacity refrigerated centrifuge with rotor recognition and imbalance detection'
            },
            {
                'name': 'NanoDrop OneC',
                'vendor': 'Thermo Fisher Scientific',
                'models_arr': ['OneC', 'Eight'],
                'visibility': 'public',
                'description': 'UV-Vis spectrophotometer for nucleic acid and protein quantification'
            },
            {
                'name': 'AVANCE NEO',
                'vendor': 'Bruker',
                'models_arr': ['400', '500', '600 MHz'],
                'visibility': 'restricted',
                'description': 'Nuclear magnetic resonance spectrometer for molecular structure determination'
            },
            {
                'name': 'Cell Discoverer 7',
                'vendor': 'Zeiss',
                'models_arr': ['with AI', 'Standard'],
                'visibility': 'restricted',
                'description': 'Automated live-cell imaging system for long-term cellular research'
            },
            {
                'name': 'Biomek i7',
                'vendor': 'Beckman Coulter',
                'models_arr': ['Automated Workstation', 'Hybrid'],
                'visibility': 'public',
                'description': 'Automated liquid handling workstation for genomics and drug discovery workflows'
            }
        ]

        created_count = 0
        for data in instruments_data:
            instrument, created = Instrument.objects.get_or_create(
                name=data['name'],
                vendor=data['vendor'],
                defaults={
                    'models_arr': data['models_arr'],
                    'visibility': data['visibility'],
                    'description': data['description']
                }
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created: {instrument.vendor} {instrument.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'  Skipped (exists): {instrument.vendor} {instrument.name}')
                )

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(f'Successfully seeded {created_count} new instruments')
        )
        self.stdout.write(
            self.style.SUCCESS(f'Total instruments in database: {Instrument.objects.count()}')
        )
