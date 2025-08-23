import asyncio
import json
import os
import time
import csv
import psutil
from typing import Dict, List, Any, Optional, Callable
from functools import wraps
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class RATE_LIMIT_HIT(Exception):
    """Custom exception for rate limit errors"""
    pass

class AUTH_ERROR(Exception):
    """Custom exception for authentication errors"""
    pass

class NETWORK_ERROR(Exception):
    """Custom exception for network errors"""
    pass

class FILE_SYSTEM_ERROR(Exception):
    """Custom exception for file system errors"""
    pass

def retry_with_exponential_backoff(max_retries: int = 5, base_delay: float = 1.0, max_delay: float = 30.0):
    """
    Decorator for exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except RATE_LIMIT_HIT as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        print(f"⚠️ Rate limit hit (attempt {attempt + 1}/{max_retries + 1}). Waiting {delay:.1f}s...")
                        await asyncio.sleep(delay)
                    else:
                        print(f"❌ Max retries ({max_retries}) exceeded for rate limit. Stopping.")
                        raise
                        
                except (NETWORK_ERROR, AUTH_ERROR) as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        print(f"⚠️ {type(e).__name__} (attempt {attempt + 1}/{max_retries + 1}). Waiting {delay:.1f}s...")
                        await asyncio.sleep(delay)
                    else:
                        print(f"❌ Max retries ({max_retries}) exceeded for {type(e).__name__}. Stopping.")
                        raise
                        
                except Exception as e:
                    # Don't retry on other exceptions
                    raise e
                    
            raise last_exception
            
        return wrapper
    return decorator

class AIProcessor:
    """
    Helper class to handle OpenAI API interactions, progress tracking, and batch processing
    for both brand_identifier and product_validator scripts.
    """
    
    def __init__(self, script_type: str, batch_size: int = 10):
        """
        Initialize the AI processor.
        
        Args:
            script_type: Either "brand_identifier" or "product_validator"
            batch_size: Number of items to process per API call
        """
        self.script_type = script_type
        self.batch_size = batch_size
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Progress tracking files
        self.progress_file = f"{script_type}_progress.json"
        self.partial_output_file = f"{script_type}_PARTIAL.csv"
        
        # Rate limiting and performance tracking
        self.requests_per_minute = 0
        self.last_request_time = 0
        self.rate_limit_occurrences = 0
        self.total_wait_time = 0
        self.start_time = time.time()
        
        # Memory and performance monitoring
        self.memory_usage = []
        self.processing_speeds = []
        self.batch_times = []
        
        # Error tracking
        self.error_counts = {
            'rate_limit': 0,
            'network': 0,
            'auth': 0,
            'parsing': 0,
            'file_system': 0
        }
        
    def get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024  # Convert to MB
        
    def log_memory_usage(self):
        """Log current memory usage."""
        memory_mb = self.get_memory_usage()
        self.memory_usage.append({
            'timestamp': time.time(),
            'memory_mb': memory_mb
        })
        
        # Keep only last 100 memory readings
        if len(self.memory_usage) > 100:
            self.memory_usage = self.memory_usage[-100:]
            
    def get_processing_speed(self) -> float:
        """Calculate processing speed (items per minute)."""
        if not self.processing_speeds:
            return 0.0
        
        # Calculate average speed from last 10 batches
        recent_speeds = self.processing_speeds[-10:]
        return sum(recent_speeds) / len(recent_speeds)
        
    def calculate_eta(self, remaining_items: int) -> str:
        """Calculate estimated time to completion."""
        speed = self.get_processing_speed()
        if speed <= 0:
            return "Unknown"
            
        remaining_minutes = remaining_items / speed
        if remaining_minutes < 60:
            return f"{remaining_minutes:.1f} minutes"
        else:
            hours = remaining_minutes / 60
            return f"{hours:.1f} hours"
            
    def log_batch_performance(self, batch_size: int, processing_time: float):
        """Log batch processing performance metrics."""
        speed = batch_size / (processing_time / 60)  # items per minute
        self.processing_speeds.append(speed)
        self.batch_times.append(processing_time)
        
        # Keep only last 50 performance readings
        if len(self.processing_speeds) > 50:
            self.processing_speeds = self.processing_speeds[-50:]
        if len(self.batch_times) > 50:
            self.batch_times = self.batch_times[-50:]
            
    def get_progress_bar(self, current: int, total: int, width: int = 50) -> str:
        """Generate a text-based progress bar."""
        progress = current / total
        filled = int(width * progress)
        bar = '█' * filled + '░' * (width - filled)
        percentage = progress * 100
        return f"[{bar}] {percentage:.1f}% ({current}/{total})"
        
    def save_progress(self, current_batch: int, processed_count: int, total_items: int):
        """Save current progress to JSON file with enhanced metrics."""
        progress_data = {
            'script_type': self.script_type,
            'current_batch': current_batch,
            'processed_count': processed_count,
            'total_items': total_items,
            'timestamp': time.time(),
            'last_update': time.strftime('%Y-%m-%d %H:%M:%S'),
            'processing_speed': self.get_processing_speed(),
            'eta': self.calculate_eta(total_items - processed_count),
            'memory_usage_mb': self.get_memory_usage(),
            'rate_limit_occurrences': self.rate_limit_occurrences,
            'total_wait_time': self.total_wait_time,
            'error_counts': self.error_counts,
            'uptime_seconds': time.time() - self.start_time
        }
        
        try:
            with open(self.progress_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving progress: {e}")
            self.error_counts['file_system'] += 1
            
    def load_progress(self) -> Optional[Dict[str, Any]]:
        """Load existing progress from JSON file."""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    progress = json.load(f)
                    
                # Restore error counts and performance metrics
                if 'error_counts' in progress:
                    self.error_counts.update(progress['error_counts'])
                if 'rate_limit_occurrences' in progress:
                    self.rate_limit_occurrences = progress['rate_limit_occurrences']
                if 'total_wait_time' in progress:
                    self.total_wait_time = progress['total_wait_time']
                    
                return progress
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"⚠️ Error loading progress: {e}")
                self.error_counts['file_system'] += 1
                return None
        return None
    
    def save_partial_results(self, results: List[Dict[str, Any]], fieldnames: List[str]):
        """Save partial results to CSV file with enhanced error handling."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.partial_output_file) if os.path.dirname(self.partial_output_file) else '.', exist_ok=True)
            
            # Write to CSV (append mode if file exists, create new if not)
            mode = 'a' if os.path.exists(self.partial_output_file) else 'w'
            
            # Use file locking to prevent corruption
            with open(self.partial_output_file, mode, newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                # Write header only if creating new file
                if mode == 'w':
                    writer.writeheader()
                
                # Write results
                writer.writerows(results)
                
            # Log memory usage after file operation
            self.log_memory_usage()
            
        except Exception as e:
            print(f"⚠️ Error saving partial results: {e}")
            self.error_counts['file_system'] += 1
            raise FILE_SYSTEM_ERROR(f"Failed to save partial results: {e}")
    
    def read_partial_results(self, fieldnames: List[str]) -> List[Dict[str, Any]]:
        """Read existing partial results from CSV file."""
        if not os.path.exists(self.partial_output_file):
            return []
            
        try:
            results = []
            with open(self.partial_output_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # Validate that all required fields are present
                missing_fields = set(fieldnames) - set(reader.fieldnames or [])
                if missing_fields:
                    print(f"⚠️ Warning: Missing fields in partial results: {missing_fields}")
                
                for row in reader:
                    # Ensure all required fields are present
                    clean_row = {}
                    for field in fieldnames:
                        clean_row[field] = row.get(field, '')
                    results.append(clean_row)
                    
            return results
            
        except Exception as e:
            print(f"⚠️ Error reading partial results: {e}")
            self.error_counts['file_system'] += 1
            return []
    
    @retry_with_exponential_backoff(max_retries=5, base_delay=1.0, max_delay=30.0)
    async def process_brand_batch(self, keywords: List[str]) -> List[Dict[str, str]]:
        """
        Process a batch of keywords for brand identification with enhanced error handling.
        
        Args:
            keywords: List of keywords to process
            
        Returns:
            List of dictionaries with 'Search Term' and 'Brand' keys
        """
        batch_start_time = time.time()
        
        try:
            # Create prompt for multiple keywords
            keywords_text = ", ".join(keywords)
            prompt = f"""Are these keywords brands? Return: keyword1:brand1, keyword2:brand2, keyword3:brand3...

Keywords: {keywords_text}

Rules:
- If it's a brand name, return the brand name
- If it's not a brand, return "no"
- Separate each keyword:brand pair with commas
- Use exact keyword spelling

Example response: makeup:no, nike:nike, toothbrush:no"""

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a brand identification expert. Respond with ONLY keyword:brand pairs separated by commas, no other text."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse the response
            results = []
            pairs = [pair.strip() for pair in result.split(',')]
            
            for i, pair in enumerate(pairs):
                if ':' in pair:
                    keyword_part, brand_part = pair.split(':', 1)
                    keyword = keyword_part.strip()
                    brand = brand_part.strip()
                    
                    # Find the original keyword (case-insensitive match)
                    original_keyword = None
                    for orig_kw in keywords:
                        if orig_kw.lower() == keyword.lower():
                            original_keyword = orig_kw
                            break
                    
                    if original_keyword:
                        results.append({
                            'Search Term': original_keyword,
                            'Brand': brand
                        })
                    else:
                        # Fallback if keyword matching fails
                        results.append({
                            'Search Term': keywords[i] if i < len(keywords) else f"unknown_{i}",
                            'Brand': brand
                        })
                else:
                    # Handle malformed responses
                    results.append({
                        'Search Term': keywords[i] if i < len(keywords) else f"unknown_{i}",
                        'Brand': 'ERROR_PARSING'
                    })
            
            # Ensure we have results for all keywords
            while len(results) < len(keywords):
                missing_index = len(results)
                results.append({
                    'Search Term': keywords[missing_index],
                    'Brand': 'ERROR_PARSING'
                })
            
            # Log performance metrics
            batch_time = time.time() - batch_start_time
            self.log_batch_performance(len(keywords), batch_time)
            
            return results
            
        except Exception as e:
            # Log error and categorize
            if "rate limit" in str(e).lower() or "429" in str(e):
                self.error_counts['rate_limit'] += 1
                self.rate_limit_occurrences += 1
                raise RATE_LIMIT_HIT(f"Rate limit exceeded: {e}")
            elif "authentication" in str(e).lower() or "401" in str(e):
                self.error_counts['auth'] += 1
                raise AUTH_ERROR(f"Authentication error: {e}")
            elif "network" in str(e).lower() or "timeout" in str(e).lower():
                self.error_counts['network'] += 1
                raise NETWORK_ERROR(f"Network error: {e}")
            else:
                self.error_counts['parsing'] += 1
                print(f"⚠️ Error processing brand batch: {e}")
                # Return default results for all keywords
                return [
                    {'Search Term': kw, 'Brand': 'ERROR_API'} 
                    for kw in keywords
                ]
    
    @retry_with_exponential_backoff(max_retries=5, base_delay=1.0, max_delay=30.0)
    async def process_product_batch(self, search_terms: List[str]) -> List[Dict[str, Any]]:
        """
        Process a batch of search terms for product assessment with enhanced error handling.
        
        Args:
            search_terms: List of search terms to process
            
        Returns:
            List of dictionaries with assessment results
        """
        batch_start_time = time.time()
        
        try:
            # Create prompt for multiple search terms
            terms_text = ", ".join(search_terms)
            prompt = f"""Assess these products for e-commerce potential. For each product, provide ratings:

Products: {terms_text}

Rate each product (0-5 scale) for:
1. SEASONAL DEMAND: 0=flat year, 5=strongly seasonal
2. SPECIFICITY (0=broad term like "shampoo", 5=very narrow like "creatine monohydrate 5g gummies").
3. COMMODITY: 0=brand-owned, 5=commodity
4. SUBSCRIBE & SAVE: 0=not suitable, 5=perfect for subscription

Plus binary (0/1) for:
5. GATED (1 if restricted Amazon category (OTC, medical device, adult, pesticides, hazmat, etc. — not supplements), else 0)
6. ELECTRONICS/BATTERIES (1 if electronic, battery-powered, or requires replacement heads/charging)
7. INSURANCE/GOV (1 if reimbursed by insurance or supplied free by gov programs)

IMPORTANT: You MUST respond with EXACTLY 7 numbers per product, separated by commas.
Format: product1:1,2,3,4,0,0,0;product2:2,3,2,1,0,1,0

Example: makeup:2,2,3,2,0,0,0;nike_shoes:1,4,1,2,0,0,0"""

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an e-commerce product analyst. Respond with ONLY assessment numbers separated by commas and semicolons, no other text."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse the response
            results = []
            product_assessments = result.split(';')
            
            for i, assessment in enumerate(product_assessments):
                if ':' in assessment:
                    product_part, ratings_part = assessment.split(':', 1)
                    product = product_part.strip()
                    ratings = [r.strip() for r in ratings_part.split(',')]
                    
                    if len(ratings) == 7:
                        try:
                            # Convert ratings to appropriate types
                            seasonal = int(ratings[0])
                            specificity = int(ratings[1])
                            commodity = int(ratings[2])
                            subscribe_save = int(ratings[3])
                            gated = int(ratings[4])
                            electronics = int(ratings[5])
                            insurance = int(ratings[6])
                            
                            # Validate ranges
                            if (0 <= seasonal <= 5 and 0 <= specificity <= 5 and 0 <= commodity <= 5 and 
                                0 <= subscribe_save <= 5 and 0 <= gated <= 1 and 0 <= electronics <= 1 and 0 <= insurance <= 1):
                                
                                results.append({
                                    'Seasonal': seasonal,
                                    'Specificity': specificity,
                                    'Commodity': commodity,
                                    'Subscribe&Save': subscribe_save,
                                    'Gated': gated,
                                    'Electronics_Batteries': electronics,
                                    'Insurance_Gov': insurance
                                })
                            else:
                                raise ValueError("Rating out of range")
                                
                        except (ValueError, IndexError):
                            # Use default values if parsing fails
                            results.append({
                                'Seasonal': 3, 'Specificity': 3, 'Commodity': 3, 
                                'Subscribe&Save': 2, 'Gated': 0, 'Electronics_Batteries': 0, 
                                'Insurance_Gov': 0
                            })
                    else:
                        # Use default values if wrong number of ratings
                        results.append({
                            'Seasonal': 3, 'Specificity': 3, 'Commodity': 3, 
                            'Subscribe&Save': 2, 'Gated': 0, 'Electronics_Batteries': 0, 
                            'Insurance_Gov': 0
                        })
                else:
                    # Use default values if format is wrong
                    results.append({
                        'Seasonal': 3, 'Specificity': 3, 'Commodity': 3, 
                        'Subscribe&Save': 2, 'Gated': 0, 'Electronics_Batteries': 0, 
                        'Insurance_Gov': 0
                    })
            
            # Ensure we have results for all search terms
            while len(results) < len(search_terms):
                results.append({
                    'Seasonal': 3, 'Specificity': 3, 'Commodity': 3, 
                    'Subscribe&Save': 2, 'Gated': 0, 'Electronics_Batteries': 0, 
                    'Insurance_Gov': 0
                })
            
            # Log performance metrics
            batch_time = time.time() - batch_start_time
            self.log_batch_performance(len(search_terms), batch_time)
            
            return results
            
        except Exception as e:
            # Log error and categorize
            if "rate limit" in str(e).lower() or "429" in str(e):
                self.error_counts['rate_limit'] += 1
                self.rate_limit_occurrences += 1
                raise RATE_LIMIT_HIT(f"Rate limit exceeded: {e}")
            elif "authentication" in str(e).lower() or "401" in str(e):
                self.error_counts['auth'] += 1
                raise AUTH_ERROR(f"Authentication error: {e}")
            elif "network" in str(e).lower() or "timeout" in str(e).lower():
                self.error_counts['network'] += 1
                raise NETWORK_ERROR(f"Network error: {e}")
            else:
                self.error_counts['parsing'] += 1
                print(f"⚠️ Error processing product batch: {e}")
                # Return default results for all search terms
                return [
                    {
                        'Seasonal': 3, 'Specificity': 3, 'Commodity': 3, 
                        'Subscribe&Save': 2, 'Gated': 0, 'Electronics_Batteries': 0, 
                        'Insurance_Gov': 0
                    }
                    for _ in search_terms
                ]
    
    async def process_batch(self, items: List[str], batch_type: str) -> List[Dict[str, Any]]:
        """
        Process a batch of items based on the batch type.
        
        Args:
            items: List of items to process
            batch_type: Either "brand" or "product"
            
        Returns:
            List of processed results
        """
        if batch_type == "brand":
            return await self.process_brand_batch(items)
        elif batch_type == "product":
            return await self.process_product_batch(items)
        else:
            raise ValueError(f"Unknown batch type: {batch_type}")
    
    def cleanup_progress_files(self):
        """Clean up progress files after successful completion."""
        try:
            if os.path.exists(self.progress_file):
                os.remove(self.progress_file)
            if os.path.exists(self.partial_output_file):
                os.remove(self.partial_output_file)
        except Exception as e:
            print(f"⚠️ Warning: Could not clean up progress files: {e}")
    
    def get_progress_summary(self) -> str:
        """Get a comprehensive summary of current progress and performance."""
        progress = self.load_progress()
        if progress:
            memory_mb = self.get_memory_usage()
            speed = self.get_processing_speed()
            eta = self.calculate_eta(progress.get('total_items', 0) - progress.get('processed_count', 0))
            
            summary = f"""📊 Progress Summary for {progress['script_type']}
├── Current Batch: {progress['current_batch']}
├── Processed: {progress['processed_count']}
├── Total: {progress['total_items']}
├── Completion: {progress['processed_count']/progress['total_items']*100:.1f}%
├── ETA: {eta}
├── Processing Speed: {speed:.1f} items/minute
├── Memory Usage: {memory_mb:.1f} MB
├── Rate Limit Hits: {self.rate_limit_occurrences}
├── Total Wait Time: {self.total_wait_time:.1f}s
├── Uptime: {(time.time() - self.start_time)/60:.1f} minutes
└── Last Update: {progress['last_update']}"""
            
            # Add error summary if any errors occurred
            if any(count > 0 for count in self.error_counts.values()):
                error_summary = "\n\n🚨 Error Summary:"
                for error_type, count in self.error_counts.items():
                    if count > 0:
                        error_summary += f"\n   - {error_type.replace('_', ' ').title()}: {count}"
                summary += error_summary
                
            return summary
        return "No progress file found."
    
    def get_performance_report(self) -> str:
        """Get a detailed performance report."""
        if not self.batch_times:
            return "No performance data available."
            
        avg_batch_time = sum(self.batch_times) / len(self.batch_times)
        avg_speed = self.get_processing_speed()
        memory_trend = "Stable"
        
        if len(self.memory_usage) > 10:
            recent_memory = [m['memory_mb'] for m in self.memory_usage[-10:]]
            if max(recent_memory) - min(recent_memory) > 50:  # 50MB variation
                memory_trend = "Fluctuating"
            elif recent_memory[-1] > recent_memory[0] * 1.5:  # 50% increase
                memory_trend = "Increasing"
                
        return f"""📈 Performance Report
├── Average Batch Time: {avg_batch_time:.2f}s
├── Processing Speed: {avg_speed:.1f} items/minute
├── Memory Trend: {memory_trend}
├── Total Batches Processed: {len(self.batch_times)}
├── Rate Limit Occurrences: {self.rate_limit_occurrences}
└── Total Wait Time: {self.total_wait_time:.1f}s"""
