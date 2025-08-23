import csv
import time
import openai
import os
import json
from typing import List, Tuple
import asyncio
import aiohttp
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
INPUT_CSV = "search_terms_sample.csv"
CSV_FOLDER = "csv_outputs"
OUTPUT_CSV = f"{CSV_FOLDER}/step0-brand-filtered.csv"
NO_BRAND_CSV = f"{CSV_FOLDER}/step0-no-brand-products.csv"  # New file for products without brands
BATCH_SIZE = 5  # Process in small batches to avoid rate limits
DELAY_BETWEEN_BATCHES = 1  # Seconds between batches

# Progress tracking files
PROGRESS_FILE = f"{CSV_FOLDER}/progress.json"
PARTIAL_OUTPUT_CSV = f"{CSV_FOLDER}/step0-brand-filtered-PARTIAL.csv"

# Initialize OpenAI client
client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

def save_progress(current_batch: int, total_batches: int, processed_count: int, all_brands: List[str]):
    """Save current progress to allow resuming later."""
    progress_data = {
        'current_batch': current_batch,
        'total_batches': total_batches,
        'processed_count': processed_count,
        'all_brands': all_brands,
        'timestamp': time.time(),
        'input_file': INPUT_CSV
    }
    
    # Ensure csv_outputs directory exists
    os.makedirs(CSV_FOLDER, exist_ok=True)
    
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress_data, f, indent=2)
    
    print(f"💾 Progress saved: Batch {current_batch}/{total_batches} ({processed_count} keywords processed)")

def load_progress() -> dict:
    """Load existing progress if available."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r') as f:
                progress = json.load(f)
            
            # Check if this is for the same input file
            if progress.get('input_file') == INPUT_CSV:
                return progress
            else:
                print("⚠️  Progress file found but for different input file. Starting fresh.")
                return None
        except Exception as e:
            print(f"⚠️  Error loading progress file: {e}. Starting fresh.")
            return None
    return None

def save_partial_results(rows: List[dict], all_brands: List[str], headers: List[str]):
    """Save partial results to allow resuming later."""
    # Ensure csv_outputs directory exists
    os.makedirs(CSV_FOLDER, exist_ok=True)
    
    # Add brand column to rows
    enriched_rows = []
    for i, row in enumerate(rows):
        if i < len(all_brands):
            enriched_row = row.copy()
            enriched_row['Brand'] = all_brands[i]
            enriched_rows.append(enriched_row)
    
    # Write partial results
    with open(PARTIAL_OUTPUT_CSV, 'w', newline='', encoding='utf-8') as file:
        fieldnames = ['Search Term', 'Brand'] + [h for h in headers if h != 'Search Term']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(enriched_rows)
    
    print(f"💾 Partial results saved: {len(enriched_rows)} keywords with brand data")

async def identify_brand(search_term: str) -> str:
    """
    Call OpenAI API to identify if a search term contains a brand.
    Returns either the brand name or 'no'.
    """
    prompt = f"Does the following product name include a brand? {search_term}\n- If yes, return the brand name only.\n- If no, return exactly: 'no'"
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You must respond with either a brand name (single phrase) or exactly 'no'. Do not include any other text, punctuation, or explanations."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50,
            temperature=0
        )
        
        result = response.choices[0].message.content.strip().lower()
        
        # Ensure the result is either a brand name or 'no'
        if result == 'no':
            return 'no'
        else:
            # Clean up the response to get just the brand name
            return result.strip('"').strip("'").strip()
            
    except Exception as e:
        error_msg = str(e).lower()
        
        # Check for rate limit errors
        if 'rate limit' in error_msg or '429' in error_msg or 'quota' in error_msg:
            print(f"🚨 RATE LIMIT HIT for '{search_term}'. This is a critical error that requires immediate attention.")
            raise Exception("RATE_LIMIT_HIT") from e
        elif 'authentication' in error_msg or 'api key' in error_msg:
            print(f"🔑 AUTHENTICATION ERROR for '{search_term}'. Check your OpenAI API key.")
            raise Exception("AUTH_ERROR") from e
        else:
            print(f"⚠️  Error processing '{search_term}': {e}")
            return 'error'

async def process_batch(search_terms: List[str]) -> List[str]:
    """
    Process a batch of search terms concurrently.
    """
    tasks = [identify_brand(term) for term in search_terms]
    results = await asyncio.gather(*tasks)
    return results

def filter_no_brand_products(input_csv: str, output_csv: str) -> int:
    """
    Filter products with no brands from the brand_filtered.csv and save to a new CSV.
    Returns the number of no-brand products found.
    """
    no_brand_rows = []
    
    # Read the brand_filtered.csv file
    with open(input_csv, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Only keep rows where Brand is "no"
            if row['Brand'].lower() == 'no':
                no_brand_rows.append(row)
    
    # Write the filtered data to the new CSV
    if no_brand_rows:
        with open(output_csv, 'w', newline='', encoding='utf-8') as file:
            # Preserve all original columns including monthly data
            fieldnames = list(no_brand_rows[0].keys())
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(no_brand_rows)
    
    return len(no_brand_rows)

async def main():
    """
    Main function to process the CSV file.
    """
    print("🎯 BRAND IDENTIFICATION SCRIPT")
    print("This script identifies brands in product search terms using AI.")
    
    # Check for existing progress
    existing_progress = load_progress()
    
    if existing_progress:
        print(f"\n📋 EXISTING PROGRESS DETECTED!")
        print(f"   Input file: {existing_progress['input_file']}")
        print(f"   Last processed: Batch {existing_progress['current_batch']}/{existing_progress['total_batches']}")
        print(f"   Keywords processed: {existing_progress['processed_count']}")
        print(f"   Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(existing_progress['timestamp']))}")
        
        # Ask user what to do
        while True:
            choice = input("\nDo you want to:\n1. Resume from where you left off\n2. Start fresh (overwrite existing results)\n3. View partial results\nEnter choice (1/2/3): ").strip()
            
            if choice == '1':
                print("🔄 Resuming from previous progress...")
                break
            elif choice == '2':
                print("🆕 Starting fresh...")
                existing_progress = None
                break
            elif choice == '3':
                if os.path.exists(PARTIAL_OUTPUT_CSV):
                    print(f"\n📊 Partial results preview (first 5 rows):")
                    with open(PARTIAL_OUTPUT_CSV, 'r') as f:
                        reader = csv.DictReader(f)
                        for i, row in enumerate(reader):
                            if i < 5:
                                print(f"   {row['Search Term']} -> {row['Brand']}")
                            else:
                                break
                    print("   ... (showing first 5 rows)")
                else:
                    print("❌ No partial results file found.")
                continue
            else:
                print("❌ Invalid choice. Please enter 1, 2, or 3.")
    
    # Read the input CSV - handle the special structure
    rows = []
    with open(INPUT_CSV, 'r', encoding='utf-8') as file:
        # Read the first line as headers (no metadata row to skip)
        lines = file.readlines()
        if len(lines) >= 2:
            # Use the first line as headers
            header_line = lines[0].strip()
            headers = [h.strip() for h in header_line.split(',') if h.strip()]
            
            # Process data rows starting from line 2, skip empty lines
            for line in lines[1:]:
                line = line.strip()
                if line:  # Skip empty lines
                    values = [v.strip().strip('"') for v in line.split(',')]
                    if len(values) >= 1 and values[0]:  # Ensure we have at least the search term
                        # Create row with ALL original columns
                        row = {}
                        for i, header in enumerate(headers):
                            if i < len(values):
                                row[header] = values[i]
                            else:
                                row[header] = ''  # Fill missing values with empty string
                        rows.append(row)
    
    print(f"\n📊 Found {len(rows)} search terms to process")
    
    # Calculate total batches
    total_batches = (len(rows) + BATCH_SIZE - 1) // BATCH_SIZE
    
    # Initialize or resume progress
    if existing_progress:
        # Resume from previous progress
        all_brands = existing_progress['all_brands']
        start_batch = existing_progress['current_batch']
        print(f"🔄 Resuming from batch {start_batch + 1}/{total_batches}")
        print(f"   Already processed: {len(all_brands)} keywords")
    else:
        # Start fresh
        all_brands = []
        start_batch = 0
        print(f"🚀 Starting fresh processing of {total_batches} batches")
    
    print(f"\nProcessing {len(rows)} search terms...")
    
    try:
        # Process in batches
        for i in range(start_batch, total_batches):
            batch_start = i * BATCH_SIZE
            batch_end = min(batch_start + BATCH_SIZE, len(rows))
            batch = rows[batch_start:batch_end]
            search_terms = [row['Search Term'] for row in batch]
            
            print(f"\n📦 Processing batch {i + 1}/{total_batches} (keywords {batch_start + 1}-{batch_end})...")
            
            try:
                brands = await process_batch(search_terms)
                all_brands.extend(brands)
                
                # Save progress after each batch
                processed_count = len(all_brands)
                save_progress(i, total_batches, processed_count, all_brands)
                
                # Save partial results after each batch
                save_partial_results(rows, all_brands, headers)
                
                print(f"   ✅ Batch {i + 1} completed. Total processed: {processed_count}/{len(rows)}")
                
                # Add delay between batches to avoid rate limits
                if i + 1 < total_batches:
                    print(f"   ⏳ Waiting {DELAY_BETWEEN_BATCHES} seconds before next batch...")
                    await asyncio.sleep(DELAY_BETWEEN_BATCHES)
                    
            except Exception as e:
                if "RATE_LIMIT_HIT" in str(e):
                    print(f"\n🚨 RATE LIMIT HIT! Saving progress and stopping gracefully...")
                    print(f"   Progress saved: {len(all_brands)} keywords processed")
                    print(f"   You can resume later by running the script again")
                    print(f"   Partial results saved to: {PARTIAL_OUTPUT_CSV}")
                    return False
                else:
                    print(f"❌ Error in batch {i + 1}: {e}")
                    # Continue with next batch instead of crashing
                    all_brands.extend(['error'] * len(search_terms))
                    continue
        
        # All batches completed successfully
        print(f"\n✅ All {total_batches} batches completed successfully!")
        
        # Add brand column to each row
        for i, row in enumerate(rows):
            row['Brand'] = all_brands[i]
        
        # Write the final enriched data to output CSV
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as file:
            # Include Search Term first, then Brand, then all monthly data columns
            fieldnames = ['Search Term', 'Brand'] + [h for h in headers if h != 'Search Term']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"✅ Processing complete! Results saved to {OUTPUT_CSV}")
        
        # Clean up progress files on successful completion
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
        if os.path.exists(PARTIAL_OUTPUT_CSV):
            os.remove(PARTIAL_OUTPUT_CSV)
        
        # Filter products with no brands
        print(f"\n🔍 Filtering products with no brands...")
        no_brand_count = filter_no_brand_products(OUTPUT_CSV, NO_BRAND_CSV)
        
        # Calculate how many were filtered out
        branded_count = len(rows) - no_brand_count
        
        if no_brand_count > 0:
            print(f"✅ Found {no_brand_count} products with no brands. Saved to {NO_BRAND_CSV}")
            print(f"❌ Filtered out {branded_count} branded products")
            print(f"📊 Total: {len(rows)} products → {no_brand_count} kept, {branded_count} filtered out")
        else:
            print("ℹ️ No products without brands found.")
        
        # Display some results
        print("\nSample results:")
        for i, row in enumerate(rows[:5]):
            print(f"{i+1}: '{row['Search Term']}' -> Brand: '{row['Brand']}'")
        
        print(f"\n📁 Files created:")
        print(f"  - {OUTPUT_CSV} (all results)")
        print(f"  - {NO_BRAND_CSV} (no-brand products only)")
        print(f"📁 All files saved to: {CSV_FOLDER}/")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Critical error occurred: {e}")
        print(f"💾 Progress has been saved. You can resume later.")
        return False

if __name__ == "__main__":
    # Check if OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY environment variable not set!")
        print("Please set your OpenAI API key:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        exit(1)
    
    # Run the async main function
    asyncio.run(main())
