import csv
import os
import asyncio
from typing import List, Dict
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
INPUT_CSV = "csv_outputs/step0-no-brand-products.csv"  # Use output from brand identifier
CSV_FOLDER = "csv_outputs"
ASSESSED_CSV = f"{CSV_FOLDER}/step1-products-assessed.csv"

# Initialize OpenAI client
client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

async def assess_product_ai(search_term: str) -> Dict[str, int]:
    """
    Use OpenAI API to automatically assess a product based on the criteria from the presentation.
    Returns a dictionary with Seasonal, Specificity, Commodity, and Subscribe&Save ratings.
    """
    try:
        # Create the assessment prompt
        prompt = f"""Assess the following product keyword for e-commerce validation. 
Rate each criterion 0-5 or 0/1:

Keyword: {search_term}

1. SEASONAL DEMAND (0-5): 0=flat year, 5=strongly seasonal
2. SPECIFICITY (0-5): 0=very broad, 5=very precise
3. COMMODITY (0-5): 0=brand-owned, 5=commodity
4. SUBSCRIBE & SAVE (0-5): 0=not suitable, 5=perfect consumable
5. GATED (0/1): 1 if restricted Amazon category (OTC, medical device, adult, pesticides, hazmat, etc. — not supplements), else 0
6. ELECTRONICS/BATTERIES (0/1): 1 if electronic, battery-powered, or requires replacement heads/charging
7. INSURANCE/GOV (0/1): 1 if reimbursed by insurance or supplied free by gov programs

IMPORTANT: You MUST respond with EXACTLY 7 numbers, comma-separated (e.g., "3,5,2,4,0,1,0"). 
The response MUST include ALL 7 values: Seasonal, Specificity, Commodity, Subscribe&Save, Gated, Electronics/Batteries, Insurance/Gov Coverage."""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an e-commerce product analyst. Respond with ONLY seven numbers (0-5 for first 4, 0-1 for last 3) separated by commas, no other text."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50,
            temperature=0
        )
        
        result = response.choices[0].message.content.strip()
        ratings = [int(x.strip()) for x in result.split(',')]
        
        if len(ratings) == 7 and all(0 <= r <= 5 for r in ratings[:4]) and all(0 <= r <= 1 for r in ratings[4:]):
            return {
                'Seasonal': ratings[0],
                'Specificity': ratings[1],
                'Commodity': ratings[2],
                'Subscribe&Save': ratings[3],
                'Gated': ratings[4],
                'Electronics_Batteries': ratings[5],
                'Insurance_Gov': ratings[6]
            }
        else:
            print(f"⚠️ AI response format error for '{search_term}'. Using default values.")
            return {'Seasonal': 3, 'Specificity': 3, 'Commodity': 3, 'Subscribe&Save': 2, 'Gated': 0, 'Electronics_Batteries': 0, 'Insurance_Gov': 0}
            
    except Exception as e:
        print(f"⚠️ Error assessing '{search_term}': {e}. Using default values.")
        return {'Seasonal': 3, 'Specificity': 3, 'Commodity': 3, 'Subscribe&Save': 2, 'Gated': 0, 'Electronics_Batteries': 0, 'Insurance_Gov': 0}



async def main():
    """
    Main function to validate products.
    """
    print("🚀 PRODUCT VALIDATION SCRIPT")
    print("This script will automatically assess products using AI.")
    print(f"Input file: {INPUT_CSV}")
    
    # Check if input file exists
    if not os.path.exists(INPUT_CSV):
        print(f"❌ Error: {INPUT_CSV} not found!")
        print("Please run brand_identifier.py first to create this file.")
        return
    
    # Check if OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY environment variable not set!")
        print("Please set your OpenAI API key.")
        return
    
    # Read the products with monthly data
    products = []
    with open(INPUT_CSV, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Preserve all original data from the CSV
            products.append(row)
    
    print(f"\n📊 Found {len(products)} products to assess.")
    
    # Step 1: Assess all products using AI
    print(f"\n🔍 STEP 1: Assessing all products using AI...")
    assessed_products = []
    
    # Process products in batches to avoid overwhelming the API
    BATCH_SIZE = 10
    total_batches = (len(products) + BATCH_SIZE - 1) // BATCH_SIZE
    
    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(products))
        batch_products = products[start_idx:end_idx]
        
        print(f"\n📦 Processing batch {batch_num + 1}/{total_batches} (products {start_idx + 1}-{end_idx})")
        
        for i, product in enumerate(batch_products, start_idx + 1):
            print(f"   Product {i}/{len(products)}: {product['Search Term']}")
            assessment = await assess_product_ai(product['Search Term'])
            
            # Add assessment data to product
            product.update(assessment)
            assessed_products.append(product)
            
            print(f"      AI Assessment: Seasonal={assessment['Seasonal']}, Specificity={assessment['Specificity']}, Commodity={assessment['Commodity']}, Subscribe&Save={assessment['Subscribe&Save']}, Gated={assessment['Gated']}, Electronics_Batteries={assessment['Electronics_Batteries']}, Insurance_Gov={assessment['Insurance_Gov']}")
        
        # Small delay between batches to be respectful to the API
        if batch_num < total_batches - 1:
            print("   ⏳ Waiting 2 seconds before next batch...")
            await asyncio.sleep(2)
    
    print(f"\n✅ Step 1 complete! All products assessed.")
    
    # Step 2: Filter products based on new criteria
    print(f"\n🔍 STEP 2: Filtering products based on new validation criteria...")
    
    # SAVE ALL PRODUCTS - NO FILTERING
    filtered_products = assessed_products.copy()
    
    if not filtered_products:
        print("❌ No products found!")
        return
    
    print(f"Found {len(filtered_products)} products - ALL PRODUCTS SAVED (no filtering applied)")
    print(f"   - All products with assessments are being saved")
    print(f"   - No filtering by Seasonal, Specificity, Commodity, or Subscribe&Save")
    

    
    # Preserve ALL original data plus add AI assessments, but remove Brand column
    filtered_products_clean = []
    for product in filtered_products:
        clean_product = {k: v for k, v in product.items() if k != 'Brand'}
        filtered_products_clean.append(clean_product)
    
    with open(ASSESSED_CSV, 'w', newline='', encoding='utf-8') as file:
        # Define the final column order: Search Term + AI assessments + monthly data (no Brand column)
        fieldnames = [
            'Search Term',
            'Seasonal', 'Specificity', 'Commodity', 'Subscribe&Save', 'Gated', 'Electronics_Batteries', 'Insurance_Gov',
            '2023-August', '2023-September', '2023-October', '2023-November', '2023-December',
            '2024-January', '2024-February', '2024-March', '2024-April', '2024-May', '2024-June', '2024-July',
            '2024-August', '2024-September', '2024-October', '2024-November', '2024-December',
            '2025-January', '2025-February', '2025-March', '2025-April', '2025-May', '2025-June', '2025-July'
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered_products_clean)
    
    print(f"\n🎉 ASSESSMENT COMPLETE!")
    print(f"📁 Files created:")
    print(f"  - {ASSESSED_CSV} (all products with AI assessments + preserved monthly data)")
    
    # Display summary
    print(f"\n📊 SUMMARY:")
    print(f"  - Total products assessed: {len(assessed_products)}")
    print(f"  - Products saved: {len(filtered_products)} (ALL PRODUCTS - NO FILTERING)")
    print(f"  - Filtering status: DISABLED - All products with assessments are saved")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
