#!/usr/bin/env python3
"""
Visualize benchmark results from benchmark_runner.py
Creates comparison charts and detailed analysis.
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict
import sys

try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not available. Charts will be skipped.")


def load_results(json_path: Path) -> Dict:
    """Load benchmark results from JSON file."""
    with json_path.open('r', encoding='utf-8') as f:
        return json.load(f)


def print_comparison_table(data: Dict):
    """Print detailed comparison table."""
    results = data.get('results', [])
    successful = [r for r in results if r.get('success', False)]
    
    if not successful:
        print("No successful runs found.")
        return
    
    # Sort by total cost
    successful.sort(key=lambda r: r.get('total_cost', float('inf')))
    
    print(f"\n{'='*100}")
    print(f"BENCHMARK RESULTS COMPARISON")
    print(f"Timestamp: {data.get('timestamp', 'N/A')}")
    print(f"Total Runs: {data.get('total_runs', 0)} | Successful: {data.get('successful_runs', 0)}")
    print(f"{'='*100}\n")
    
    # Feasibility check
    feasible = [r for r in successful if r.get('is_feasible', True)]
    infeasible = [r for r in successful if not r.get('is_feasible', True)]
    
    if infeasible:
        print(f"⚠️  Warning: {len(infeasible)} solutions have hard constraint violations!\n")
    
    # Detailed table
    print(f"{'Rank':<6} {'Feas':>5} {'Time(s)':>8} {'Seed':>6} {'Total':>7} {'S7':>5} {'S8':>5} {'S6':>5} {'Compact':>8} {'HardViol':>9}")
    print(f"{'-'*6} {'-'*5} {'-'*8} {'-'*6} {'-'*7} {'-'*5} {'-'*5} {'-'*5} {'-'*8} {'-'*9}")
    
    for rank, result in enumerate(successful, 1):
        config = result.get('config', {})
        soft_costs = result.get('soft_costs', {})
        hard_viols = result.get('hard_violations', {})
        
        time_limit = config.get('time_limit', 0)
        seed = config.get('seed', 0)
        total = result.get('total_cost', 0)
        is_feasible = result.get('is_feasible', True)
        total_hard = sum(hard_viols.values()) if hard_viols else 0
        
        s7 = soft_costs.get('teacher_working_days', 0)
        s8 = soft_costs.get('teacher_preferences', 0)
        s6 = soft_costs.get('teacher_consolidation', 0)
        compact = soft_costs.get('curriculum_compactness', 0)
        
        feas_mark = "✓" if is_feasible else "✗"
        marker = "🏆" if rank == 1 and is_feasible else ("🥈" if rank == 2 and is_feasible else ("🥉" if rank == 3 and is_feasible else "  "))
        print(f"{marker}{rank:<4} {feas_mark:>5} {time_limit:>8} {seed:>6} {total:>7} {s7:>5} {s8:>5} {s6:>5} {compact:>8} {total_hard:>9}")


def print_best_vs_worst(data: Dict):
    """Compare best vs worst results."""
    results = data.get('results', [])
    successful = [r for r in results if r.get('success', False)]
    
    if len(successful) < 2:
        print("\nNot enough successful runs for comparison.")
        return
    
    successful.sort(key=lambda r: r.get('total_cost', float('inf')))
    best = successful[0]
    worst = successful[-1]
    
    print(f"\n{'='*100}")
    print(f"BEST vs WORST COMPARISON")
    print(f"{'='*100}\n")
    
    print(f"{'Metric':<30} {'Best':>15} {'Worst':>15} {'Improvement':>20}")
    print(f"{'-'*30} {'-'*15} {'-'*15} {'-'*20}")
    
    best_config = best.get('config', {})
    worst_config = worst.get('config', {})
    best_soft = best.get('soft_costs', {})
    worst_soft = worst.get('soft_costs', {})
    
    # Configuration
    print(f"{'Time Limit (s)':<30} {best_config.get('time_limit', 0):>15} {worst_config.get('time_limit', 0):>15} {'-':>20}")
    print(f"{'Seed':<30} {best_config.get('seed', 0):>15} {worst_config.get('seed', 0):>15} {'-':>20}")
    print()
    
    # Total cost
    best_total = best.get('total_cost', 0)
    worst_total = worst.get('total_cost', 0)
    improvement = ((worst_total - best_total) / worst_total * 100) if worst_total > 0 else 0
    print(f"{'Total Cost':<30} {best_total:>15} {worst_total:>15} {f'-{improvement:.1f}%':>20}")
    print()
    
    # Soft costs breakdown
    metrics = [
        ('teacher_working_days', 'Teacher Working Days (S7)'),
        ('teacher_preferences', 'Teacher Preferences (S8)'),
        ('teacher_consolidation', 'Teacher Consolidation (S6)'),
        ('curriculum_compactness', 'Curriculum Compactness'),
        ('lecture_consecutiveness', 'Lecture Consecutiveness'),
        ('room_stability', 'Room Stability')
    ]
    
    for key, label in metrics:
        best_val = best_soft.get(key, 0)
        worst_val = worst_soft.get(key, 0)
        if worst_val > 0:
            imp = ((worst_val - best_val) / worst_val * 100)
            imp_str = f'-{imp:.1f}%' if imp > 0 else f'+{abs(imp):.1f}%'
        else:
            imp_str = 'N/A'
        print(f"{label:<30} {best_val:>15} {worst_val:>15} {imp_str:>20}")


def print_time_analysis(data: Dict):
    """Analyze relationship between time limit and solution quality."""
    results = data.get('results', [])
    successful = [r for r in results if r.get('success', False)]
    
    if not successful:
        return
    
    # Group by time limit
    by_time = {}
    for result in successful:
        time_limit = result.get('config', {}).get('time_limit', 0)
        if time_limit not in by_time:
            by_time[time_limit] = []
        by_time[time_limit].append(result.get('total_cost', 0))
    
    print(f"\n{'='*100}")
    print(f"TIME LIMIT ANALYSIS")
    print(f"{'='*100}\n")
    
    print(f"{'Time Limit (s)':<15} {'Runs':>8} {'Best':>10} {'Avg':>10} {'Worst':>10} {'StdDev':>10}")
    print(f"{'-'*15} {'-'*8} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    
    for time_limit in sorted(by_time.keys()):
        costs = by_time[time_limit]
        count = len(costs)
        best = min(costs)
        avg = sum(costs) / count
        worst = max(costs)
        
        # Calculate standard deviation
        if count > 1:
            variance = sum((c - avg) ** 2 for c in costs) / (count - 1)
            stddev = variance ** 0.5
        else:
            stddev = 0.0
        
        print(f"{time_limit:<15} {count:>8} {best:>10} {avg:>10.1f} {worst:>10} {stddev:>10.2f}")


def print_seed_analysis(data: Dict):
    """Analyze impact of different random seeds."""
    results = data.get('results', [])
    successful = [r for r in results if r.get('success', False)]
    
    if not successful:
        return
    
    # Group by seed
    by_seed = {}
    for result in successful:
        seed = result.get('config', {}).get('seed', 0)
        if seed not in by_seed:
            by_seed[seed] = []
        by_seed[seed].append(result.get('total_cost', 0))
    
    if len(by_seed) <= 1:
        return  # Skip if only one seed
    
    print(f"\n{'='*100}")
    print(f"RANDOM SEED ANALYSIS")
    print(f"{'='*100}\n")
    
    print(f"{'Seed':<10} {'Runs':>8} {'Best':>10} {'Avg':>10} {'Worst':>10}")
    print(f"{'-'*10} {'-'*8} {'-'*10} {'-'*10} {'-'*10}")
    
    for seed in sorted(by_seed.keys()):
        costs = by_seed[seed]
        count = len(costs)
        best = min(costs)
        avg = sum(costs) / count
        worst = max(costs)
        
        print(f"{seed:<10} {count:>8} {best:>10} {avg:>10.1f} {worst:>10}")


def print_s7_focus(data: Dict):
    """Focus on Teacher Working Days (S7) metric."""
    results = data.get('results', [])
    successful = [r for r in results if r.get('success', False)]
    
    if not successful:
        return
    
    print(f"\n{'='*100}")
    print(f"TEACHER WORKING DAYS (S7) ANALYSIS")
    print(f"{'='*100}\n")
    
    # Sort by S7
    successful.sort(key=lambda r: r.get('soft_costs', {}).get('teacher_working_days', float('inf')))
    
    print(f"{'Rank':<6} {'Time(s)':>8} {'Seed':>6} {'S7':>5} {'S8':>5} {'S6':>5} {'Total':>7} {'Output File':<30}")
    print(f"{'-'*6} {'-'*8} {'-'*6} {'-'*5} {'-'*5} {'-'*5} {'-'*7} {'-'*30}")
    
    for rank, result in enumerate(successful[:10], 1):  # Top 10
        config = result.get('config', {})
        soft_costs = result.get('soft_costs', {})
        
        time_limit = config.get('time_limit', 0)
        seed = config.get('seed', 0)
        s7 = soft_costs.get('teacher_working_days', 0)
        s8 = soft_costs.get('teacher_preferences', 0)
        s6 = soft_costs.get('teacher_consolidation', 0)
        total = result.get('total_cost', 0)
        output = config.get('output_file', 'N/A')
        
        marker = "⭐" if rank == 1 else "  "
        print(f"{marker}{rank:<4} {time_limit:>8} {seed:>6} {s7:>5} {s8:>5} {s6:>5} {total:>7} {output:<30}")


def export_csv(data: Dict, output_path: Path):
    """Export results to CSV for external analysis."""
    results = data.get('results', [])
    successful = [r for r in results if r.get('success', False)]
    
    if not successful:
        print("No data to export.")
        return
    
    import csv
    
    with output_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            'time_limit', 'seed', 'total_cost', 'elapsed_time',
            's7_working_days', 's8_preferences', 's6_consolidation',
            'curriculum_compactness', 'lecture_consecutiveness', 'room_stability',
            'output_file'
        ])
        
        # Data rows
        for result in successful:
            config = result.get('config', {})
            soft_costs = result.get('soft_costs', {})
            
            writer.writerow([
                config.get('time_limit', 0),
                config.get('seed', 0),
                result.get('total_cost', 0),
                result.get('elapsed_time', 0),
                soft_costs.get('teacher_working_days', 0),
                soft_costs.get('teacher_preferences', 0),
                soft_costs.get('teacher_consolidation', 0),
                soft_costs.get('curriculum_compactness', 0),
                soft_costs.get('lecture_consecutiveness', 0),
                soft_costs.get('room_stability', 0),
                config.get('output_file', '')
            ])
    
    print(f"\n✓ CSV exported to: {output_path}")


def plot_constraint_violations(data: Dict, output_dir: Path):
    """Plot constraint violations for each solution (only non-zero constraints).
    
    Args:
        data: Benchmark results data
        output_dir: Directory to save plots
    """
    if not MATPLOTLIB_AVAILABLE:
        print("\n⚠️  Matplotlib not available. Skipping charts.")
        return
    
    results = data.get('results', [])
    successful = [r for r in results if r.get('success', False)]
    
    if not successful:
        print("\nNo successful runs to plot.")
        return
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Sort by total cost for better visualization
    successful.sort(key=lambda r: r.get('total_cost', float('inf')))
    
    # Take top 10 for clarity (or all if less than 10)
    top_n = min(10, len(successful))
    top_results = successful[:top_n]
    
    # Prepare data
    labels = []
    hard_constraints = {
        'Lectures': [],
        'Conflicts': [],
        'Availability': [],
        'RoomOccupation': [],
        'RoomType': [],
        'Equipment': []
    }
    soft_constraints = {
        'RoomCapacity': [],
        'MinWorkingDays': [],
        'CurriculumCompact': [],
        'RoomStability': [],
        'LectureConsec': [],
        'TeacherConsol (S6)': [],
        'TeacherWorkDays (S7)': [],
        'TeacherPref (S8)': []
    }
    
    for result in top_results:
        config = result.get('config', {})
        time_limit = config.get('time_limit', 0)
        seed = config.get('seed', 0)
        labels.append(f"{time_limit}s\nseed={seed}")
        
        # Hard violations
        hard_viols = result.get('hard_violations', {})
        hard_constraints['Lectures'].append(hard_viols.get('lectures', 0))
        hard_constraints['Conflicts'].append(hard_viols.get('conflicts', 0))
        hard_constraints['Availability'].append(hard_viols.get('availability', 0))
        hard_constraints['RoomOccupation'].append(hard_viols.get('room_occupation', 0))
        hard_constraints['RoomType'].append(hard_viols.get('room_type', 0))
        hard_constraints['Equipment'].append(hard_viols.get('equipment', 0))
        
        # Soft costs
        soft_costs = result.get('soft_costs', {})
        soft_constraints['RoomCapacity'].append(soft_costs.get('room_capacity', 0))
        soft_constraints['MinWorkingDays'].append(soft_costs.get('min_working_days', 0))
        soft_constraints['CurriculumCompact'].append(soft_costs.get('curriculum_compactness', 0))
        soft_constraints['RoomStability'].append(soft_costs.get('room_stability', 0))
        soft_constraints['LectureConsec'].append(soft_costs.get('lecture_consecutiveness', 0))
        soft_constraints['TeacherConsol (S6)'].append(soft_costs.get('teacher_consolidation', 0))
        soft_constraints['TeacherWorkDays (S7)'].append(soft_costs.get('teacher_working_days', 0))
        soft_constraints['TeacherPref (S8)'].append(soft_costs.get('teacher_preferences', 0))
    
    # Filter: Only keep constraints with at least one non-zero value
    hard_to_plot = {k: v for k, v in hard_constraints.items() if any(val > 0 for val in v)}
    soft_to_plot = {k: v for k, v in soft_constraints.items() if any(val > 0 for val in v)}
    
    # Determine number of subplots needed
    n_plots = 0
    if hard_to_plot:
        n_plots += 1
    if soft_to_plot:
        n_plots += 1
    
    if n_plots == 0:
        print("\n✓ No constraint violations found (all constraints = 0). No charts needed.")
        return
    
    # Create figure with subplots
    fig, axes = plt.subplots(n_plots, 1, figsize=(14, 6 * n_plots))
    if n_plots == 1:
        axes = [axes]  # Make it a list for consistent indexing
    
    plot_idx = 0
    
    # Plot hard constraints if any violations exist
    if hard_to_plot:
        ax = axes[plot_idx]
        plot_idx += 1
        
        x_pos = range(len(labels))
        width = 0.12
        colors_hard = ['#d62728', '#ff7f0e', '#e377c2', '#bcbd22', '#8c564b', '#9467bd']
        
        for i, (constraint, values) in enumerate(hard_to_plot.items()):
            offset = width * (i - len(hard_to_plot) / 2)
            ax.bar([x + offset for x in x_pos], values, width, 
                   label=constraint, color=colors_hard[i % len(colors_hard)])
        
        ax.set_xlabel('Configuration', fontsize=12, fontweight='bold')
        ax.set_ylabel('Violation Count', fontsize=12, fontweight='bold')
        ax.set_title('Hard Constraint Violations (MUST BE ZERO)', 
                     fontsize=14, fontweight='bold', color='red')
        ax.set_xticks(x_pos)
        ax.set_xticklabels(labels, fontsize=9)
        ax.legend(loc='upper right', fontsize=10)
        ax.grid(axis='y', alpha=0.3)
    
    # Plot soft constraints if any costs exist
    if soft_to_plot:
        ax = axes[plot_idx]
        
        x_pos = range(len(labels))
        width = 0.10
        colors_soft = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                       '#8c564b', '#e377c2', '#7f7f7f']
        
        for i, (constraint, values) in enumerate(soft_to_plot.items()):
            offset = width * (i - len(soft_to_plot) / 2)
            ax.bar([x + offset for x in x_pos], values, width, 
                   label=constraint, color=colors_soft[i % len(colors_soft)])
        
        ax.set_xlabel('Configuration', fontsize=12, fontweight='bold')
        ax.set_ylabel('Cost', fontsize=12, fontweight='bold')
        ax.set_title('Soft Constraint Costs (Minimize)', 
                     fontsize=14, fontweight='bold', color='orange')
        ax.set_xticks(x_pos)
        ax.set_xticklabels(labels, fontsize=9)
        ax.legend(loc='upper right', fontsize=10, ncol=2)
        ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    output_file = output_dir / "constraint_violations.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"\n✓ Constraint violations chart saved to: {output_file}")
    
    # Also create a focused S7/S8/S6 chart if they have values
    teacher_constraints = {
        'S6: Teacher Consolidation': soft_constraints['TeacherConsol (S6)'],
        'S7: Teacher Working Days': soft_constraints['TeacherWorkDays (S7)'],
        'S8: Teacher Preferences': soft_constraints['TeacherPref (S8)']
    }
    teacher_to_plot = {k: v for k, v in teacher_constraints.items() if any(val > 0 for val in v)}
    
    if teacher_to_plot:
        fig, ax = plt.subplots(figsize=(14, 6))
        
        x_pos = range(len(labels))
        width = 0.25
        colors_teacher = ['#8c564b', '#d62728', '#ff7f0e']
        
        for i, (constraint, values) in enumerate(teacher_to_plot.items()):
            offset = width * (i - len(teacher_to_plot) / 2)
            ax.bar([x + offset for x in x_pos], values, width, 
                   label=constraint, color=colors_teacher[i % len(colors_teacher)])
        
        ax.set_xlabel('Configuration', fontsize=12, fontweight='bold')
        ax.set_ylabel('Cost', fontsize=12, fontweight='bold')
        ax.set_title('Teacher-Related Constraints (S6, S7, S8)', 
                     fontsize=14, fontweight='bold')
        ax.set_xticks(x_pos)
        ax.set_xticklabels(labels, fontsize=9)
        ax.legend(loc='upper right', fontsize=11)
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        teacher_output = output_dir / "teacher_constraints.png"
        plt.savefig(teacher_output, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Teacher constraints chart saved to: {teacher_output}")


def main():
    parser = argparse.ArgumentParser(description="Visualize benchmark results")
    parser.add_argument("--input", type=str, default="benchmark_results.json",
                       help="Input JSON file from benchmark_runner.py")
    parser.add_argument("--csv", type=str, default=None,
                       help="Export to CSV file (optional)")
    parser.add_argument("--charts", action="store_true",
                       help="Generate constraint violation charts (requires matplotlib)")
    parser.add_argument("--output-dir", type=str, default="benchmark_charts",
                       help="Directory for chart output (default: benchmark_charts)")
    
    args = parser.parse_args()
    
    # Load results
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)
    
    data = load_results(input_path)
    
    # Print all analyses
    print_comparison_table(data)
    print_best_vs_worst(data)
    print_time_analysis(data)
    print_seed_analysis(data)
    print_s7_focus(data)
    
    # Generate charts if requested
    if args.charts:
        output_dir = Path(args.output_dir)
        plot_constraint_violations(data, output_dir)
    
    # Export CSV if requested
    if args.csv:
        csv_path = Path(args.csv)
        export_csv(data, csv_path)


if __name__ == "__main__":
    main()
