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
    print("1. Brand identification (OpenAI API)")
    print("2. Product validation (OpenAI API)")
    print("\nStarting pipeline...")
    
    # Check if required files exist
    if not os.path.exists("brand_identifier.py"):
        print("❌ brand_identifier.py not found!")
        return False
    
    if not os.path.exists("product_validator.py"):
        print("❌ product_validator.py not found!")
        return False
    
    # Check if input CSV exists
    if not os.path.exists("search_terms_sample.csv"):
        print("❌ search_terms_sample.csv not found!")
        return False
    
    # Step 1: Brand Identification
    if not run_script("brand_identifier.py", "STEP 1: Brand Identification"):
        print("❌ Pipeline failed at brand identification step!")
        return False
    
    # Step 2: Product Validation
    if not run_script("product_validator.py", "STEP 2: Product Validation"):
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
    
    print(f"\n🎯 Pipeline Summary:")
    print(f"  ✅ Brand identification completed")
    print(f"  ✅ Product validation completed")
    print(f"  📊 Check csv_outputs/ folder for results")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
