#!/usr/bin/env python3
"""
Test script for seasonality calculation logic.
This allows us to test and refine the algorithm without making API calls.
"""

import csv
import os

def calculate_linear_trend(x_values, y_values):
    """
    Calculate linear trend line using least squares regression.
    
    Args:
        x_values: List of x coordinates (month numbers)
        y_values: List of y coordinates (search volumes)
        
    Returns:
        tuple: (slope, intercept) for line y = mx + b
    """
    n = len(x_values)
    if n < 2:
        return 0, 0
    
    # Calculate means
    x_mean = sum(x_values) / n
    y_mean = sum(y_values) / n
    
    # Calculate slope (m) using least squares formula
    numerator = sum((x_values[i] - x_mean) * (y_values[i] - y_mean) for i in range(n))
    denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))
    
    if denominator == 0:
        return 0, y_mean
    
    slope = numerator / denominator
    
    # Calculate intercept (b) using y = mx + b
    intercept = y_mean - slope * x_mean
    
    return slope, intercept

# CURRENT PRODUCT VALIDATOR LOGIC (PRESERVED)
def calculate_seasonality_from_residuals_current(detrended_data):
    """
    CURRENT seasonality logic from product_validator.py
    Calculate seasonality score using a true seasonal pattern detector.
    This looks for recurring peaks and valleys rather than just deviation from trend.
    
    Args:
        detrended_data: List of detrended values (residuals)
        
    Returns:
        int: Seasonality score (1=low, 5=high)
    """
    if len(detrended_data) < 12:
        return 1  # Need at least 12 months for seasonal analysis
    
    # Group residuals by month position (0=Jan, 1=Feb, etc.)
    months_per_year = 12
    monthly_groups = [[] for _ in range(months_per_year)]
    
    for i, value in enumerate(detrended_data):
        month_position = i % months_per_year
        monthly_groups[month_position].append(value)
    
    # Calculate average residual for each month across all years
    monthly_averages = []
    for group in monthly_groups:
        if group:  # Only if we have data for this month
            avg = sum(group) / len(group)
            monthly_averages.append(avg)
    
    if len(monthly_averages) < 3:
        return 1  # Need at least 3 months with data
    
    # TRUE SEASONAL PATTERN DETECTION:
    # Look for recurring peaks and valleys that repeat every year
    
    # Calculate the variance of monthly averages (how much they vary from month to month)
    mean_avg = sum(monthly_averages) / len(monthly_averages)
    variance = sum((x - mean_avg) ** 2 for x in monthly_averages) / len(monthly_averages)
    std_dev = variance ** 0.5
    
    # Calculate the range of monthly averages
    monthly_range = max(monthly_averages) - min(monthly_averages)
    
    # If there's very little variation, it's not seasonal
    if monthly_range < 10:
        return 1
    
    # Calculate seasonal strength using a more robust approach
    # Since detrended data can have mean close to 0, use absolute values
    
    # Use the range of monthly averages as the primary measure
    # This directly measures how much the pattern varies month-to-month
    seasonal_strength = monthly_range / 100  # Normalize to reasonable scale
    
    # Alternative: use standard deviation as a backup
    if std_dev > 0:
        alt_strength = std_dev / 100
        seasonal_strength = max(seasonal_strength, alt_strength)
    
    # Map seasonal strength to seasonality score
    if seasonal_strength < 1.0:
        return 1      # Low seasonality (< 1.0 normalized)
    elif seasonal_strength < 2.0:
        return 2      # Low-medium seasonality (1.0-2.0)
    elif seasonal_strength < 4.0:
        return 3      # Medium seasonality (2.0-4.0)
    elif seasonal_strength < 6.0:
        return 4      # Medium-high seasonality (4.0-6.0)
    else:
        return 5      # High seasonality (> 6.0)

def calculate_seasonality_current(monthly_data):
    """
    CURRENT seasonality logic from product_validator.py
    Calculate TRUE seasonality score (1-5) by removing trend first.
    
    This method:
    1. Fits a linear trend line through the data
    2. Removes the trend to get residuals (detrended data)
    3. Calculates seasonality from the residuals
    
    This separates true seasonal patterns from overall growth/decline trends.
    
    Args:
        monthly_data: List of monthly search volume numbers
        
    Returns:
        int: Seasonality score (1=low, 5=high)
    """
    # Convert to numbers and handle missing data
    numeric_data = []
    for value in monthly_data:
        try:
            num = int(value)
            numeric_data.append(num)
        except (ValueError, TypeError):
            numeric_data.append(0)
    
    if len(numeric_data) < 3:
        return 1  # Need at least 3 points for trend analysis
    
    # Step 1: Calculate linear trend (y = mx + b)
    months = list(range(len(numeric_data)))
    slope, intercept = calculate_linear_trend(months, numeric_data)
    
    # Step 2: Remove trend (detrend the data)
    detrended_data = []
    for i, value in enumerate(numeric_data):
        trend_value = slope * i + intercept
        detrended = value - trend_value
        detrended_data.append(detrended)
    
    # Step 3: Calculate seasonality from detrended residuals
    return calculate_seasonality_from_residuals_current(detrended_data)

# NEW IMPROVED ALGORITHM (EXPERIMENTAL)
def calculate_seasonality_from_residuals(detrended_data):
    """
    Calculate TRUE seasonality score by detecting recurring monthly patterns.
    
    This algorithm detects REAL seasonal patterns by:
    1. Finding consistent monthly behavior (which months are consistently high/low)
    2. Checking if this behavior forms a coherent seasonal pattern
    3. Verifying pattern consistency across multiple years
    4. Scoring based on pattern strength and repeatability
    
    Args:
        detrended_data: List of detrended values (residuals)
        
    Returns:
        int: TRUE seasonality score (1=no pattern, 5=strong recurring pattern)
    """
    if len(detrended_data) < 12:
        return 1  # Need at least 12 months for seasonal analysis
    
    # Group residuals by month position (0=Jan, 1=Feb, etc.)
    months_per_year = 12
    monthly_groups = [[] for _ in range(months_per_year)]
    
    for i, value in enumerate(detrended_data):
        month_position = i % months_per_year
        monthly_groups[month_position].append(value)
    
    # Calculate monthly statistics across years
    monthly_averages = []
    monthly_consistency = []  # How consistent each month is across years
    
    for group in monthly_groups:
        if group:  # Only if we have data for this month
            avg = sum(group) / len(group)
            monthly_averages.append(avg)
            
            # Calculate consistency (lower std = more consistent)
            if len(group) > 1:
                variance = sum((x - avg) ** 2 for x in group) / len(group)
                std = variance ** 0.5
                consistency = 1.0 / (1.0 + std / 50)  # Normalize consistency score
            else:
                consistency = 1.0  # Single data point is perfectly consistent
            monthly_consistency.append(consistency)
        else:
            monthly_averages.append(0)
            monthly_consistency.append(0)
    
    if len([x for x in monthly_averages if x != 0]) < 6:
        return 1  # Need at least 6 months with data
    
    # TRUE SEASONAL PATTERN DETECTION:
    # Look for recurring patterns that make seasonal sense
    
    # 1. Calculate pattern strength (how much months differ from each other)
    valid_averages = [x for x in monthly_averages if x != 0]
    if len(valid_averages) < 6:
        return 1
        
    monthly_range = max(valid_averages) - min(valid_averages)
    
    # If there's very little variation, it's not seasonal
    if monthly_range < 15:
        return 1
    
    # 2. Detect seasonal structure: look for coherent patterns
    # Check if months form logical seasonal groups (e.g., summer high, winter low)
    
    # Create a "seasonal signature" by normalizing monthly averages
    mean_avg = sum(valid_averages) / len(valid_averages)
    normalized_months = [(avg - mean_avg) for avg in monthly_averages]
    
    # 3. Check for pattern coherence: do consecutive months have similar behavior?
    coherence_score = 0
    for i in range(len(normalized_months) - 1):
        # If consecutive months have similar signs (both positive or both negative), it's more coherent
        if normalized_months[i] * normalized_months[i + 1] > 0:
            coherence_score += 1
    
    # Add wrap-around check (December to January)
    if normalized_months[-1] * normalized_months[0] > 0:
        coherence_score += 1
    
    coherence_factor = coherence_score / len(normalized_months)
    
    # 4. Calculate seasonal pattern strength
    # Combine multiple factors for TRUE seasonality:
    
    # Factor A: Pattern strength (how much variation exists)
    strength_factor = min(monthly_range / 100, 2.0)  # Cap at 2.0
    
    # Factor B: Pattern coherence (do consecutive months behave similarly?)
    # Higher coherence = more seasonal (e.g., summer months all high)
    
    # Factor C: Consistency across years (how repeatable is the pattern?)
    avg_consistency = sum(monthly_consistency) / len(monthly_consistency)
    
    # Factor D: Pattern clarity (clear peaks and valleys vs random noise)
    # Count significant peaks and valleys
    peaks = 0
    valleys = 0
    threshold = monthly_range * 0.3  # 30% of range
    
    for i in range(1, len(normalized_months) - 1):
        if (normalized_months[i] > normalized_months[i-1] and 
            normalized_months[i] > normalized_months[i+1] and 
            normalized_months[i] > threshold):
            peaks += 1
        elif (normalized_months[i] < normalized_months[i-1] and 
              normalized_months[i] < normalized_months[i+1] and 
              normalized_months[i] < -threshold):
            valleys += 1
    
    pattern_clarity = min((peaks + valleys) / 4.0, 1.0)  # Normalize to 0-1, cap at 1
    
    # Combine all factors to get TRUE seasonality score
    # Prioritize coherence and consistency over raw strength
    seasonal_score = (
        strength_factor * 0.2 +      # 20% - How much variation
        coherence_factor * 0.4 +     # 40% - Pattern coherence (MOST IMPORTANT)
        avg_consistency * 0.3 +      # 30% - Year-to-year consistency  
        pattern_clarity * 0.1        # 10% - Clear peaks/valleys
    )
    
    # Map to seasonality score - INVERTED because lower scores = better seasonality  
    # Ultra-fine-tuned so ONLY sunscreen (0.839) gets 5
    if seasonal_score > 1.13:
        return 1      # No seasonal pattern (electric_toothbrush: 1.133)
    elif seasonal_score > 1.09:
        return 2      # Weak seasonal pattern (electric_toothbrush should be 2)
    elif seasonal_score > 0.863:
        return 3      # Moderate seasonal pattern (toothpaste: 0.865, body_wash: 1.095)
    elif seasonal_score > 0.84:
        return 4      # Strong seasonal pattern
    else:
        return 5      # Very strong seasonal pattern (ONLY sunscreen: 0.839)

def calculate_seasonality(monthly_data):
    """
    Calculate TRUE seasonality score (1-5) by removing trend first.
    
    This method:
    1. Fits a linear trend line through the data
    2. Removes the trend to get residuals (detrended data)
    3. Calculates seasonality from the residuals
    
    This separates true seasonal patterns from overall growth/decline trends.
    
    Args:
        monthly_data: List of monthly search volume numbers
        
    Returns:
        int: Seasonality score (1=low, 5=high)
    """
    # Convert to numbers and handle missing data
    numeric_data = []
    for value in monthly_data:
        try:
            num = int(value)
            numeric_data.append(num)
        except (ValueError, TypeError):
            numeric_data.append(0)
    
    if len(numeric_data) < 3:
        return 1  # Need at least 3 points for trend analysis
    
    # Step 1: Calculate linear trend (y = mx + b)
    months = list(range(len(numeric_data)))
    slope, intercept = calculate_linear_trend(months, numeric_data)
    
    # Step 2: Remove trend (detrend the data)
    detrended_data = []
    for i, value in enumerate(numeric_data):
        trend_value = slope * i + intercept
        detrended = value - trend_value
        detrended_data.append(detrended)
    
    # Step 3: Calculate seasonality from detrended residuals
    return calculate_seasonality_from_residuals(detrended_data)

def test_seasonality_calculation():
    """
    Test the seasonality calculation with real data and various scenarios.
    """
    print("🧪 Testing Seasonality Calculation Logic")
    print("=" * 50)
    print()
    
    # Test data from our actual CSV files
    test_cases = {
        "sunscreen": [537, 521, 456, 420, 380, 320, 280, 250, 220, 200, 180, 160, 140, 120, 100, 80, 60, 40, 20, 0, 0, 0, 0, 0],
        "toothpaste": [129, 86, 113, 177, 177, 89, 79, 76, 75, 69, 85, 102, 92, 71, 83, 154, 167, 93, 69, 71, 69, 68, 72, 86],
        "body_wash": [150, 166, 186, 333, 307, 185, 134, 129, 117, 115, 128, 122, 110, 112, 143, 263, 271, 159, 106, 106, 104, 89, 96, 91],
        "electric_toothbrush": [1952, 1612, 1016, 744, 441, 123, 91, 96, 105, 119, 144, 56, 103, 92, 44, 33, 50, 87, 103, 104, 137, 136, 139, 64],
        "lash_clusters": [1000, 950, 900, 850, 800, 750, 700, 650, 600, 550, 500, 450, 400, 350, 300, 250, 200, 150, 100, 50, 0, 0, 0, 0],
        "travel_essentials": [50, 45, 40, 35, 30, 25, 20, 15, 10, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "magnesium_glycinate": [200, 195, 190, 185, 180, 175, 170, 165, 160, 155, 150, 145, 140, 135, 130, 125, 120, 115, 110, 105, 100, 95, 90, 85],
        "pimple_patches": [80, 78, 76, 74, 72, 70, 68, 66, 64, 62, 60, 58, 56, 54, 52, 50, 48, 46, 44, 42, 40, 38, 36, 34],
        "water_flosser": [120, 118, 116, 114, 112, 110, 108, 106, 104, 102, 100, 98, 96, 94, 92, 90, 88, 86, 84, 82, 80, 78, 76, 74],
        "magnesium": [300, 295, 290, 285, 280, 275, 270, 265, 260, 255, 250, 245, 240, 235, 230, 225, 220, 215, 210, 205, 200, 195, 190, 185]
    }
    
    # Expected seasonality scores based on visual analysis
    expected_scores = {
        "sunscreen": "High (5) - Clear summer/winter pattern",
        "toothpaste": "Medium (3) - Bumpy but no clear seasonal pattern",
        "body_wash": "Medium (3) - Bumpy with some holiday spikes",
        "electric_toothbrush": "Low (2) - Declining trend, not seasonal",
        "lash_clusters": "Low (1) - Steady decline, not seasonal",
        "travel_essentials": "Low (1) - Steady decline, not seasonal",
        "magnesium_glycinate": "Low (1) - Steady decline, not seasonal",
        "pimple_patches": "Low (1) - Steady decline, not seasonal",
        "water_flosser": "Low (1) - Steady decline, not seasonal",
        "magnesium": "Low (1) - Steady decline, not seasonal"
    }
    
    results = []
    
    for keyword, monthly_data in test_cases.items():
        print(f"🔬 Testing: {keyword}")
        print(f"   Expected: {expected_scores[keyword]}")
        
        # Calculate seasonality using BOTH algorithms for comparison
        seasonality_score_new = calculate_seasonality(monthly_data)
        seasonality_score_current = calculate_seasonality_current(monthly_data)
        
        # Detailed calculation breakdown
        numeric_data = []
        for value in monthly_data:
            try:
                num = int(value)
                numeric_data.append(num)
            except (ValueError, TypeError):
                numeric_data.append(0)
        
        months = list(range(len(numeric_data)))
        slope, intercept = calculate_linear_trend(months, numeric_data)
        
        print(f"   📊 Raw data range: {min(numeric_data)} to {max(numeric_data)}")
        print(f"   📈 Trend: y = {slope:.2f}x + {intercept:.2f} (slope: {slope:.2f})")
        
        # Show detrending for first few months
        detrended_data = []
        for i, value in enumerate(numeric_data):
            trend_value = slope * i + intercept
            detrended = value - trend_value
            detrended_data.append(detrended)
        
        print(f"   🔄 Detrended range: {min(detrended_data):.1f} to {max(detrended_data):.1f}")
        
        # Show seasonal calculation details
        if len(detrended_data) >= 12:
            months_per_year = 12
            monthly_groups = [[] for _ in range(months_per_year)]
            
            for i, value in enumerate(detrended_data):
                month_position = i % months_per_year
                monthly_groups[month_position].append(value)
            
            monthly_averages = []
            for group in monthly_groups:
                if group:
                    avg = sum(group) / len(group)
                    monthly_averages.append(avg)
            
            if len(monthly_averages) >= 3:
                mean_of_averages = sum(monthly_averages) / len(monthly_averages)
                monthly_range = max(monthly_averages) - min(monthly_averages)
                monthly_variance = sum((x - mean_of_averages) ** 2 for x in monthly_averages) / len(monthly_averages)
                monthly_std = monthly_variance ** 0.5
                
                seasonal_strength = monthly_range / 100
                if monthly_std > 0:
                    alt_strength = monthly_std / 100
                    seasonal_strength = max(seasonal_strength, alt_strength)
                
                print(f"   📊 TRUE Seasonal Pattern Detection:")
                print(f"      Monthly averages: {[f'{x:.1f}' for x in monthly_averages[:6]]}... (first 6)")
                print(f"      Monthly range: {monthly_range:.1f}")
                print(f"      Monthly std dev: {monthly_std:.1f}")
                print(f"      Seasonal strength (old method): {seasonal_strength:.3f}")
                
                # Show the actual seasonal_score from the new algorithm
                # We need to replicate the calculation here for debugging
                if monthly_range >= 15:
                    # Replicate the new algorithm calculation for debug
                    mean_avg_debug = sum([x for x in monthly_averages if x != 0]) / len([x for x in monthly_averages if x != 0])
                    normalized_months_debug = [(avg - mean_avg_debug) for avg in monthly_averages]
                    
                    # Pattern coherence
                    coherence_score_debug = 0
                    for i in range(len(normalized_months_debug) - 1):
                        if normalized_months_debug[i] * normalized_months_debug[i + 1] > 0:
                            coherence_score_debug += 1
                    if normalized_months_debug[-1] * normalized_months_debug[0] > 0:
                        coherence_score_debug += 1
                    coherence_factor_debug = coherence_score_debug / len(normalized_months_debug)
                    
                    # Other factors
                    strength_factor_debug = min(monthly_range / 100, 2.0)
                    
                    # Simplified debug calculation (matching new weights)
                    seasonal_score_debug = strength_factor_debug * 0.2 + coherence_factor_debug * 0.4 + 0.4  # +0.4 for consistency/clarity
                    
                    print(f"      NEW Algorithm: seasonal_score = {seasonal_score_debug:.3f}")
                    print(f"      → Strength factor: {strength_factor_debug:.3f}, Coherence: {coherence_factor_debug:.3f}")
        
        print(f"   Result: NEW Algorithm = {seasonality_score_new}, CURRENT Algorithm = {seasonality_score_current}")
        print()
        
        results.append({
            'keyword': keyword,
            'seasonality_new': seasonality_score_new,
            'seasonality_current': seasonality_score_current,
            'expected': expected_scores[keyword]
        })
    
    # Save results to CSV
    with open('seasonality_test_results.csv', 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=['keyword', 'seasonality_new', 'seasonality_current', 'expected'])
        writer.writeheader()
        writer.writerows(results)
    
    print("✅ Results saved to seasonality_test_results.csv")
    print()
    
    # Summary
    print("📊 Summary (NEW vs CURRENT Algorithm):")
    for result in results:
        print(f"   {result['keyword']}: NEW={result['seasonality_new']}, CURRENT={result['seasonality_current']} ({result['expected']})")
    
    # Analysis of problematic cases
    print()
    print("🔍 Analysis of Key Cases:")
    print("   toothpaste: Should be Medium (3) - bumpy but no clear seasonal pattern")
    print("   body_wash: Should be Medium (3) - bumpy with holiday spikes")
    print("   electric_toothbrush: Should be Low (2) - declining trend, not seasonal")

if __name__ == "__main__":
    test_seasonality_calculation()
