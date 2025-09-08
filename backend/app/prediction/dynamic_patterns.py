"""
Dynamic Pattern Analysis for EV Charging Power Prediction

This module implements adaptive seasonal and temporal pattern detection
based on actual charging data, replacing static pattern factors with
data-driven dynamic calculations.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
import warnings

warnings.filterwarnings("ignore")


@dataclass
class PatternFactors:
    """Container for calculated pattern factors"""
    seasonal_factors: Dict[int, float]  # month -> factor
    weekly_factors: Dict[int, float]    # weekday -> factor
    hourly_factors: Dict[int, float]    # hour -> factor
    trend_factor: float                 # overall trend adjustment
    confidence: float                   # confidence in pattern reliability
    data_quality: str                   # data quality assessment
    calculation_metadata: Dict[str, Any]


class DynamicPatternAnalyzer:
    """
    Analyzes charging data to extract adaptive seasonal, weekly, and hourly patterns.
    
    This class calculates dynamic adjustment factors based on actual data patterns
    rather than using static predefined factors, making predictions more responsive
    to actual charging behavior.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.min_data_points = 50  # Minimum data points for reliable pattern calculation
        self.recent_weight = 0.7   # Weight for recent data (last 3 months)
        self.historical_weight = 0.3  # Weight for historical data
        
    def analyze_patterns(self, data: pd.DataFrame, station_id: str = None) -> PatternFactors:
        """
        Analyze charging data to extract dynamic patterns.
        
        Args:
            data: DataFrame with charging session data
            station_id: Station identifier for logging
            
        Returns:
            PatternFactors object with calculated adjustment factors
        """
        if data.empty:
            return self._create_fallback_patterns("empty_data")
            
        try:
            # Prepare time-indexed data
            time_data = self._prepare_time_data(data)
            
            if len(time_data) < self.min_data_points:
                self.logger.warning(f"Station {station_id}: Insufficient data ({len(time_data)} points), using fallback patterns")
                return self._create_fallback_patterns("insufficient_data")
            
            # Calculate different pattern types
            seasonal_factors = self._calculate_seasonal_patterns(time_data)
            weekly_factors = self._calculate_weekly_patterns(time_data)
            hourly_factors = self._calculate_hourly_patterns(time_data)
            trend_factor = self._calculate_trend_factor(time_data)
            
            # Assess data quality and confidence
            confidence, data_quality = self._assess_pattern_quality(time_data, seasonal_factors, weekly_factors)
            
            # Create metadata
            metadata = {
                "data_points": len(time_data),
                "date_range": {
                    "start": time_data.index.min().isoformat() if not time_data.empty else None,
                    "end": time_data.index.max().isoformat() if not time_data.empty else None,
                    "span_days": (time_data.index.max() - time_data.index.min()).days if len(time_data) > 1 else 0
                },
                "pattern_strength": self._calculate_pattern_strength(seasonal_factors, weekly_factors),
                "station_id": station_id,
                "analysis_timestamp": datetime.now().isoformat()
            }
            
            self.logger.info(f"Station {station_id}: Dynamic patterns calculated with {confidence:.2f} confidence")
            
            return PatternFactors(
                seasonal_factors=seasonal_factors,
                weekly_factors=weekly_factors,
                hourly_factors=hourly_factors,
                trend_factor=trend_factor,
                confidence=confidence,
                data_quality=data_quality,
                calculation_metadata=metadata
            )
            
        except Exception as e:
            self.logger.error(f"Pattern analysis failed for station {station_id}: {e}")
            return self._create_fallback_patterns("analysis_error")
    
    def apply_pattern_adjustment(self, base_prediction: float, pattern_factors: PatternFactors, 
                               target_month: int = None, target_weekday: int = None, 
                               target_hour: int = None) -> float:
        """
        Apply dynamic pattern adjustments to base prediction.
        
        Args:
            base_prediction: Base prediction value to adjust
            pattern_factors: Calculated pattern factors
            target_month: Target month (1-12), defaults to next month
            target_weekday: Target weekday (0-6), defaults to typical workday
            target_hour: Target hour (0-23), defaults to peak hour
            
        Returns:
            Adjusted prediction value
        """
        if not pattern_factors or pattern_factors.confidence < 0.3:
            self.logger.info("Low confidence in patterns, using base prediction")
            return base_prediction
            
        try:
            # Use current time context if not specified
            now = datetime.now()
            if target_month is None:
                target_month = (now.month % 12) + 1  # Next month
            if target_weekday is None:
                target_weekday = 1  # Tuesday (typical high-usage day)
            if target_hour is None:
                target_hour = 14  # 2 PM (typical peak hour)
            
            # Apply adjustments
            adjusted_value = base_prediction
            
            # 1. Seasonal adjustment
            if target_month in pattern_factors.seasonal_factors:
                seasonal_factor = pattern_factors.seasonal_factors[target_month]
                adjusted_value *= seasonal_factor
                self.logger.debug(f"Applied seasonal factor {seasonal_factor:.3f} for month {target_month}")
            
            # 2. Weekly pattern adjustment (reduced weight)
            if target_weekday in pattern_factors.weekly_factors:
                weekly_factor = pattern_factors.weekly_factors[target_weekday]
                # Reduce weekly impact to 30% to avoid over-adjustment
                weekly_adjustment = 1.0 + (weekly_factor - 1.0) * 0.3
                adjusted_value *= weekly_adjustment
                self.logger.debug(f"Applied weekly factor {weekly_adjustment:.3f} for weekday {target_weekday}")
            
            # 3. Trend adjustment
            if abs(pattern_factors.trend_factor - 1.0) > 0.05:  # Only apply if significant trend
                adjusted_value *= pattern_factors.trend_factor
                self.logger.debug(f"Applied trend factor {pattern_factors.trend_factor:.3f}")
            
            # 4. Confidence-based dampening
            # Reduce adjustment impact based on confidence
            confidence_weight = min(1.0, pattern_factors.confidence * 1.5)
            final_adjustment_ratio = adjusted_value / base_prediction
            dampened_ratio = 1.0 + (final_adjustment_ratio - 1.0) * confidence_weight
            final_value = base_prediction * dampened_ratio
            
            # 5. Bounds checking
            final_value = max(base_prediction * 0.5, min(base_prediction * 2.0, final_value))
            
            self.logger.info(
                f"Pattern adjustment: {base_prediction:.1f} -> {final_value:.1f} "
                f"(confidence: {pattern_factors.confidence:.2f}, ratio: {final_value/base_prediction:.3f})"
            )
            
            return final_value
            
        except Exception as e:
            self.logger.error(f"Pattern adjustment failed: {e}")
            return base_prediction
    
    def _prepare_time_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare time-indexed DataFrame for pattern analysis"""
        time_cols = ["충전시작일시", "사용일시", "charging_start_time", "timestamp"]
        power_cols = ["순간최고전력", "max_power", "power", "전력"]
        
        # Find time and power columns
        time_col = None
        power_col = None
        
        for col in time_cols:
            if col in data.columns:
                time_col = col
                break
                
        for col in power_cols:
            if col in data.columns:
                power_col = col
                break
                
        if not time_col or not power_col:
            return pd.DataFrame()
        
        # Create time-indexed data
        try:
            result_data = data[[time_col, power_col]].copy()
            result_data[time_col] = pd.to_datetime(result_data[time_col], errors='coerce')
            result_data = result_data.dropna()
            
            if result_data.empty:
                return pd.DataFrame()
                
            result_data.set_index(time_col, inplace=True)
            result_data.columns = ['power']
            
            # Remove outliers using IQR method
            Q1 = result_data['power'].quantile(0.25)
            Q3 = result_data['power'].quantile(0.75)
            IQR = Q3 - Q1
            
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            result_data = result_data[(result_data['power'] >= lower_bound) & 
                                    (result_data['power'] <= upper_bound)]
            
            return result_data.sort_index()
            
        except Exception as e:
            self.logger.warning(f"Time data preparation failed: {e}")
            return pd.DataFrame()
    
    def _calculate_seasonal_patterns(self, time_data: pd.DataFrame) -> Dict[int, float]:
        """Calculate monthly seasonal adjustment factors"""
        if time_data.empty:
            return self._get_default_seasonal_factors()
        
        try:
            # Group by month and calculate average power
            time_data['month'] = time_data.index.month
            monthly_avg = time_data.groupby('month')['power'].mean()
            
            if len(monthly_avg) < 2:
                return self._get_default_seasonal_factors()
            
            # Calculate factors as ratio to overall mean
            overall_mean = time_data['power'].mean()
            seasonal_factors = {}
            
            for month in range(1, 13):
                if month in monthly_avg.index:
                    factor = monthly_avg[month] / overall_mean
                    # Apply smoothing and bounds checking
                    factor = max(0.7, min(1.3, factor))  # Limit factor range
                    seasonal_factors[month] = factor
                else:
                    # Interpolate missing months using nearby months
                    seasonal_factors[month] = self._interpolate_missing_month(month, monthly_avg, overall_mean)
            
            # Apply temporal weighting (recent data more important)
            if len(time_data) > 90:  # If we have more than 3 months of data
                seasonal_factors = self._apply_temporal_weighting(time_data, seasonal_factors)
            
            return seasonal_factors
            
        except Exception as e:
            self.logger.warning(f"Seasonal pattern calculation failed: {e}")
            return self._get_default_seasonal_factors()
    
    def _calculate_weekly_patterns(self, time_data: pd.DataFrame) -> Dict[int, float]:
        """Calculate weekly/daily adjustment factors"""
        if time_data.empty:
            return self._get_default_weekly_factors()
        
        try:
            time_data['weekday'] = time_data.index.weekday  # 0=Monday, 6=Sunday
            weekly_avg = time_data.groupby('weekday')['power'].mean()
            
            if len(weekly_avg) < 2:
                return self._get_default_weekly_factors()
            
            overall_mean = time_data['power'].mean()
            weekly_factors = {}
            
            for day in range(7):
                if day in weekly_avg.index:
                    factor = weekly_avg[day] / overall_mean
                    factor = max(0.7, min(1.3, factor))  # Limit factor range
                    weekly_factors[day] = factor
                else:
                    weekly_factors[day] = 1.0  # Default factor
            
            return weekly_factors
            
        except Exception as e:
            self.logger.warning(f"Weekly pattern calculation failed: {e}")
            return self._get_default_weekly_factors()
    
    def _calculate_hourly_patterns(self, time_data: pd.DataFrame) -> Dict[int, float]:
        """Calculate hourly adjustment factors"""
        if time_data.empty:
            return self._get_default_hourly_factors()
        
        try:
            time_data['hour'] = time_data.index.hour
            hourly_avg = time_data.groupby('hour')['power'].mean()
            
            if len(hourly_avg) < 2:
                return self._get_default_hourly_factors()
            
            overall_mean = time_data['power'].mean()
            hourly_factors = {}
            
            for hour in range(24):
                if hour in hourly_avg.index:
                    factor = hourly_avg[hour] / overall_mean
                    factor = max(0.5, min(1.5, factor))  # Allow wider range for hourly patterns
                    hourly_factors[hour] = factor
                else:
                    hourly_factors[hour] = 1.0  # Default factor
            
            return hourly_factors
            
        except Exception as e:
            self.logger.warning(f"Hourly pattern calculation failed: {e}")
            return self._get_default_hourly_factors()
    
    def _calculate_trend_factor(self, time_data: pd.DataFrame) -> float:
        """Calculate overall trend adjustment factor"""
        try:
            if len(time_data) < 30:  # Need at least 30 data points for trend
                return 1.0
            
            # Calculate monthly averages for trend analysis
            monthly_data = time_data.resample('M')['power'].mean().dropna()
            
            if len(monthly_data) < 3:
                return 1.0
            
            # Simple linear trend calculation
            x = np.arange(len(monthly_data))
            y = monthly_data.values
            
            # Calculate slope
            slope = np.polyfit(x, y, 1)[0]
            
            # Convert slope to annual growth rate
            months_per_year = 12
            annual_growth_rate = slope * months_per_year / monthly_data.mean()
            
            # Convert to factor (limit to reasonable range)
            trend_factor = 1.0 + min(0.2, max(-0.2, annual_growth_rate))
            
            return trend_factor
            
        except Exception as e:
            self.logger.warning(f"Trend factor calculation failed: {e}")
            return 1.0
    
    def _apply_temporal_weighting(self, time_data: pd.DataFrame, factors: Dict[int, float]) -> Dict[int, float]:
        """Apply temporal weighting to give more importance to recent data"""
        try:
            cutoff_date = time_data.index.max() - timedelta(days=90)  # Last 3 months
            recent_data = time_data[time_data.index >= cutoff_date]
            historical_data = time_data[time_data.index < cutoff_date]
            
            if recent_data.empty:
                return factors
            
            # Calculate recent patterns
            recent_monthly = recent_data.groupby(recent_data.index.month)['power'].mean()
            overall_recent_mean = recent_data['power'].mean()
            
            # Weight combination
            weighted_factors = {}
            for month, factor in factors.items():
                if month in recent_monthly.index:
                    recent_factor = recent_monthly[month] / overall_recent_mean
                    recent_factor = max(0.7, min(1.3, recent_factor))
                    
                    # Weighted combination
                    weighted_factor = (self.recent_weight * recent_factor + 
                                     self.historical_weight * factor)
                    weighted_factors[month] = weighted_factor
                else:
                    weighted_factors[month] = factor
            
            return weighted_factors
            
        except Exception as e:
            self.logger.warning(f"Temporal weighting failed: {e}")
            return factors
    
    def _interpolate_missing_month(self, month: int, monthly_avg: pd.Series, overall_mean: float) -> float:
        """Interpolate factor for missing months"""
        try:
            available_months = sorted(monthly_avg.index.tolist())
            
            if not available_months:
                return 1.0
            
            # Find closest months
            before_months = [m for m in available_months if m < month]
            after_months = [m for m in available_months if m > month]
            
            if before_months and after_months:
                # Interpolate between closest before and after
                before_month = max(before_months)
                after_month = min(after_months)
                
                before_factor = monthly_avg[before_month] / overall_mean
                after_factor = monthly_avg[after_month] / overall_mean
                
                weight = (month - before_month) / (after_month - before_month)
                interpolated_factor = before_factor + weight * (after_factor - before_factor)
                
            elif before_months:
                # Use closest previous month
                closest_month = max(before_months)
                interpolated_factor = monthly_avg[closest_month] / overall_mean
                
            elif after_months:
                # Use closest next month
                closest_month = min(after_months)
                interpolated_factor = monthly_avg[closest_month] / overall_mean
                
            else:
                return 1.0
            
            return max(0.7, min(1.3, interpolated_factor))
            
        except Exception as e:
            self.logger.warning(f"Month interpolation failed: {e}")
            return 1.0
    
    def _assess_pattern_quality(self, time_data: pd.DataFrame, 
                               seasonal_factors: Dict[int, float], 
                               weekly_factors: Dict[int, float]) -> Tuple[float, str]:
        """Assess the quality and reliability of calculated patterns"""
        try:
            if time_data.empty:
                return 0.3, "no_data"
            
            data_span_days = (time_data.index.max() - time_data.index.min()).days
            data_points = len(time_data)
            
            # Base confidence based on data quantity
            if data_points >= 1000 and data_span_days >= 180:
                base_confidence = 0.9
                quality = "excellent"
            elif data_points >= 500 and data_span_days >= 90:
                base_confidence = 0.8
                quality = "good"
            elif data_points >= 200 and data_span_days >= 60:
                base_confidence = 0.7
                quality = "fair"
            else:
                base_confidence = 0.6
                quality = "limited"
            
            # Adjust confidence based on pattern consistency
            seasonal_consistency = self._calculate_pattern_consistency(seasonal_factors)
            weekly_consistency = self._calculate_pattern_consistency(weekly_factors)
            
            consistency_factor = (seasonal_consistency + weekly_consistency) / 2
            final_confidence = base_confidence * consistency_factor
            
            return final_confidence, quality
            
        except Exception as e:
            self.logger.warning(f"Pattern quality assessment failed: {e}")
            return 0.5, "unknown"
    
    def _calculate_pattern_consistency(self, factors: Dict[int, float]) -> float:
        """Calculate how consistent/stable the pattern factors are"""
        if not factors:
            return 0.5
        
        values = list(factors.values())
        
        # Calculate coefficient of variation
        mean_val = np.mean(values)
        std_val = np.std(values)
        
        if mean_val == 0:
            return 0.5
        
        cv = std_val / mean_val
        
        # Convert CV to consistency score (lower CV = higher consistency)
        consistency = max(0.3, min(1.0, 1.0 - cv))
        
        return consistency
    
    def _calculate_pattern_strength(self, seasonal_factors: Dict[int, float], 
                                   weekly_factors: Dict[int, float]) -> Dict[str, float]:
        """Calculate the strength of different patterns"""
        seasonal_strength = self._calculate_single_pattern_strength(seasonal_factors)
        weekly_strength = self._calculate_single_pattern_strength(weekly_factors)
        
        return {
            "seasonal_strength": seasonal_strength,
            "weekly_strength": weekly_strength,
            "overall_strength": (seasonal_strength + weekly_strength) / 2
        }
    
    def _calculate_single_pattern_strength(self, factors: Dict[int, float]) -> float:
        """Calculate strength of a single pattern type"""
        if not factors:
            return 0.0
        
        values = list(factors.values())
        
        # Pattern strength is based on deviation from 1.0 (neutral)
        deviations = [abs(v - 1.0) for v in values]
        avg_deviation = np.mean(deviations)
        
        # Normalize to 0-1 scale
        strength = min(1.0, avg_deviation * 2)
        
        return strength
    
    def _get_default_seasonal_factors(self) -> Dict[int, float]:
        """Get default seasonal factors based on general EV charging patterns"""
        # Mild seasonal patterns for EV charging (less pronounced than heating/cooling)
        return {
            1: 0.95,   # January - slightly lower (winter)
            2: 0.95,   # February - slightly lower
            3: 1.0,    # March - neutral
            4: 1.0,    # April - neutral
            5: 1.05,   # May - slightly higher (spring travel)
            6: 1.1,    # June - higher (summer travel begins)
            7: 1.15,   # July - highest (peak summer travel)
            8: 1.1,    # August - high (continued summer travel)
            9: 1.05,   # September - moderate (back to school)
            10: 1.0,   # October - neutral
            11: 0.95,  # November - slightly lower
            12: 0.95   # December - slightly lower (winter)
        }
    
    def _get_default_weekly_factors(self) -> Dict[int, float]:
        """Get default weekly factors based on general commuting patterns"""
        return {
            0: 1.1,    # Monday - high (commute start)
            1: 1.05,   # Tuesday - moderate high
            2: 1.0,    # Wednesday - neutral
            3: 1.0,    # Thursday - neutral
            4: 1.05,   # Friday - moderate high (weekend prep)
            5: 0.85,   # Saturday - lower (weekend)
            6: 0.8     # Sunday - lowest (weekend)
        }
    
    def _get_default_hourly_factors(self) -> Dict[int, float]:
        """Get default hourly factors based on general daily patterns"""
        # Peak hours: morning (7-9), evening (17-19)
        factors = {}
        for hour in range(24):
            if 7 <= hour <= 9 or 17 <= hour <= 19:
                factors[hour] = 1.3  # Peak hours
            elif 10 <= hour <= 16:
                factors[hour] = 1.1  # Daytime
            elif 20 <= hour <= 22:
                factors[hour] = 1.0  # Evening
            else:
                factors[hour] = 0.7  # Night/early morning
        
        return factors
    
    def _create_fallback_patterns(self, reason: str) -> PatternFactors:
        """Create fallback patterns when analysis fails"""
        return PatternFactors(
            seasonal_factors=self._get_default_seasonal_factors(),
            weekly_factors=self._get_default_weekly_factors(),
            hourly_factors=self._get_default_hourly_factors(),
            trend_factor=1.0,
            confidence=0.3,
            data_quality="fallback",
            calculation_metadata={
                "fallback_reason": reason,
                "analysis_timestamp": datetime.now().isoformat(),
                "pattern_type": "default_static_patterns"
            }
        )
    
    def apply_pattern_adjustment(self, base_prediction: float, patterns: PatternFactors, 
                                target_month: int = None, target_weekday: int = None, 
                                target_hour: int = None) -> float:
        """
        Apply pattern adjustments to base prediction.
        
        Args:
            base_prediction: Base prediction value
            patterns: Calculated pattern factors
            target_month: Target month (1-12), defaults to current
            target_weekday: Target weekday (0-6), defaults to current
            target_hour: Target hour (0-23), defaults to current
            
        Returns:
            Adjusted prediction value
        """
        try:
            now = datetime.now()
            
            if target_month is None:
                target_month = now.month
            if target_weekday is None:
                target_weekday = now.weekday()
            if target_hour is None:
                target_hour = now.hour
            
            # Apply adjustments
            seasonal_adjustment = patterns.seasonal_factors.get(target_month, 1.0)
            weekly_adjustment = patterns.weekly_factors.get(target_weekday, 1.0)
            hourly_adjustment = patterns.hourly_factors.get(target_hour, 1.0)
            
            # Weight adjustments based on confidence
            confidence_weight = min(1.0, max(0.3, patterns.confidence))
            
            # Calculate weighted adjustments (less aggressive than full application)
            weighted_seasonal = 1.0 + (seasonal_adjustment - 1.0) * confidence_weight * 0.8
            weighted_weekly = 1.0 + (weekly_adjustment - 1.0) * confidence_weight * 0.6
            weighted_hourly = 1.0 + (hourly_adjustment - 1.0) * confidence_weight * 0.4
            
            # Apply adjustments sequentially
            adjusted_prediction = base_prediction
            adjusted_prediction *= weighted_seasonal
            adjusted_prediction *= weighted_weekly
            adjusted_prediction *= weighted_hourly
            adjusted_prediction *= patterns.trend_factor
            
            # Ensure reasonable bounds
            adjusted_prediction = max(base_prediction * 0.5, 
                                    min(base_prediction * 2.0, adjusted_prediction))
            
            self.logger.debug(f"Pattern adjustment: {base_prediction:.1f} -> {adjusted_prediction:.1f} "
                            f"(seasonal: {weighted_seasonal:.3f}, weekly: {weighted_weekly:.3f}, "
                            f"hourly: {weighted_hourly:.3f}, trend: {patterns.trend_factor:.3f})")
            
            return adjusted_prediction
            
        except Exception as e:
            self.logger.warning(f"Pattern adjustment failed: {e}")
            return base_prediction  # Return original if adjustment fails