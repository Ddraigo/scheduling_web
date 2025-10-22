"""
Interactive LLM Test View
Simple web interface to test schedule generation with LLM
"""

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
import logging

from .services.schedule_generator_llm import ScheduleGeneratorLLM
from .models import DotXep

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def llm_test_interactive(request):
    """Interactive LLM testing interface"""
    
    if request.method == 'GET':
        # Get list of available periods
        try:
            periods = list(DotXep.objects.all().values('ma_dot', 'ten_dot', 'trang_thai'))
        except Exception as e:
            logger.error(f"Error fetching periods: {e}")
            periods = []
        
        context = {
            'periods': periods,
            'title': 'LLM Schedule Generation - Interactive Test'
        }
        try:
            return render(request, 'scheduling/llm_test_interactive.html', context)
        except Exception as e:
            logger.error(f"Template render error: {e}")
            # Fallback to JSON if template fails
            return JsonResponse({
                'error': str(e),
                'message': 'Failed to render template',
                'periods': periods
            }, status=400)
    
    elif request.method == 'POST':
        # Handle AJAX requests
        try:
            data = json.loads(request.body)
            action = data.get('action')
            ma_dot = data.get('ma_dot')
            
            if not ma_dot:
                return JsonResponse({'error': 'Period required'}, status=400)
            
            # Get semester code from period
            try:
                dot = DotXep.objects.get(ma_dot=ma_dot)
                # semester_code is the primary key of DuKienDT model (VD: "2025-2026_HK1")
                semester_code = dot.ma_du_kien_dt_id  # Direct foreign key value
                logger.info(f"✅ Period {ma_dot} -> semester_code={semester_code}")
            except DotXep.DoesNotExist:
                logger.error(f"❌ Period {ma_dot} not found")
                return JsonResponse({'error': f'Period {ma_dot} not found'}, status=404)
            
            # Initialize generator
            generator = ScheduleGeneratorLLM()
            
            if action == 'fetch_data':
                return handle_fetch_data(generator, semester_code)
            
            elif action == 'prepare_compact':
                # Assumes previous step fetched data
                # This would need session or separate step
                return handle_prepare_compact(generator, semester_code)
            
            elif action == 'build_prompt':
                return handle_build_prompt(generator, semester_code)
            
            elif action == 'call_llm':
                return handle_call_llm(generator, semester_code)
            
            elif action == 'full_test':
                return handle_full_test(generator, semester_code)
            
            else:
                return JsonResponse({'error': f'Unknown action: {action}'}, status=400)
        
        except Exception as e:
            logger.exception(f"Error in LLM test: {e}")
            return JsonResponse({
                'error': str(e),
                'type': type(e).__name__
            }, status=500)


def handle_fetch_data(generator, semester_code):
    """Fetch schedule data from database"""
    try:
        logger.info(f"🔍 Fetching data for semester_code={semester_code}")
        data = generator._fetch_schedule_data(semester_code)
        
        logger.info(f"📊 Data keys: {data.keys()}")
        logger.info(f"📊 Dot list count: {len(data.get('dot_xep_list', []))}")
        
        if not data or not data.get('dot_xep_list'):
            logger.warning(f"⚠️ No periods found for semester_code={semester_code}")
            return JsonResponse({
                'error': f'No periods found for semester {semester_code}',
                'debug': {
                    'semester_code': semester_code,
                    'dot_count': len(data.get('dot_xep_list', [])) if data else 0
                }
            }, status=404)
        
        return JsonResponse({
            'success': True,
            'data': {
                'classes': sum(len(dot_data.get('phan_cong', [])) for dot_data in data.get('all_dot_data', {}).values()),
                'rooms_lt': len([r for r in data.get('all_rooms', []) if 'LT' in r.loai_phong or 'Lý' in r.loai_phong]),
                'rooms_th': len([r for r in data.get('all_rooms', []) if 'TH' in r.loai_phong or 'Thực' in r.loai_phong]),
                'teachers': len(set([pc.ma_gv.ma_gv for dot_data in data.get('all_dot_data', {}).values() for pc in dot_data.get('phan_cong', [])])),
                'constraints': sum(len(dot_data.get('constraints', [])) for dot_data in data.get('all_dot_data', {}).values()),
                'preferences': sum(len(dot_data.get('preferences', [])) for dot_data in data.get('all_dot_data', {}).values()),
            }
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def handle_prepare_compact(generator, semester_code):
    """Prepare compact data format"""
    try:
        data = generator._fetch_schedule_data(semester_code)
        if not data:
            return JsonResponse({'error': 'No data'}, status=404)
        
        compact = generator._prepare_data_for_llm(data, semester_code)
        
        # Calculate savings - need to convert to serializable format first
        import json as json_module
        def json_serial(obj):
            """Convert non-serializable objects to serializable format"""
            if hasattr(obj, 'isoformat'):  # datetime
                return obj.isoformat()
            if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):  # QuerySet/list
                return list(obj)
            return str(obj)
        
        try:
            full_str = json_module.dumps(data, default=json_serial, ensure_ascii=False)
            compact_str = json_module.dumps(compact, default=json_serial, ensure_ascii=False)
        except TypeError:
            # Fallback: just estimate based on string representation
            full_str = str(data)
            compact_str = str(compact)
        
        full_size = len(full_str)
        compact_size = len(compact_str)
        reduction = (1 - compact_size / full_size) * 100 if full_size > 0 else 0
        
        return JsonResponse({
            'success': True,
            'optimization': {
                'full_bytes': full_size,
                'compact_bytes': compact_size,
                'reduction_percent': round(reduction, 1),
                'slot_mapping_count': len(compact.get('slot_mapping', {})) if isinstance(compact.get('slot_mapping'), dict) else 0,
            }
        })
    
    except Exception as e:
        logger.exception(f"Prepare compact failed: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def handle_build_prompt(generator, semester_code):
    """Build LLM prompt"""
    try:
        data = generator._fetch_schedule_data(semester_code)
        if not data:
            return JsonResponse({'error': 'No data'}, status=404)
        
        compact = generator._prepare_data_for_llm(data, semester_code)
        
        # Build prompt requires conflicts parameter
        conflicts = generator._detect_conflicts(data, semester_code)
        prompt = generator._build_llm_prompt(compact, conflicts)
        
        # Show preview
        preview_lines = prompt.split('\n')[:15]
        
        return JsonResponse({
            'success': True,
            'prompt': {
                'length': len(prompt),
                'estimated_tokens': len(prompt) // 4,
                'preview': '\n'.join(preview_lines)
            }
        })
    
    except Exception as e:
        logger.exception(f"Build prompt failed: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def handle_call_llm(generator, semester_code):
    """Call LLM for schedule generation"""
    try:
        data = generator._fetch_schedule_data(semester_code)
        if not data:
            return JsonResponse({'error': 'No data'}, status=404)
        
        compact = generator._prepare_data_for_llm(data, semester_code)
        
        # Build prompt first (needs conflicts)
        conflicts = generator._detect_conflicts(data, semester_code)
        prompt = generator._build_llm_prompt(compact, conflicts)
        
        # Call LLM with prompt and processed data
        result = generator._call_llm_for_schedule(prompt, compact)
        
        if not result:
            return JsonResponse({'error': 'No result from LLM'}, status=500)
        
        # Parse result
        schedule_count = len(result.get('schedule', []))
        sample = result.get('schedule', [])[:3] if result.get('schedule') else []
        
        return JsonResponse({
            'success': True,
            'llm_result': {
                'schedule_count': schedule_count,
                'sample_assignments': sample,
                'has_errors': len(result.get('errors', [])) > 0,
                'error_count': len(result.get('errors', []))
            }
        })
    
    except Exception as e:
        logger.exception(f"LLM call failed: {e}")
        return JsonResponse({
            'error': str(e),
            'type': type(e).__name__
        }, status=500)


def handle_full_test(generator, semester_code):
    """Full end-to-end test"""
    results = {
        'steps': [],
        'success': True
    }
    
    result = None  # Initialize result variable
    
    def json_serial(obj):
        """Convert non-serializable objects"""
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
            return list(obj)
        return str(obj)
    
    try:
        # Step 1: Fetch data
        results['steps'].append({'name': 'Fetch Data', 'status': 'running'})
        data = generator._fetch_schedule_data(semester_code)
        if data:
            results['steps'][-1]['status'] = 'success'
            # Count classes safely
            class_count = 0
            if 'all_dot_data' in data:
                for dot_data in data['all_dot_data'].values():
                    if 'phan_cong' in dot_data:
                        try:
                            class_count += len(list(dot_data['phan_cong']))
                        except:
                            pass
            results['steps'][-1]['info'] = f"{class_count} classes"
        else:
            results['steps'][-1]['status'] = 'error'
            results['success'] = False
            return JsonResponse(results)
        
        # Step 2: Prepare compact format
        results['steps'].append({'name': 'Prepare Compact Format', 'status': 'running'})
        compact = generator._prepare_data_for_llm(data, semester_code)
        import json as json_module
        try:
            full_str = json_module.dumps(data, default=json_serial, ensure_ascii=False)
            compact_str = json_module.dumps(compact, default=json_serial, ensure_ascii=False)
            full_size = len(full_str)
            compact_size = len(compact_str)
            reduction = (1 - compact_size / full_size) * 100 if full_size > 0 else 0
        except:
            reduction = 0
        results['steps'][-1]['status'] = 'success'
        results['steps'][-1]['info'] = f"{reduction:.1f}% reduction"
        
        # Step 3: Build prompt
        results['steps'].append({'name': 'Build Prompt', 'status': 'running'})
        try:
            conflicts = generator._detect_conflicts(data, semester_code)
            prompt = generator._build_llm_prompt(compact, conflicts)
            results['steps'][-1]['status'] = 'success'
            results['steps'][-1]['info'] = f"{len(prompt) // 4} tokens"
        except Exception as e:
            results['steps'][-1]['status'] = 'error'
            results['steps'][-1]['info'] = f"Failed: {str(e)[:50]}"
            results['success'] = False
            return JsonResponse(results)  # Stop here if build prompt fails
        
        # Step 4: Call LLM
        results['steps'].append({'name': 'Call LLM', 'status': 'running'})
        try:
            result = generator._call_llm_for_schedule(prompt, compact)
            if result:
                schedule_count = len(result.get('schedule', []))
                results['steps'][-1]['status'] = 'success'
                results['steps'][-1]['info'] = f"{schedule_count} assignments"
            else:
                results['steps'][-1]['status'] = 'error'
                results['steps'][-1]['info'] = 'No result'
                results['success'] = False
        except Exception as e:
            results['steps'][-1]['status'] = 'error'
            results['steps'][-1]['info'] = f"Failed: {str(e)[:50]}"
            results['success'] = False
        
        # Step 5: Validate
        results['steps'].append({'name': 'Validate Result', 'status': 'running'})
        if result and isinstance(result, dict) and 'schedule' in result:
            results['steps'][-1]['status'] = 'success'
            results['steps'][-1]['info'] = 'Valid format'
        else:
            results['steps'][-1]['status'] = 'error'
            results['steps'][-1]['info'] = 'Invalid format'
            results['success'] = False
        
        return JsonResponse(results)
    
    except Exception as e:
        logger.exception(f"Full test failed: {e}")
        results['success'] = False
        results['error'] = str(e)
        return JsonResponse(results)
