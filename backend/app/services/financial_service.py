"""
Financial Service - Cost analysis, budget tracking, and financial projections
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class FinancialService:
    """Service for financial analysis and cost management"""
    
    def get_cost_breakdown(self, project_data: Dict) -> Dict:
        """
        Generate detailed cost breakdown
        
        Returns:
            {
                'material_costs': float,
                'labor_costs': float,
                'overhead_costs': float,
                'total_costs': float,
                'cost_by_category': Dict[str, float]
            }
        """
        costs = project_data.get('costs', {})
        
        material = costs.get('materials', 0)
        labor = costs.get('labor', 0)
        overhead = costs.get('overhead', 0)
        other = costs.get('other', 0)
        
        return {
            'material_costs': material,
            'labor_costs': labor,
            'overhead_costs': overhead,
            'other_costs': other,
            'total_costs': material + labor + overhead + other,
            'cost_by_category': {
                'Materials': material,
                'Labor': labor,
                'Overhead': overhead,
                'Other': other
            }
        }
    
    def calculate_budget_variance(self, budgeted: float, actual: float) -> Dict:
        """
        Calculate budget variance analysis
        
        Returns:
            {
                'budgeted': float,
                'actual': float,
                'variance': float,
                'variance_percent': float,
                'status': str  # 'Under Budget', 'On Budget', 'Over Budget'
            }
        """
        variance = actual - budgeted
        variance_percent = (variance / budgeted * 100) if budgeted > 0 else 0
        
        if variance_percent <  -5:
            status = 'Under Budget'
        elif variance_percent > 5:
            status = 'Over Budget'
        else:
            status = 'On Budget'
        
        return {
            'budgeted': budgeted,
            'actual': actual,
            'variance': variance,
            'variance_percent': variance_percent,
            'status': status
        }
    
    def analyze_cost_trends(self, historical_costs: List[Dict]) -> Dict:
        """
        Analyze cost trends over time
        
        Args:
            historical_costs: [{'date': datetime, 'amount': float, 'category': str}, ...]
        
        Returns:
            {
                'trend': str,  # 'Increasing', 'Decreasing', 'Stable'
                'average_monthly_cost': float,
                'growth_rate': float,
                'cost_volatility': float
            }
        """
        if not historical_costs:
            return {
                'trend': 'Unknown',
                'average_monthly_cost': 0,
                'growth_rate': 0,
                'cost_volatility': 0
            }
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(historical_costs)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # Monthly aggregation
        monthly = df.groupby(pd.Grouper(key='date', freq='M'))['amount'].sum()
        
        if len(monthly) < 2:
            return {
                'trend': 'Insufficient Data',
                'average_monthly_cost': monthly.mean() if not monthly.empty else 0,
                'growth_rate': 0,
                'cost_volatility': 0
            }
        
        # Calculate trend
        x = np.arange(len(monthly))
        y = monthly.values
        slope, intercept = np.polyfit(x, y, 1)
        
        if slope > monthly.mean() * 0.05:
            trend = 'Increasing'
        elif slope < -monthly.mean() * 0.05:
            trend = 'Decreasing'
        else:
            trend = 'Stable'
        
        # Growth rate (comparing first and last period)
        growth_rate = ((monthly.iloc[-1] - monthly.iloc[0]) / monthly.iloc[0] * 100) if monthly.iloc[0] > 0 else 0
        
        # Volatility (standard deviation / mean)
        volatility = (monthly.std() / monthly.mean() * 100) if monthly.mean() > 0 else 0
        
        return {
            'trend': trend,
            'average_monthly_cost': monthly.mean(),
            'growth_rate': growth_rate,
            'cost_volatility': volatility
        }
    
    def generate_scenario_analysis(self, base_cost: float, base_revenue: float) -> Dict:
        """
        Generate best/worst/expected case scenarios
        
        Returns:
            {
                'best_case': {'cost': float, 'revenue': float, 'margin': float},
                'expected_case': {'cost': float, 'revenue': float, 'margin': float},
                'worst_case': {'cost': float, 'revenue': float, 'margin': float}
            }
        """
        def calculate_margin(revenue, cost):
            return ((revenue - cost) / revenue * 100) if revenue > 0 else 0
        
        # Best case: 10% lower costs, 15% higher revenue
        best_cost = base_cost * 0.9
        best_revenue = base_revenue * 1.15
        
        # Worst case: 15% higher costs, 10% lower revenue
        worst_cost = base_cost * 1.15
        worst_revenue = base_revenue * 0.9
        
        return {
            'best_case': {
                'cost': best_cost,
                'revenue': best_revenue,
                'margin': calculate_margin(best_revenue, best_cost)
            },
            'expected_case': {
                'cost': base_cost,
                'revenue': base_revenue,
                'margin': calculate_margin(base_revenue, base_cost)
            },
            'worst_case': {
                'cost': worst_cost,
                'revenue': worst_revenue,
                'margin': calculate_margin(worst_revenue, worst_cost)
            }
        }
    
    def calculate_profitability_metrics(self, financial_data: Dict) -> Dict:
        """
        Calculate key profitability metrics
        
        Returns:
            {
                'gross_margin': float,
                'net_margin': float,
                'roi': float,
                'ebitda_margin': float
            }
        """
        revenue = financial_data.get('revenue', 0)
        cogs = financial_data.get('cogs', 0)
        operating_expenses = financial_data.get('operating_expenses', 0)
        net_income = financial_data.get('net_income', 0)
        ebitda = financial_data.get('ebitda', 0)
        investment = financial_data.get('investment', 1)  # Avoid division by zero
        
        return {
            'gross_margin': ((revenue - cogs) / revenue * 100) if revenue > 0 else 0,
            'net_margin': (net_income / revenue * 100) if revenue > 0 else 0,
            'roi': (net_income / investment * 100) if investment > 0 else 0,
            'ebitda_margin': (ebitda / revenue * 100) if revenue > 0 else 0
        }
    
    def forecast_costs(self, historical_costs: List[Dict], periods: int = 12) -> List[Dict]:
        """
        Forecast future costs based on historical data
        
        Args:
            historical_costs: Historical cost data
            periods: Number of periods to forecast
        
        Returns:
            [{'period': int, 'forecasted_cost': float, 'confidence_lower': float, 'confidence_upper': float}, ...]
        """
        if not historical_costs or len(historical_costs) < 3:
            return []
        
        df = pd.DataFrame(historical_costs)
        df['date'] = pd.to_datetime(df['date'])
        monthly = df.groupby(pd.Grouper(key='date', freq='M'))['amount'].sum()
        
        # Simple linear regression forecast
        x = np.arange(len(monthly))
        y = monthly.values
        
        slope, intercept = np.polyfit(x, y, 1)
        
        # Forecast
        forecasts = []
        std_dev = monthly.std()
        
        for i in range(periods):
            period_num = len(monthly) + i
            forecast = slope * period_num + intercept
            
            # Confidence interval (simple ±2 std dev)
            forecasts.append({
                'period': i + 1,
                'forecasted_cost': max(0, forecast),
                'confidence_lower': max(0, forecast - 2 * std_dev),
                'confidence_upper': forecast + 2 * std_dev
            })
        
        return forecasts
    
    def calculate_cost_efficiency(self, costs: float, output: float, unit: str = 'units') -> Dict:
        """
        Calculate cost efficiency metrics
        
        Returns:
            {
                'cost_per_unit': float,
                'efficiency_rating': str,  # 'Excellent', 'Good', 'Average', 'Poor'
                'benchmark_comparison': float
            }
        """
        cost_per_unit = costs / output if output > 0 else 0
        
        # This would ideally compare against industry benchmarks
        # For now, use simple rating
        if cost_per_unit < 100:
            rating = 'Excellent'
        elif cost_per_unit < 500:
            rating = 'Good'
        elif cost_per_unit < 1000:
            rating = 'Average'
        else:
            rating = 'Poor'
        
        return {
            'cost_per_unit': cost_per_unit,
            'unit': unit,
            'efficiency_rating': rating,
            'benchmark_comparison': 0  # Would require external benchmark data
        }


# Singleton instance
financial_service = FinancialService()
