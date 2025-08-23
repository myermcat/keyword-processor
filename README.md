# Product Validator Analytics

A comprehensive e-commerce product validation system that uses AI to assess products for market opportunities.

## 🚀 Features

### Core Functionality
- **Brand Identification**: Automatically identifies branded vs. generic products using AI
- **Product Assessment**: AI-powered evaluation of products across 7 key criteria
- **Batch Processing**: Efficient processing of large datasets with rate limiting
- **Resume Functionality**: Robust crash recovery and progress tracking
- **Pipeline Automation**: Complete workflow from raw data to validated products

### AI Assessment Criteria
1. **Seasonal Demand** (0-5): 0=flat year, 5=strongly seasonal
2. **Specificity** (0-5): 0=very broad, 5=very precise
3. **Commodity Level** (0-5): 0=brand-owned, 5=commodity
4. **Subscribe & Save** (0-5): 0=not suitable, 5=perfect consumable
5. **Gated** (0/1): 1 if restricted Amazon category, else 0
6. **Electronics/Batteries** (0/1): 1 if electronic/battery-powered, else 0
7. **Insurance/Gov** (0/1): 1 if reimbursed by insurance or supplied free by gov programs

## 📁 File Structure

```
product-validator_analytics/
├── brand_identifier.py          # Brand identification with resume functionality
├── product_validator.py         # AI product assessment
├── pipeline.py                  # Automated workflow runner
├── search_terms_sample.csv      # Input data (Search Term + monthly data)
├── csv_outputs/                 # Output directory
│   ├── step0-brand-filtered.csv        # All products with brand data
│   ├── step0-no-brand-products.csv     # Filtered no-brand products
│   ├── step1-products-assessed.csv     # Final output with AI assessments
│   ├── progress.json                   # Progress tracking (auto-created)
│   └── step0-brand-filtered-PARTIAL.csv # Partial results (auto-created)
└── README.md                    # This file
```

## 🔧 Configuration

### Environment Variables
- `OPENAI_API_KEY`: Your OpenAI API key (required)

### Script Configuration
- `BATCH_SIZE`: Number of terms processed concurrently (default: 5)
- `DELAY_BETWEEN_BATCHES`: Delay between batches in seconds (default: 1)
- `INPUT_CSV`: Input file path (default: "search_terms_sample.csv")
- `CSV_FOLDER`: Output directory (default: "csv_outputs")

## 🚀 Usage

### Quick Start
1. **Set your OpenAI API key:**
   ```bash
   export OPENAI_API_KEY='your-api-key-here'
   ```

2. **Run the complete pipeline:**
   ```bash
   python3 pipeline.py
   ```

### Individual Scripts

#### Brand Identification
```bash
python3 brand_identifier.py
```
- Processes input CSV to identify branded vs. generic products
- **Resume functionality**: Automatically detects and offers to resume from previous runs
- **Progress tracking**: Saves progress after each batch
- **Crash recovery**: Gracefully handles rate limits and errors

#### Product Validation
```bash
python3 product_validator.py
```
- Assesses products using AI across 7 criteria
- Processes in batches of 10 with 2-second delays
- Preserves all monthly data while adding AI assessments

## 🔄 Resume Functionality

### How It Works
The brand identifier automatically detects when you're resuming a previous run and offers you options:

1. **Resume from where you left off** - Continues processing from the last completed batch
2. **Start fresh** - Overwrites existing results and starts over
3. **View partial results** - Shows what was already processed

### Progress Tracking Files
- **`progress.json`**: Tracks current batch, total processed, timestamps
- **`step0-brand-filtered-PARTIAL.csv`**: Partial results saved after each batch
- **Auto-cleanup**: Progress files are removed when processing completes successfully

### Crash Recovery Scenarios
- **Rate limit hit**: Progress saved, graceful exit with clear instructions
- **Mac sleep/crash**: Progress saved, resume from exact failure point
- **API errors**: Individual batch errors logged, processing continues
- **Manual interruption**: Progress saved, can resume later

### Example Resume Session
```
📋 EXISTING PROGRESS DETECTED!
   Input file: search_terms_sample.csv
   Last processed: Batch 45/2600
   Keywords processed: 225
   Timestamp: 2024-01-15 14:30:25

Do you want to:
1. Resume from where you left off
2. Start fresh (overwrite existing results)
3. View partial results
Enter choice (1/2/3): 1

🔄 Resuming from batch 46/2600
   Already processed: 225 keywords
```

## 📊 Performance & Scaling

### Processing Times
- **36 keywords**: ~8 minutes (8 batches × 1 second delay)
- **13,000 keywords**: ~50 minutes (2,600 batches × 1 second delay)
- **100,000 keywords**: ~6 hours (20,000 batches × 1 second delay)

### Optimization Options
- **Increase batch size**: Change `BATCH_SIZE` from 5 to 10
- **Reduce delays**: Change `DELAY_BETWEEN_BATCHES` from 1 to 0.5 seconds
- **Combined optimization**: 10 batches + 0.5s delay = ~2.5x faster

### Memory Usage
- **Current approach**: All data stored in RAM (efficient for <100k keywords)
- **Streaming approach**: Row-by-row processing (better for >100k keywords)
- **Typical usage**: 13k keywords ≈ 50-100 MB RAM

## 🛡️ Error Handling

### Rate Limit Detection
- **Automatic detection** of OpenAI rate limit errors
- **Progress preservation** before graceful exit
- **Clear instructions** for resuming later

### API Error Handling
- **Individual batch errors** don't crash the entire process
- **Error logging** for debugging
- **Graceful degradation** with error placeholders

### File System Safety
- **Partial results** saved after each batch
- **Progress tracking** with timestamps
- **Input file validation** to prevent corruption

## 🔍 Troubleshooting

### Common Issues
1. **Rate limit hit**: Script saves progress and exits gracefully
2. **API key issues**: Check environment variable and API key validity
3. **File not found**: Ensure input CSV exists and has correct format
4. **Memory issues**: For very large datasets, consider streaming approach

### Recovery Steps
1. **Check progress files** in `csv_outputs/` directory
2. **Verify API key** and rate limit status
3. **Run script again** and choose resume option
4. **Monitor progress** with detailed logging

## 📈 Future Enhancements

### Planned Features
- **Streaming processing** for datasets >100k keywords
- **Advanced rate limit handling** with exponential backoff
- **Progress visualization** with real-time charts
- **Cloud deployment** for enterprise-scale processing

### Customization Options
- **Configurable assessment criteria** via JSON files
- **Multiple AI model support** (GPT-4, Claude, etc.)
- **Custom filtering rules** for specific business needs
- **Export formats** (Excel, JSON, API endpoints)

## 🤝 Contributing

This system is designed for e-commerce product research and validation. Feel free to adapt it for your specific needs and contribute improvements.

## 📄 License

Use this system responsibly and in accordance with OpenAI's terms of service.
