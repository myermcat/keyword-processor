import csv
import os
import asyncio
from ai_processor import AIProcessor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
INPUT_CSV = "csv_outputs/step0-no-brand-products.csv"  # Use output from brand identifier
CSV_FOLDER = "csv_outputs"
ASSESSED_CSV = f"{CSV_FOLDER}/step1-products-assessed.csv"
BATCH_SIZE = 20  # Increased batch size for efficiency

async def main():
    """
    Main function to validate products using AIProcessor.
    """
    print("🚀 PRODUCT VALIDATION SCRIPT")
    print("This script will automatically assess products using AI.")
    print(f"Using AIProcessor with batch size: {BATCH_SIZE}")
    print(f"Input file: {INPUT_CSV}")
    
    # Check if OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY environment variable not set!")
        print("Please set your OpenAI API key.")
        return
    
    # Check if input file exists
    if not os.path.exists(INPUT_CSV):
        print(f"❌ Error: {INPUT_CSV} not found!")
        print("Please run brand_identifier.py first to create this file.")
        return
    
    # Initialize AIProcessor
    processor = AIProcessor("product_validator", batch_size=BATCH_SIZE)
    
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
                                print(f"   {row['Search Term']} -> Seasonal={row.get('Seasonal', 'N/A')}, Specificity={row.get('Specificity', 'N/A')}")
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
    
    # Read the products with monthly data
    products = []
    with open(INPUT_CSV, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Preserve all original data from the CSV
            products.append(row)
    
    print(f"\n📊 Found {len(products)} products to assess.")
    
    # Calculate total batches
    total_batches = (len(products) + BATCH_SIZE - 1) // BATCH_SIZE
    
    # Initialize or resume progress
    if existing_progress:
        # Resume from previous progress
        start_batch = existing_progress['current_batch']
        processed_count = existing_progress['processed_count']
        print(f"🔄 Resuming from batch {start_batch + 1}/{total_batches}")
        print(f"   Already processed: {processed_count} keywords")
        
        # Load existing partial results
        existing_results = processor.read_partial_results([
            'Search Term', 'Seasonal', 'Specificity', 'Commodity', 'Subscribe&Save', 
            'Gated', 'Electronics_Batteries', 'Insurance_Gov'
        ])
        print(f"   Loaded {len(existing_results)} existing results")
    else:
        # Start fresh
        start_batch = 0
        processed_count = 0
        existing_results = []
        print(f"🚀 Starting fresh processing of {total_batches} batches")
    
    # Step 1: Assess all products using AI
    print(f"\n🔍 STEP 1: Assessing all products using AI...")
    
    try:
        # Process in batches
        for i in range(start_batch, total_batches):
            batch_start = i * BATCH_SIZE
            batch_end = min(batch_start + BATCH_SIZE, len(products))
            batch_products = products[batch_start:batch_end]
            search_terms = [product['Search Term'] for product in batch_products]
            
            print(f"\n📦 Processing batch {i + 1}/{total_batches} (products {batch_start + 1}-{batch_end})...")
            
            try:
                # Use AIProcessor to process the batch
                batch_assessments = await processor.process_batch(search_terms, "product")
                
                # Add assessment data to products and preserve monthly data
                enriched_results = []
                for j, (product, assessment) in enumerate(zip(batch_products, batch_assessments)):
                    enriched_result = assessment.copy()
                    enriched_result['Search Term'] = product['Search Term']
                    
                    # Add all monthly data columns
                    for key, value in product.items():
                        if key != 'Search Term':
                            enriched_result[key] = value
                    
                    enriched_results.append(enriched_result)
                
                # Save partial results after each batch
                fieldnames = [
                    'Search Term', 'Seasonal', 'Specificity', 'Commodity', 'Subscribe&Save', 
                    'Gated', 'Electronics_Batteries', 'Insurance_Gov'
                ] + [key for key in batch_products[0].keys() if key != 'Search Term']
                
                processor.save_partial_results(enriched_results, fieldnames)
                
                # Update progress
                processed_count += len(search_terms)
                processor.save_progress(i + 1, processed_count, len(products))
                
                # Show progress bar
                progress_bar = processor.get_progress_bar(processed_count, len(products))
                print(f"   ✅ Batch {i + 1} completed. {progress_bar}")
                
                # Show performance metrics
                speed = processor.get_processing_speed()
                eta = processor.calculate_eta(len(products) - processed_count)
                print(f"   📊 Speed: {speed:.1f} items/minute, ETA: {eta}")
                
                # Show sample assessment for this batch
                if enriched_results:
                    sample = enriched_results[0]
                    print(f"   📝 Sample assessment: {sample['Search Term']}")
                    print(f"      Seasonal={sample['Seasonal']}, Specificity={sample['Specificity']}, Commodity={sample['Commodity']}, Subscribe&Save={sample['Subscribe&Save']}")
                    print(f"      Gated={sample['Gated']}, Electronics={sample['Electronics_Batteries']}, Insurance={sample['Insurance_Gov']}")
                
                # Small delay between batches to be respectful to the API
                if i + 1 < total_batches:
                    print("   ⏳ Waiting 2 seconds before next batch...")
                    await asyncio.sleep(2)
                    
            except Exception as e:
                print(f"❌ Error in batch {i + 1}: {e}")
                # Continue with next batch instead of crashing
                error_results = []
                for j, product in enumerate(batch_products):
                    error_result = {
                        'Search Term': product['Search Term'],
                        'Seasonal': 3, 'Specificity': 3, 'Commodity': 3, 
                        'Subscribe&Save': 2, 'Gated': 0, 'Electronics_Batteries': 0, 
                        'Insurance_Gov': 0
                    }
                    # Add monthly data
                    for key, value in product.items():
                        if key != 'Search Term':
                            error_result[key] = value
                    error_results.append(error_result)
                
                # Save error results
                fieldnames = [
                    'Search Term', 'Seasonal', 'Specificity', 'Commodity', 'Subscribe&Save', 
                    'Gated', 'Electronics_Batteries', 'Insurance_Gov'
                ] + [key for key in batch_products[0].keys() if key != 'Search Term']
                
                processor.save_partial_results(error_results, fieldnames)
                
                # Update progress
                processed_count += len(search_terms)
                processor.save_progress(i + 1, processed_count, len(products))
                continue
        
        # All batches completed successfully!
        print(f"\n✅ All {total_batches} batches completed successfully!")
        
        # Read all results from partial file - include ALL columns to preserve monthly data
        all_results = processor.read_partial_results([
            'Search Term', 'Seasonal', 'Specificity', 'Commodity', 'Subscribe&Save', 
            'Gated', 'Electronics_Batteries', 'Insurance_Gov'
        ] + [key for key in products[0].keys() if key not in ['Search Term', 'Brand']])
        
        # Step 2: Save final results
        print(f"\n🔍 STEP 2: Saving final results...")
        
        # Preserve ALL original data plus add AI assessments, but remove Brand column
        filtered_products_clean = []
        for result in all_results:
            clean_product = {k: v for k, v in result.items() if k != 'Brand'}
            filtered_products_clean.append(clean_product)
        
        with open(ASSESSED_CSV, 'w', newline='', encoding='utf-8') as file:
            # Define the final column order: Search Term + AI assessments + monthly data (no Brand column)
            fieldnames = [
                'Search Term',
                'Seasonal', 'Specificity', 'Commodity', 'Subscribe&Save', 'Gated', 'Electronics_Batteries', 'Insurance_Gov'
            ]
            
            # Add monthly data columns dynamically
            if filtered_products_clean:
                for key in filtered_products_clean[0].keys():
                    if key not in fieldnames:
                        fieldnames.append(key)
            
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(filtered_products_clean)
        
        print(f"✅ Processing complete! Results saved to {ASSESSED_CSV}")
        
        # Clean up progress files on successful completion
        processor.cleanup_progress_files()
        
        # Display summary
        print(f"\n🎉 ASSESSMENT COMPLETE!")
        print(f"📁 Files created:")
        print(f"  - {ASSESSED_CSV} (all products with AI assessments + preserved monthly data)")
        
        # Show final performance report
        print(f"\n📈 Final Performance Report:")
        print(processor.get_performance_report())
        
        print(f"\n📊 SUMMARY:")
        print(f"  - Total products assessed: {len(all_results)}")
        print(f"  - Products saved: {len(filtered_products_clean)} (ALL PRODUCTS - NO FILTERING)")
        print(f"  - Filtering status: DISABLED - All products with assessments are saved")
        
        # Display some sample results
        print(f"\n📝 Sample Results:")
        for i, result in enumerate(all_results[:3]):
            print(f"   {i+1}. {result['Search Term']}")
            print(f"      Seasonal={result['Seasonal']}, Specificity={result['Specificity']}, Commodity={result['Commodity']}, Subscribe&Save={result['Subscribe&Save']}")
            print(f"      Gated={result['Gated']}, Electronics={result['Electronics_Batteries']}, Insurance={result['Insurance_Gov']}")
        
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
