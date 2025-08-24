#!/usr/bin/env python3
"""
Product Validation Pipeline - Facade Script
Runs the complete pipeline: brand identification → product validation
"""

import subprocess
import sys
import os
from pathlib import Path

def run_script(script_name, description):
    """Run a Python script and handle any errors."""
    print(f"\n{'='*60}")
    print(f"🚀 {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run([sys.executable, script_name], 
                              capture_output=False, 
                              text=True, 
                              check=True)
        print(f"✅ {description} completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running {script_name}: {e}")
        return False
    except FileNotFoundError:
        print(f"❌ Script {script_name} not found!")
        return False

def main():
    """Run the complete product validation pipeline."""
    print("🎯 PRODUCT VALIDATION PIPELINE")
    print("This will run the complete workflow:")
    print("1. Trend filtering (declining trends only)")
    print("2. Brand identification (OpenAI API)")
    print("3. Product validation (OpenAI API)")
    print("\nStarting pipeline...")
    
    # Check if required files exist
    if not os.path.exists("step0_trend_filter.py"):
        print("❌ step0_trend_filter.py not found!")
        return False
    
    if not os.path.exists("step1_brand_identifier.py"):
        print("❌ step1_brand_identifier.py not found!")
        return False
    
    if not os.path.exists("step2_product_validator.py"):
        print("❌ step2_product_validator.py not found!")
        return False
    
    # Check if input CSV exists
    if not os.path.exists("search_terms_sample.csv"):
        print("❌ search_terms_sample.csv not found!")
        return False
    
    # Step 1: Trend Filtering
    if not run_script("step0_trend_filter.py", "STEP 1: Trend Filtering"):
        print("❌ Pipeline failed at trend filtering step!")
        return False
    
    # Step 2: Brand Identification
    if not run_script("step1_brand_identifier.py", "STEP 2: Brand Identification"):
        print("❌ Pipeline failed at brand identification step!")
        return False
    
    # Step 3: Product Validation
    if not run_script("step2_product_validator.py", "STEP 3: Product Validation"):
        print("❌ Pipeline failed at product validation step!")
        return False
    
    # Pipeline completed successfully
    print(f"\n{'='*60}")
    print("🎉 PIPELINE COMPLETED SUCCESSFULLY!")
    print(f"{'='*60}")
    
    # Show final results
    csv_folder = Path("csv_outputs")
    if csv_folder.exists():
        print(f"\n📁 Final Output Files:")
        for file in sorted(csv_folder.glob("*.csv")):
            size = file.stat().st_size
            print(f"  - {file.name} ({size} bytes)")
    
    # Show comprehensive filtering statistics
    print(f"\n📊 COMPREHENSIVE FILTERING STATISTICS:")
    print(f"{'='*60}")
    
    try:
        # Read trend filter stats
        trend_stats_file = Path("csv_outputs/step0_trend_stats_for_pipeline.json")
        if trend_stats_file.exists():
            import json
            with open(trend_stats_file, 'r') as f:
                trend_stats = json.load(f)
            
            print(f"\n🔍 STEP 0: TREND FILTERING")
            print(f"   📊 Total products analyzed: {trend_stats['total_products']}")
            print(f"   ✅ Products kept (declining/flat): {trend_stats['declining_trends'] + trend_stats['growing_trends']}")
            print(f"   ❌ Products filtered out: {len(trend_stats['filtered_out_products'])}")
            if trend_stats['filtered_out_products']:
                print(f"   🚫 Filtered out: {', '.join([item['search_term'] for item in trend_stats['filtered_out_products']])}")
        
        # Read brand identification stats
        brand_stats_file = Path("csv_outputs/step1_brand_stats_for_pipeline.json")
        if brand_stats_file.exists():
            with open(brand_stats_file, 'r') as f:
                brand_stats = json.load(f)
            
            print(f"\n🎯 STEP 1: BRAND IDENTIFICATION")
            print(f"   📊 Total products analyzed: {brand_stats['total_products']}")
            print(f"   ✅ Products kept (no brands): {brand_stats['no_brand_products']}")
            print(f"   ❌ Products filtered out (branded): {brand_stats['branded_products']}")
            if brand_stats['filtered_out_products']:
                print(f"   🚫 Filtered out: {', '.join(brand_stats['filtered_out_products'])}")
        
        # Read product validation stats
        assessment_stats_file = Path("csv_outputs/step2_assessment_stats_for_pipeline.json")
        if assessment_stats_file.exists():
            with open(assessment_stats_file, 'r') as f:
                assessment_stats = json.load(f)
            
            print(f"\n🤖 STEP 2: PRODUCT VALIDATION")
            print(f"   📊 Total products assessed: {assessment_stats['total_products_assessed']}")
            print(f"   ✅ Products saved: {assessment_stats['products_saved']}")
            print(f"   🔧 Assessment fields: {', '.join(assessment_stats['assessment_fields'])}")
        
        # Show final summary
        print(f"\n📈 FINAL PIPELINE SUMMARY:")
        print(f"   🚀 Original dataset: {trend_stats.get('total_products', 'Unknown')} products")
        print(f"   📉 After trend filter: {trend_stats.get('declining_trends', 0) + trend_stats.get('growing_trends', 0)} products")
        print(f"   🚫 After brand filter: {brand_stats.get('no_brand_products', 0) if 'brand_stats' in locals() else 'Unknown'} products")
        print(f"   ✅ Final output: {assessment_stats.get('products_saved', 0) if 'assessment_stats' in locals() else 'Unknown'} products")
        
        # Calculate and display detailed filtering statistics with percentages
        if 'trend_stats' in locals() and 'brand_stats' in locals() and 'assessment_stats' in locals():
            original_count = trend_stats.get('total_products', 0)
            after_trend = trend_stats.get('declining_trends', 0) + trend_stats.get('growing_trends', 0)
            after_brand = brand_stats.get('no_brand_products', 0)
            final_count = assessment_stats.get('products_saved', 0)
            
            print(f"\n📊 DETAILED FILTERING BREAKDOWN:")
            print(f"   🔍 STEP 0: TREND FILTERING")
            print(f"      📥 Input: {original_count} products")
            print(f"      📤 Output: {after_trend} products")
            print(f"      🚫 Filtered out: {original_count - after_trend} products ({(original_count - after_trend) / original_count * 100:.1f}%)")
            
            print(f"   🎯 STEP 1: BRAND IDENTIFICATION")
            print(f"      📥 Input: {after_trend} products")
            print(f"      📤 Output: {after_brand} products")
            print(f"      🚫 Filtered out: {after_trend - after_brand} products ({(after_trend - after_brand) / after_trend * 100:.1f}% of step input)")
            
            print(f"   🤖 STEP 2: PRODUCT VALIDATION")
            print(f"      📥 Input: {after_brand} products")
            print(f"      📤 Output: {final_count} products")
            print(f"      🚫 Filtered out: {after_brand - final_count} products ({(after_brand - final_count) / after_brand * 100:.1f}% of step input)")
            
            print(f"\n🎯 OVERALL RESULTS:")
            print(f"   🚀 Original dataset: {original_count} products")
            print(f"   ✅ Final output: {final_count} products")
            print(f"   🚫 Total filtered out: {original_count - final_count} products")
            print(f"   📊 Success rate: {final_count / original_count * 100:.1f}% of original dataset")
        
        # Clean up pipeline stats files after displaying summary
        print(f"\n🧹 Cleaning up pipeline stats files...")
        try:
            if trend_stats_file.exists():
                os.remove(trend_stats_file)
                print(f"   ✅ Removed: {trend_stats_file}")
            if brand_stats_file.exists():
                os.remove(brand_stats_file)
                print(f"   ✅ Removed: {brand_stats_file}")
            if assessment_stats_file.exists():
                os.remove(assessment_stats_file)
                print(f"   ✅ Removed: {assessment_stats_file}")
        except Exception as e:
            print(f"   ⚠️ Warning: Could not remove some pipeline stats files: {e}")
        
    except Exception as e:
        print(f"⚠️ Could not read detailed statistics: {e}")
    
    print(f"\n🎯 Pipeline Summary:")
    print(f"  ✅ Trend filtering completed")
    print(f"  ✅ Brand identification completed")
    print(f"  ✅ Product validation completed")
    print(f"  📊 Check csv_outputs/ folder for results")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
