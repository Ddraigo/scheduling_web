"""
Management command to generate schedules
Usage: python manage.py generate_schedule --period 2025-2026_HK1
"""

from django.core.management.base import BaseCommand, CommandError
from apps.scheduling.models import DotXep
from apps.scheduling.services.schedule_generator_llm import ScheduleGeneratorLLM
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate optimal schedule for a scheduling period using LLM'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--period',
            type=str,
            required=True,
            help='Scheduling period code (e.g., 2025-2026_HK1)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Test without saving to database'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed processing information'
        )
    
    def handle(self, *args, **options):
        ma_dot = options['period']
        dry_run = options.get('dry_run', False)
        verbose = options.get('verbose', False)
        
        self.stdout.write(self.style.WARNING(
            f'🔄 Generating schedule for period: {ma_dot}'
        ))
        self.stdout.write(f'Method: LLM-optimized')
        
        # Verify period exists
        try:
            dot_xep = DotXep.objects.get(ma_dot=ma_dot)
            self.stdout.write(f'✓ Period found: {dot_xep.ten_dot}')
        except DotXep.DoesNotExist:
            raise CommandError(f'❌ Period "{ma_dot}" does not exist')
        
        try:
            # Create generator and generate schedule
            generator = ScheduleGeneratorLLM()
            
            if verbose:
                self.stdout.write(" Fetching data...")
            
            result = generator.create_schedule_llm(
                ma_dot=ma_dot,
                dry_run=dry_run,
                verbose=verbose
            )
            
            if result.get('success', False):
                self.stdout.write(self.style.SUCCESS(
                    '\n✅ Schedule generated successfully!'
                ))
                self.stdout.write(f"📦 Total classes: {result.get('total_classes', 'N/A')}")
                self.stdout.write(f"✓ Scheduled: {result.get('scheduled_count', 'N/A')}")
                
                if 'metrics' in result:
                    metrics = result['metrics']
                    self.stdout.write(f"📈 Token usage: {metrics.get('token_count', 'N/A')}")
                    self.stdout.write(f"⏱️ Processing time: {metrics.get('processing_time', 'N/A')}s")
                    
                if 'file_path' in result:
                    self.stdout.write(f"💾 Saved to: {result['file_path']}")
            else:
                error_msg = result.get('error', 'Unknown error')
                raise CommandError(f'❌ Failed to generate schedule: {error_msg}')
                
        except Exception as e:
            logger.exception(f"Error generating schedule: {e}")
            raise CommandError(f'❌ Error: {str(e)}')
