import csv
import os
import asyncio
from ai_processor import AIProcessor
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
INPUT_CSV = "search_terms_sample.csv"
CSV_FOLDER = "csv_outputs"
OUTPUT_CSV = f"{CSV_FOLDER}/step0-brand-filtered.csv"
NO_BRAND_CSV = f"{CSV_FOLDER}/step0-no-brand-products.csv"
BATCH_SIZE = 20  # Increased batch size for efficiency

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
    Main function to process the CSV file using AIProcessor.
    """
    print("🎯 BRAND IDENTIFICATION SCRIPT")
    print("This script identifies brands in product search terms using AI.")
    print(f"Using AIProcessor with batch size: {BATCH_SIZE}")
    
    # Check if OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY environment variable not set!")
        print("Please set your OpenAI API key:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        return False
    
    # Initialize AIProcessor
    processor = AIProcessor("brand_identifier", batch_size=BATCH_SIZE)
    
    # Check for existing progress
    existing_progress = processor.load_progress()
    
    if existing_progress:
        print(f"\n📋 EXISTING PROGRESS DETECTED!")
        print(f"   Script: {existing_progress['script_type']}")
        print(f"   Last processed: Batch {existing_progress['current_batch']}")
        print(f"   Keywords processed: {existing_progress['processed_count']}")
        print(f"   Total items: {existing_progress['total_items']}")
        print(f"   ETA: {existing_progress.get('eta', 'Unknown')}")
        print(f"   Processing speed: {existing_progress.get('processing_speed', 0):.1f} items/minute")
        
        # Ask user what to do
        while True:
            choice = input("\nDo you want to:\n1. Resume from where you left off\n2. Start fresh (overwrite existing results)\n3. View partial results\n4. View detailed progress\nEnter choice (1/2/3/4): ").strip()
            
            if choice == '1':
                print("🔄 Resuming from previous progress...")
                break
            elif choice == '2':
                print("🆕 Starting fresh...")
                existing_progress = None
                processor.cleanup_progress_files()
                break
            elif choice == '3':
                if os.path.exists(processor.partial_output_file):
                    print(f"\n📊 Partial results preview (first 5 rows):")
                    with open(processor.partial_output_file, 'r') as f:
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
            elif choice == '4':
                print("\n📊 Detailed Progress Summary:")
                print(processor.get_progress_summary())
                continue
            else:
                print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")
    
    # Read the input CSV - handle the special structure
    rows = []
    with open(INPUT_CSV, 'r', encoding='utf-8') as file:
        # Read the first line as headers
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
        start_batch = existing_progress['current_batch']
        processed_count = existing_progress['processed_count']
        print(f"🔄 Resuming from batch {start_batch + 1}/{total_batches}")
        print(f"   Already processed: {processed_count} keywords")
        
        # Load existing partial results
        existing_results = processor.read_partial_results(['Search Term', 'Brand'] + [h for h in headers if h != 'Search Term'])
        print(f"   Loaded {len(existing_results)} existing results")
    else:
        # Start fresh
        start_batch = 0
        processed_count = 0
        existing_results = []
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
                # Use AIProcessor to process the batch
                batch_results = await processor.process_batch(search_terms, "brand")
                
                # Add monthly data to each result
                enriched_results = []
                for j, result in enumerate(batch_results):
                    if j < len(batch):
                        enriched_result = result.copy()
                        # Add all monthly data columns
                        for header in headers:
                            if header != 'Search Term':
                                enriched_result[header] = batch[j].get(header, '')
                        enriched_results.append(enriched_result)
                
                # Save partial results after each batch
                fieldnames = ['Search Term', 'Brand'] + [h for h in headers if h != 'Search Term']
                processor.save_partial_results(enriched_results, fieldnames)
                
                # Update progress
                processed_count += len(search_terms)
                processor.save_progress(i + 1, processed_count, len(rows))
                
                # Show progress bar
                progress_bar = processor.get_progress_bar(processed_count, len(rows))
                print(f"   ✅ Batch {i + 1} completed. {progress_bar}")
                
                # Show performance metrics
                speed = processor.get_processing_speed()
                eta = processor.calculate_eta(len(rows) - processed_count)
                print(f"   📊 Speed: {speed:.1f} items/minute, ETA: {eta}")
                
                # Add delay between batches to avoid rate limits
                if i + 1 < total_batches:
                    print(f"   ⏳ Waiting 2 seconds before next batch...")
                    await asyncio.sleep(2)
                    
            except Exception as e:
                print(f"❌ Error in batch {i + 1}: {e}")
                # Continue with next batch instead of crashing
                error_results = []
                for j, search_term in enumerate(search_terms):
                    error_result = {
                        'Search Term': search_term,
                        'Brand': 'ERROR_API'
                    }
                    # Add monthly data
                    if j < len(batch):
                        for header in headers:
                            if header != 'Search Term':
                                error_result[header] = batch[j].get(header, '')
                    error_results.append(error_result)
                
                # Save error results
                fieldnames = ['Search Term', 'Brand'] + [h for h in headers if h != 'Search Term']
                processor.save_partial_results(error_results, fieldnames)
                
                # Update progress
                processed_count += len(search_terms)
                processor.save_progress(i + 1, processed_count, len(rows))
                continue
        
        # All batches completed successfully!
        print(f"\n✅ All {total_batches} batches completed successfully!")
        
        # Read all results from partial file
        all_results = processor.read_partial_results(['Search Term', 'Brand'] + [h for h in headers if h != 'Search Term'])
        
        # Write the final enriched data to output CSV
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as file:
            # Include Search Term first, then Brand, then all monthly data columns
            fieldnames = ['Search Term', 'Brand'] + [h for h in headers if h != 'Search Term']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_results)
        
        print(f"✅ Processing complete! Results saved to {OUTPUT_CSV}")
        
        # Clean up progress files on successful completion
        processor.cleanup_progress_files()
        
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
        for i, row in enumerate(all_results[:5]):
            print(f"{i+1}: '{row['Search Term']}' -> Brand: '{row['Brand']}'")
        
        # Show final performance report
        print(f"\n📈 Final Performance Report:")
        print(processor.get_performance_report())
        
        print(f"\n📁 Files created:")
        print(f"  - {OUTPUT_CSV} (all results)")
        print(f"  - {NO_BRAND_CSV} (no-brand products only)")
        print(f"📁 All files saved to: {CSV_FOLDER}/")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Critical error occurred: {e}")
        print(f"💾 Progress has been saved. You can resume later.")
        print(f"📊 Current progress:")
        print(processor.get_progress_summary())
        return False

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
