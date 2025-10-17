"""
Management command to generate schedules
Usage: python manage.py generate_schedule --period 2025-2026_HK1
"""

from django.core.management.base import BaseCommand, CommandError
from apps.scheduling.models import DotXep
from apps.scheduling.services.schedule_service import ScheduleService


class Command(BaseCommand):
    help = 'Generate optimal schedule for a scheduling period'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--period',
            type=str,
            required=True,
            help='Scheduling period code (e.g., 2025-2026_HK1)'
        )
        parser.add_argument(
            '--use-ai',
            action='store_true',
            default=True,
            help='Use AI for optimization (default: True)'
        )
        parser.add_argument(
            '--greedy',
            action='store_true',
            help='Use greedy algorithm instead of AI'
        )
    
    def handle(self, *args, **options):
        ma_dot = options['period']
        use_ai = not options['greedy']  # If greedy flag is set, don't use AI
        
        self.stdout.write(self.style.WARNING(
            f'Generating schedule for period: {ma_dot}'
        ))
        self.stdout.write(f'Method: {"AI" if use_ai else "Greedy Algorithm"}')
        
        # Check if period exists
        try:
            dot_xep = DotXep.objects.get(ma_dot=ma_dot)
            self.stdout.write(f'Period found: {dot_xep.ten_dot}')
        except DotXep.DoesNotExist:
            raise CommandError(f'Period "{ma_dot}" does not exist')
        
        # Generate schedule
        try:
            service = ScheduleService()
            result = service.generate_schedule(ma_dot, use_ai=use_ai)
            
            if result['success']:
                self.stdout.write(self.style.SUCCESS(
                    f'\n✅ Schedule generated successfully!'
                ))
                self.stdout.write(f"Total classes: {result['total_classes']}")
                self.stdout.write(f"Scheduled: {result['scheduled_count']}")
                self.stdout.write(f"Method: {result['method']}")
            else:
                raise CommandError(f"Failed to generate schedule: {result.get('error')}")
        
        except Exception as e:
            raise CommandError(f'Error: {str(e)}')
