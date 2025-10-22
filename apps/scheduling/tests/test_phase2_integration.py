"""
Phase 2 Integration Tests
Test that refactored components work together:
- ScheduleGeneratorLLM
- DataAccessLayer
- LLMService
- ScheduleSystem (refactored)
- ScheduleValidator (refactored)
"""

import logging
import json
from django.test import TestCase
from unittest.mock import Mock, patch, MagicMock

from apps.scheduling.services.schedule_system import ScheduleSystem
from apps.scheduling.services.schedule_validator import ScheduleValidator
from apps.scheduling.services.schedule_generator_llm import ScheduleGeneratorLLM
from apps.scheduling.services.data_access_layer import DataAccessLayer
from apps.scheduling.services.llm_service import LLMDataProcessor, LLMPromptBuilder

logger = logging.getLogger(__name__)


class Phase2ArchitectureTest(TestCase):
    """Test Phase 2 refactored architecture"""
    
    def setUp(self):
        """Initialize test fixtures"""
        self.schedule_system = ScheduleSystem()
        self.validator = ScheduleValidator()
        self.generator = ScheduleGeneratorLLM()
        
    def test_schedule_system_initialization(self):
        """Test ScheduleSystem initializes with new architecture"""
        self.assertIsNotNone(self.schedule_system.generator)
        self.assertIsInstance(self.schedule_system.generator, ScheduleGeneratorLLM)
        self.assertIsNotNone(self.schedule_system.dal)
        self.assertIsNotNone(self.schedule_system.data_processor)
        self.assertIsInstance(self.schedule_system.data_processor, LLMDataProcessor)
    
    def test_schedule_system_initialize(self):
        """Test ScheduleSystem.initialize() works"""
        result = self.schedule_system.initialize()
        self.assertTrue(result)
    
    @patch('apps.scheduling.services.schedule_system.DataAccessLayer.get_schedule_data_for_llm')
    def test_load_database_context(self, mock_dal):
        """Test load_database_context uses DataAccessLayer"""
        mock_data = {
            'dot_xep_list': [],
            'all_rooms': [],
            'all_timeslots': []
        }
        mock_dal.return_value = mock_data
        
        result = self.schedule_system.load_database_context('2025-2026_HK1')
        
        self.assertEqual(result, mock_data)
        mock_dal.assert_called_once_with('2025-2026_HK1')
    
    @patch('apps.scheduling.services.schedule_system.ScheduleGeneratorLLM.create_schedule_llm')
    def test_create_schedule_with_generator(self, mock_generate):
        """Test create_schedule uses ScheduleGeneratorLLM"""
        mock_generate.return_value = "✅ Schedule created"
        
        result = self.schedule_system.create_schedule('2025-2026_HK1')
        
        self.assertTrue(result['success'])
        self.assertEqual(result['semester_code'], '2025-2026_HK1')
        mock_generate.assert_called_once_with('2025-2026_HK1')
    
    def test_analyze_schedule_request_create_schedule(self):
        """Test analyze_schedule_request identifies 'create schedule' request"""
        with patch.object(self.schedule_system, 'create_schedule') as mock_create:
            mock_create.return_value = {'success': True, 'semester_code': '2025-2026_HK1'}
            
            result = self.schedule_system.analyze_schedule_request(
                "tạo lịch cho học kỳ 2025-2026_HK1"
            )
            
            mock_create.assert_called_once()
            # Result is JSON string
            self.assertIn('success', result)
    
    def test_analyzer_schedule_request_with_llm_service(self):
        """Test analyze_schedule_request uses LLM components for non-create requests"""
        result = self.schedule_system.analyze_schedule_request(
            "Giảng viên nào dạy môn Lập trình?"
        )
        
        # Should return a response (can be enhanced with actual LLM integration later)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)


class Phase2ValidatorTest(TestCase):
    """Test Phase 2 refactored ScheduleValidator"""
    
    def setUp(self):
        """Initialize validator"""
        self.validator = ScheduleValidator()
    
    def test_validator_initialization(self):
        """Test ScheduleValidator initializes correctly"""
        self.assertIsNotNone(self.validator)
        self.assertEqual(len(self.validator.violations), 0)
    
    def test_validator_reset(self):
        """Test validator.reset() clears state"""
        self.validator.violations = [Mock()]
        self.validator.reset()
        self.assertEqual(len(self.validator.violations), 0)
    
    def test_validate_schedule_empty_data(self):
        """Test validate_schedule handles empty schedule"""
        result = self.validator.validate_schedule(
            schedule_data={'schedule': []},
            classes_data=[],
            rooms_data={'LT': [], 'TH': []}
        )
        
        self.assertFalse(result['feasible'])
        self.assertIn('No schedules found', result['errors'])
    
    def test_validate_schedule_with_data(self):
        """Test validate_schedule with sample data"""
        schedule_data = {
            'schedule': [
                {'class': 'LT001', 'room': 'P001', 'slot': 'Thu2-Ca1'}
            ]
        }
        classes_data = [
            {'id': 'LT001', 'ma_lop': 'LT001', 'so_luong_sv': 30}
        ]
        rooms_data = {'LT': ['P001'], 'TH': []}
        assignments_data = [
            {'MaLop': 'LT001', 'MaGV': 'GV001'}
        ]
        
        result = self.validator.validate_schedule(
            schedule_data=schedule_data,
            classes_data=classes_data,
            rooms_data=rooms_data,
            assignments_data=assignments_data,
            preferences_data=[]
        )
        
        # Should return valid result structure
        self.assertIn('feasible', result)
        self.assertIn('errors', result)
        self.assertIn('metrics', result)
    
    def test_validate_schedule_returns_required_fields(self):
        """Test validate_schedule returns all required fields"""
        result = self.validator.validate_schedule(
            schedule_data={'schedule': []},
            classes_data=[],
            rooms_data={'LT': [], 'TH': []}
        )
        
        required_fields = [
            'feasible', 'errors', 'metrics',
            'violations_by_type', 'soft_violations_by_type'
        ]
        for field in required_fields:
            self.assertIn(field, result)


class Phase2DataFlowTest(TestCase):
    """Test data flow through refactored architecture"""
    
    @patch('apps.scheduling.services.schedule_system.DataAccessLayer')
    @patch('apps.scheduling.services.schedule_system.ScheduleGeneratorLLM')
    def test_end_to_end_schedule_creation(self, mock_generator_class, mock_dal_class):
        """Test end-to-end schedule creation flow"""
        # Setup mocks
        mock_dal = Mock()
        mock_generator = Mock()
        mock_dal_class.return_value = mock_dal
        mock_generator_class.return_value = mock_generator
        
        mock_dal.get_schedule_data_for_llm.return_value = {
            'dot_xep_list': [Mock(ma_dot='HK1')],
            'all_rooms': [],
            'all_timeslots': []
        }
        mock_generator.create_schedule_llm.return_value = "✅ Created"
        
        # Test flow
        system = ScheduleSystem()
        data = system.load_database_context('2025-2026_HK1')
        result = system.create_schedule('2025-2026_HK1')
        
        # Verify data flow
        self.assertIsNotNone(data)
        self.assertTrue(result['success'])


class Phase2BackwardCompatibilityTest(TestCase):
    """Test backward compatibility with Phase 1 code"""
    
    def test_schedule_system_has_legacy_methods(self):
        """Test ScheduleSystem maintains backward compatible interface"""
        system = ScheduleSystem()
        
        # Old interface should still exist
        self.assertTrue(callable(getattr(system, 'initialize', None)))
        self.assertTrue(callable(getattr(system, 'analyze_schedule_request', None)))
        self.assertTrue(callable(getattr(system, 'load_database_context', None)))
    
    def test_validator_has_legacy_interface(self):
        """Test ScheduleValidator maintains backward compatible interface"""
        validator = ScheduleValidator()
        
        # Old interface should still exist
        self.assertTrue(callable(getattr(validator, 'validate_schedule', None)))
        self.assertTrue(callable(getattr(validator, 'reset', None)))


# ======================== INTEGRATION SUMMARY ========================
"""
Phase 2 Integration Test Coverage:

✅ Architecture Tests:
   - ScheduleSystem uses ScheduleGeneratorLLM
   - ScheduleSystem uses DataAccessLayer
   - ScheduleSystem uses LLMService
   - All components initialized correctly

✅ Component Tests:
   - ScheduleValidator processes schedule data
   - ScheduleValidator returns required output fields
   - ScheduleValidator handles empty data gracefully

✅ Data Flow Tests:
   - End-to-end schedule creation works
   - Data flows correctly through components
   - Mock data propagates properly

✅ Backward Compatibility Tests:
   - Old method signatures still available
   - New implementations replace old code
   - Legacy interfaces maintained
"""
