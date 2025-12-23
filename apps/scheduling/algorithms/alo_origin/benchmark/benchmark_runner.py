#!/usr/bin/env python3
"""
Benchmark runner for scheduling algorithm testing.
Runs multiple configurations and compares results.
"""

import subprocess
import json
import time
import re
from pathlib import Path
from typing import Dict, List, Tuple
import argparse


class BenchmarkConfig:
    """Configuration for a single benchmark run."""
    
    def __init__(self, instance: str, time_limit: int, seed: int, meta: str = "TS", init: str = "greedy-cprop", output_dir: Path = None, instance_full_path: str = None):
        self.instance = instance
        self.instance_full_path = instance_full_path or instance  # Use full path if provided
        self.time_limit = time_limit
        self.seed = seed
        self.meta = meta
        self.init = init
        # Save to test_data directory
        output_filename = f"test_{Path(instance).stem}_t{time_limit}_s{seed}.sol"
        self.output_file = str(output_dir / output_filename) if output_dir else output_filename
    
    def to_cmd(self) -> List[str]:
        """Convert to command line arguments."""
        # Use relative path from benchmark directory to algorithms_core.py
        algo_path = "../../algorithms_core.py"
        return [
            "python", algo_path,
            "--instance", self.instance_full_path,
            "--out", self.output_file,
            "--time_limit", str(self.time_limit),
            "--seed", str(self.seed),
            "--meta", self.meta,
            "--init", self.init
        ]
    
    def __repr__(self):
        return f"Config(time={self.time_limit}s, seed={self.seed})"


class BenchmarkResult:
    """Result from a single benchmark run."""
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.elapsed_time = 0.0
        self.total_cost = None
        self.hard_violations = {}
        self.soft_costs = {}
        self.success = False
        self.error_message = None
    
    def validate_solution(self, instance_file: str, working_dir: Path):
        """Validate solution using existing validator.py script."""
        # Validator is in apps/scheduling/utils/
        # working_dir = benchmark/, parent.parent = algorithms/, parent.parent.parent = scheduling/
        validator_path = working_dir.parent.parent.parent / "utils" / "validator.py"
        
        if not validator_path.exists():
            print(f"Warning: Validator not found at {validator_path}, using solver output only")
            return False
        
        try:
            # validator.py uses positional args: validator.py <instance.ctt> <solution.sol>
            # Run from the scheduling directory (parent.parent.parent of benchmark/)
            scheduling_dir = working_dir.parent.parent.parent
            result = subprocess.run(
                ["python", str(validator_path), 
                 instance_file, 
                 str(self.config.output_file)],
                cwd=scheduling_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # validator.py may return non-zero for infeasible solutions, but still produces output
            if result.stdout:
                self.parse_validator_output(result.stdout)
                return True
            else:
                print(f"Validator failed: {result.stderr[:200]}")
                return False
        
        except Exception as e:
            print(f"Validator error: {e}")
            return False
    
    def parse_validator_output(self, output: str):
        """Parse validator output to extract full cost breakdown."""
        lines = output.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Hard constraints
            if "Violations of Lectures" in line:
                match = re.search(r':\s*(\d+)', line)
                if match:
                    self.hard_violations['lectures'] = int(match.group(1))
            
            if "Violations of Conflicts" in line:
                match = re.search(r':\s*(\d+)', line)
                if match:
                    self.hard_violations['conflicts'] = int(match.group(1))
            
            if "Violations of Availability" in line:
                match = re.search(r':\s*(\d+)', line)
                if match:
                    self.hard_violations['availability'] = int(match.group(1))
            
            if "Violations of RoomOccupation" in line:
                match = re.search(r':\s*(\d+)', line)
                if match:
                    self.hard_violations['room_occupation'] = int(match.group(1))
            
            if "Violations of RoomType" in line:
                match = re.search(r':\s*(\d+)', line)
                if match:
                    self.hard_violations['room_type'] = int(match.group(1))
            
            if "Violations of Equipment" in line:
                match = re.search(r':\s*(\d+)', line)
                if match:
                    self.hard_violations['equipment'] = int(match.group(1))
            
            # Soft costs
            if "Cost of RoomCapacity" in line:
                match = re.search(r':\s*(\d+)', line)
                if match:
                    self.soft_costs['room_capacity'] = int(match.group(1))
            
            if "Cost of MinWorkingDays" in line:
                match = re.search(r':\s*(\d+)', line)
                if match:
                    self.soft_costs['min_working_days'] = int(match.group(1))
            
            if "Cost of CurriculumCompactness" in line:
                match = re.search(r':\s*(\d+)', line)
                if match:
                    self.soft_costs['curriculum_compactness'] = int(match.group(1))
            
            if "Cost of RoomStability" in line:
                match = re.search(r':\s*(\d+)', line)
                if match:
                    self.soft_costs['room_stability'] = int(match.group(1))
            
            if "Cost of LectureConsecutiveness" in line:
                match = re.search(r':\s*(\d+)', line)
                if match:
                    self.soft_costs['lecture_consecutiveness'] = int(match.group(1))
            
            if "Cost of TeacherLectureConsolidation" in line:
                match = re.search(r':\s*(\d+)', line)
                if match:
                    self.soft_costs['teacher_consolidation'] = int(match.group(1))
            
            if "Cost of TeacherWorkingDays" in line:
                match = re.search(r':\s*(\d+)', line)
                if match:
                    self.soft_costs['teacher_working_days'] = int(match.group(1))
            
            if "Cost of TeacherPreferences" in line:
                match = re.search(r':\s*(\d+)', line)
                if match:
                    self.soft_costs['teacher_preferences'] = int(match.group(1))
            
            # Total cost
            if "Total Cost =" in line:
                match = re.search(r'=\s*(\d+)', line)
                if match:
                    self.total_cost = int(match.group(1))
        
        self.success = self.total_cost is not None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'config': {
                'instance': self.config.instance,
                'time_limit': self.config.time_limit,
                'seed': self.config.seed,
                'meta': self.config.meta,
                'init': self.config.init,
                'output_file': self.config.output_file
            },
            'elapsed_time': self.elapsed_time,
            'total_cost': self.total_cost,
            'hard_violations': self.hard_violations,
            'soft_costs': self.soft_costs,
            'success': self.success,
            'error_message': self.error_message,
            'is_feasible': sum(self.hard_violations.values()) == 0 if self.hard_violations else None
        }


class BenchmarkRunner:
    """Runs multiple benchmark configurations and collects results."""
    
    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
        self.results: List[BenchmarkResult] = []
    
    def run_single(self, config: BenchmarkConfig) -> BenchmarkResult:
        """Run a single benchmark configuration."""
        result = BenchmarkResult(config)
        
        print(f"\n{'='*70}")
        print(f"Running: {config}")
        print(f"Command: {' '.join(config.to_cmd())}")
        print(f"{'='*70}")
        
        start_time = time.time()
        
        try:
            process = subprocess.run(
                config.to_cmd(),
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=config.time_limit + 60  # Extra 60s for initialization
            )
            
            result.elapsed_time = time.time() - start_time
            
            if process.returncode == 0:
                print("\n✓ Run completed successfully")
                
                # Validate solution using validator
                if result.validate_solution(config.instance_full_path, self.working_dir):
                    print(f"✓ Validation successful")
                    print(f"✓ Total cost: {result.total_cost}")
                    print(f"  Hard violations: {sum(result.hard_violations.values())}")
                    print(f"  - Teacher working days (S7): {result.soft_costs.get('teacher_working_days', 'N/A')}")
                    print(f"  - Teacher preferences (S8): {result.soft_costs.get('teacher_preferences', 'N/A')}")
                    print(f"  - Teacher consolidation (S6): {result.soft_costs.get('teacher_consolidation', 'N/A')}")
                else:
                    print("✗ Validation failed, using solver output")
                    result.parse_validator_output(process.stdout)
                
                if not result.success:
                    print("✗ Failed to parse results")
                    result.error_message = "Failed to parse output"
            else:
                print(f"\n✗ Run failed with return code {process.returncode}")
                result.error_message = f"Return code {process.returncode}"
                print("STDERR:", process.stderr[:500])
        
        except subprocess.TimeoutExpired:
            result.elapsed_time = time.time() - start_time
            result.error_message = "Timeout"
            print(f"\n✗ Run timed out after {result.elapsed_time:.1f}s")
        
        except Exception as e:
            result.elapsed_time = time.time() - start_time
            result.error_message = str(e)
            print(f"\n✗ Run failed with exception: {e}")
        
        self.results.append(result)
        return result
    
    def run_all(self, configs: List[BenchmarkConfig]):
        """Run all benchmark configurations."""
        print(f"\n{'#'*70}")
        print(f"# Starting benchmark suite: {len(configs)} configurations")
        print(f"{'#'*70}")
        
        for i, config in enumerate(configs, 1):
            print(f"\n[{i}/{len(configs)}]")
            self.run_single(config)
        
        print(f"\n{'#'*70}")
        print(f"# Benchmark suite completed")
        print(f"{'#'*70}")
    
    def save_results(self, output_path: Path):
        """Save results to JSON file."""
        data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_runs': len(self.results),
            'successful_runs': sum(1 for r in self.results if r.success),
            'results': [r.to_dict() for r in self.results]
        }
        
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Results saved to: {output_path}")
    
    def print_summary(self):
        """Print comparison summary."""
        successful = [r for r in self.results if r.success]
        
        if not successful:
            print("\n✗ No successful runs to compare")
            return
        
        print(f"\n{'='*70}")
        print(f"BENCHMARK SUMMARY ({len(successful)} successful runs)")
        print(f"{'='*70}\n")
        
        # Sort by total cost
        successful.sort(key=lambda r: r.total_cost)
        
        # Table header
        print(f"{'Rank':<6} {'Time':>6} {'Seed':>6} {'Total':>7} {'S7':>5} {'S8':>5} {'S6':>5} {'Output':<30}")
        print(f"{'-'*6} {'-'*6} {'-'*6} {'-'*7} {'-'*5} {'-'*5} {'-'*5} {'-'*30}")
        
        # Table rows
        for rank, result in enumerate(successful, 1):
            time_limit = result.config.time_limit
            seed = result.config.seed
            total = result.total_cost
            s7 = result.soft_costs.get('teacher_working_days', 0)
            s8 = result.soft_costs.get('teacher_preferences', 0)
            s6 = result.soft_costs.get('teacher_consolidation', 0)
            output = result.config.output_file
            
            marker = "🏆" if rank == 1 else "  "
            print(f"{marker}{rank:<4} {time_limit:>6} {seed:>6} {total:>7} {s7:>5} {s8:>5} {s6:>5} {output:<30}")
        
        # Best result details
        best = successful[0]
        print(f"\n{'='*70}")
        print(f"BEST RESULT: {best.config}")
        print(f"{'='*70}")
        print(f"Total Cost: {best.total_cost}")
        print(f"Elapsed Time: {best.elapsed_time:.2f}s")
        print("\nSoft Costs Breakdown:")
        for key, value in sorted(best.soft_costs.items()):
            print(f"  {key:30s}: {value:>5}")


def main():
    parser = argparse.ArgumentParser(description="Benchmark runner for scheduling algorithm")
    parser.add_argument("--instance", type=str, default="dot1.ctt", help="Instance file")
    parser.add_argument("--time-limits", type=int, nargs="+", default=[100, 300, 600, 1000], 
                       help="Time limits to test (seconds)")
    parser.add_argument("--seeds", type=int, nargs="+", default=[42], 
                       help="Random seeds to test")
    parser.add_argument("--meta", type=str, default="TS", choices=["SA", "TS"], 
                       help="Metaheuristic algorithm")
    parser.add_argument("--init", type=str, default="greedy-cprop", 
                       choices=["greedy-cprop", "random-repair"], 
                       help="Initial solution strategy")
    parser.add_argument("--output", type=str, default="benchmark_results.json", 
                       help="Output JSON file for results")
    
    args = parser.parse_args()
    
    # Setup paths
    script_dir = Path(__file__).parent
    test_data_dir = script_dir.parent / "test_data"
    
    # Create test_data directory if not exists
    test_data_dir.mkdir(exist_ok=True)
    print(f"Output directory: {test_data_dir}")
    
    # Find instance file - try multiple locations
    instance_path = None
    possible_locations = [
        script_dir / args.instance,  # In benchmark directory
        test_data_dir / args.instance,  # In test_data directory
        Path(args.instance),  # Absolute or relative from cwd
    ]
    
    for loc in possible_locations:
        if loc.exists():
            instance_path = loc.resolve()
            print(f"Found instance: {instance_path}")
            break
    
    if not instance_path:
        print(f"ERROR: Instance file '{args.instance}' not found in:")
        for loc in possible_locations:
            print(f"  - {loc}")
        return
    
    # Generate configurations
    configs = []
    for time_limit in args.time_limits:
        for seed in args.seeds:
            config = BenchmarkConfig(
                instance=args.instance,
                instance_full_path=str(instance_path),
                time_limit=time_limit,
                seed=seed,
                meta=args.meta,
                init=args.init,
                output_dir=test_data_dir
            )
            configs.append(config)
    
    # Run benchmarks
    runner = BenchmarkRunner(script_dir)
    runner.run_all(configs)
    
    # Save and display results
    output_path = test_data_dir / args.output
    runner.save_results(output_path)
    runner.print_summary()
    
    print(f"\n✓ Benchmark complete! Results saved to: {output_path}")
    print(f"✓ To visualize: python visualize_benchmark.py --input {args.output}")


if __name__ == "__main__":
    main()
