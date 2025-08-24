#!/usr/bin/env python3
"""
TREND FILTER - STEP 0
Filters products based on declining search trends and keyword specificity.

This script:
1. Reads the original CSV with monthly data
2. Filters out one-word keywords (too non-specific)
3. Calculates linear regression slope for each product (ignoring zeros)
4. Filters to keep only products with declining trends (negative slope)
5. Saves filtered results for brand identification (step 1)

The trend filtering happens BEFORE brand filtering to reduce the dataset size early.
"""

import csv
import os
import numpy as np
from typing import List, Dict, Tuple, Any
import argparse
import json

def calculate_trend_slope(monthly_data: List[str]) -> float:
    """
    Calculate linear regression slope for monthly data, ignoring zeros.
    
    Args:
        monthly_data: List of monthly search volume numbers as strings
        
    Returns:
        float: Slope of the trend line (negative = declining, positive = growing)
    """
    # Convert to numbers and filter out zeros
    numeric_data = []
    month_indices = []
    
    for i, value in enumerate(monthly_data):
        try:
            num = int(value)
            if num > 0:  # Only include non-zero values
                numeric_data.append(num)
                month_indices.append(i)
        except (ValueError, TypeError):
            continue
    
    if len(numeric_data) < 3:
        return 0.0  # Need at least 3 non-zero points for trend analysis
    
    # Calculate linear regression slope using numpy
    try:
        slope = np.polyfit(month_indices, numeric_data, 1)[0]
        return slope
    except:
        return 0.0

def filter_by_declining_trends(input_file: str, output_file: str, slope_threshold: float = 0.0) -> Dict[str, Any]:
    """
    Filter products to keep only those with declining trends and multi-word keywords.
    
    Args:
        input_file: Path to input CSV with monthly data
        output_file: Path to output CSV with filtered products
        slope_threshold: Maximum slope to keep (default 0.0 = only negative slopes)
        
    Returns:
        Dict with filtering statistics and filtered out products
    """
    stats = {
        'total_products': 0,
        'declining_trends': 0,
        'growing_trends': 0,
        'insufficient_data': 0,
        'one_word_keywords': 0,
        'filtered_out_products': [],
        'kept_products': []
    }
    
    # Read input CSV
    with open(input_file, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        
        if not fieldnames:
            raise ValueError("CSV file has no headers")
        
        # Identify monthly data columns (exclude Search Term and other non-monthly columns)
        monthly_columns = [col for col in fieldnames if col not in ['Search Term', 'Brand']]
        
        # Prepare output data
        filtered_products = []
        
        for row in reader:
            stats['total_products'] += 1
            
            # Check if it's a one-word keyword (very non-specific)
            search_term = row['Search Term'].strip()
            if ' ' not in search_term:
                stats['one_word_keywords'] += 1
                stats['filtered_out_products'].append({
                    'search_term': search_term,
                    'slope': 0,
                    'trend': 'one_word_keyword'
                })
                print(f"   🚫 ONE-WORD: {search_term} - FILTERED OUT (too non-specific)")
                continue
            
            # Extract monthly data
            monthly_data = [row[col] for col in monthly_columns]
            
            # Calculate trend slope
            slope = calculate_trend_slope(monthly_data)
            
            # Filter based on slope
            if slope <= slope_threshold:  # Keep declining or flat trends
                filtered_products.append(row)
                stats['kept_products'].append({
                    'search_term': search_term,
                    'slope': slope,
                    'trend': 'declining' if slope < 0 else 'flat'
                })
                
                if slope < 0:
                    stats['declining_trends'] += 1
                else:
                    stats['growing_trends'] += 1
                    
                # Log the trend for this product
                trend_direction = "📉 DECLINING" if slope < 0 else "➡️ FLAT"
                print(f"   {trend_direction}: {search_term} (slope: {slope:.3f})")
            else:
                stats['growing_trends'] += 1
                stats['filtered_out_products'].append({
                    'search_term': search_term,
                    'slope': slope,
                    'trend': 'growing'
                })
                print(f"   📈 GROWING: {search_term} (slope: {slope:.3f}) - FILTERED OUT")
    
    # Write filtered results
    with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered_products)
    
    return stats

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Filter products by declining search trends and keyword specificity')
    parser.add_argument('--input', default='search_terms_sample.csv', 
                       help='Input CSV file path')
    parser.add_argument('--output', default='csv_outputs/step0-trend-filtered.csv',
                       help='Output CSV file path')
    parser.add_argument('--slope-threshold', type=float, default=0.0,
                       help='Maximum slope to keep (default: 0.0 = only negative slopes)')
    
    args = parser.parse_args()
    
    print("🔍 TREND FILTER - STEP 0")
    print("=" * 50)
    print(f"Input file: {args.input}")
    print(f"Output file: {args.output}")
    print(f"Slope threshold: {args.slope_threshold} (keep slopes ≤ {args.slope_threshold})")
    print()
    
    # Check if input file exists
    if not os.path.exists(args.input):
        print(f"❌ Error: Input file '{args.input}' not found!")
        return
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    print("🚀 Starting trend filtering...")
    print()
    
    try:
        # Filter products by declining trends
        stats = filter_by_declining_trends(args.input, args.output, args.slope_threshold)
        
        # Save detailed filtering statistics
        stats_file = "csv_outputs/step0-trend-filtered_stats.json"
        stats_file_pipeline = "csv_outputs/step0_trend_stats_for_pipeline.json"  # For pipeline to read

        # Save stats for immediate cleanup
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2)

        # Save stats for pipeline (won't be cleaned up)
        with open(stats_file_pipeline, 'w') as f:
            json.dump(stats, f, indent=2)

        print(f"📁 Filtered results saved to: {args.output}")
        print(f"📊 Detailed stats saved to: {stats_file}")

        # Clean up immediate stats file after successful completion
        print(f"\n🧹 Cleaning up temporary stats file...")
        try:
            os.remove(stats_file)
            print(f"   ✅ Removed: {stats_file}")
        except Exception as e:
            print(f"   ⚠️ Warning: Could not remove stats file: {e}")

        print(f"🔄 Next step: Run step1_brand_identifier.py on the filtered results")
        
    except Exception as e:
        print(f"❌ Error during trend filtering: {e}")
        return

if __name__ == "__main__":
    main()
