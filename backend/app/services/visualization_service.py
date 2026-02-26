"""
Visualization Service - Professional charts and graphs
Based on Axel Windbrake's visualization patterns
NO EMOJIS - Professional styling only
"""
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class VisualizationService:
    """Service for generating professional visualizations"""
    
    def __init__(self):
        # Professional color scheme (corporate blues/grays)
        self.color_scheme = {
            'primary': '#003366',     # Dark blue
            'secondary': '#0066CC',   # Medium blue
            'accent': '#6699CC',      # Light blue
            'success': '#28a745',     # Green
            'warning': '#ffc107',     # Amber
            'danger': '#dc3545',      # Red
            'neutral': '#6c757d'      # Gray
        }
        
        # Professional template
        self.template = 'plotly_white'
    
    def create_revenue_trend_chart(self, data: pd.DataFrame, x_col: str, y_col: str, title: str = 'Revenue Trend') -> go.Figure:
        """
        Create revenue trend line chart
        
        Args:
            data: DataFrame with time series data
            x_col: Column name for x-axis (dates)
            y_col: Column name for y-axis (revenue)
            title: Chart title
        
        Returns:
            Plotly figure object
        """
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=data[x_col],
            y=data[y_col],
            mode='lines+markers',
            name='Revenue',
            line=dict(color=self.color_scheme['primary'], width=3),
            marker=dict(size=8, color=self.color_scheme['secondary']),
            hovertemplate='<b>%{x}</b><br>Revenue: $%{y:,.2f}<extra></extra>'
        ))
        
        fig.update_layout(
            title=title,
            xaxis_title='Period',
            yaxis_title='Revenue ($)',
            template=self.template,
            hovermode='x unified',
            showlegend=True
        )
        
        return fig
    
    def create_project_distribution_chart(self, data: Dict[str, int], title: str = 'Project Distribution') -> go.Figure:
        """
        Create project distribution pie/donut chart
        
        Args:
            data: Dictionary of {category: count}
            title: Chart title
        
        Returns:
            Plotly figure object
        """
        labels = list(data.keys())
        values = list(data.values())
        
        colors = [
            self.color_scheme['primary'],
            self.color_scheme['secondary'],
            self.color_scheme['accent'],
            self.color_scheme['success'],
            self.color_scheme['neutral']
        ]
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4,  # Donut chart
            marker=dict(colors=colors),
            textinfo='label+percent',
            hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
        )])
        
        fig.update_layout(
            title=title,
            template=self.template,
            showlegend=True
        )
        
        return fig
    
    def create_gantt_chart(self, projects: pd.DataFrame) -> go.Figure:
        """
        Create Gantt chart for project timelines
        
        Args:
            projects: DataFrame with columns ['Task', 'Start', 'Finish', 'Resource']
        
        Returns:
            Plotly figure object
        """
        # Use plotly express for Gantt chart
        fig = px.timeline(
            projects,
            x_start='Start',
            x_end='Finish',
            y='Task',
            color='Resource',
            title='Project Timeline'
        )
        
        fig.update_yaxes(categoryorder='total ascending')
        fig.update_layout(
            template=self.template,
            xaxis_title='Timeline',
            yaxis_title='Projects',
            showlegend=True
        )
        
        return fig
    
    def create_kpi_scorecard(self, kpis: Dict[str, Dict]) -> go.Figure:
        """
        Create KPI scorecard with multiple metrics
        
        Args:
            kpis: Dict of {kpi_name: {'value': float, 'target': float, 'unit': str}}
        
        Returns:
            Plotly figure object with subplots
        """
        kpi_names = list(kpis.keys())
        n_kpis = len(kpi_names)
        
        # Create subplots for each KPI
        fig = make_subplots(
            rows=1,
            cols=n_kpis,
            specs=[[{'type': 'indicator'}] * n_kpis],
            subplot_titles=kpi_names
        )
        
        for idx, (name, data) in enumerate(kpis.items(), 1):
            value = data.get('value', 0)
            target = data.get('target', value)
            unit = data.get('unit', '')
            
            # Calculate percentage of target
            pct_of_target = (value / target * 100) if target > 0 else 0
            
            # Determine color based on performance
            if pct_of_target >= 100:
                color = self.color_scheme['success']
            elif pct_of_target >= 80:
                color = self.color_scheme['warning']
            else:
                color = self.color_scheme['danger']
            
            fig.add_trace(
                go.Indicator(
                    mode='number+delta',
                    value=value,
                    delta={'reference': target, 'relative': False},
                    number={'suffix': unit},
                    domain={'x': [0, 1], 'y': [0, 1]}
                ),
                row=1,
                col=idx
            )
        
        fig.update_layout(
            title='Key Performance Indicators',
            template=self.template,
            height=300
        )
        
        return fig
    
    def create_cost_breakdown_chart(self, costs: Dict[str, float], title: str = 'Cost Breakdown') -> go.Figure:
        """
        Create cost breakdown bar chart
        
        Args:
            costs: Dictionary of {category: amount}
            title: Chart title
        
        Returns:
            Plotly figure object
        """
        categories = list(costs.keys())
        amounts = list(costs.values())
        
        fig = go.Figure(data=[
            go.Bar(
                x=categories,
                y=amounts,
                marker=dict(
                    color=self.color_scheme['primary'],
                    line=dict(color=self.color_scheme['secondary'], width=2)
                ),
                text=[f'${amt:,.0f}' for amt in amounts],
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>Amount: $%{y:,.2f}<extra></extra>'
            )
        ])
        
        fig.update_layout(
            title=title,
            xaxis_title='Category',
            yaxis_title='Amount ($)',
            template=self.template,
            showlegend=False
        )
        
        return fig
    
    def create_budget_variance_chart(self, data: pd.DataFrame) -> go.Figure:
        """
        Create budget vs actual comparison chart
        
        Args:
            data: DataFrame with columns ['Category', 'Budgeted', 'Actual']
        
        Returns:
            Plotly figure object
        """
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='Budgeted',
            x=data['Category'],
            y=data['Budgeted'],
            marker_color=self.color_scheme['secondary'],
            text=data['Budgeted'].apply(lambda x: f'${x:,.0f}'),
            textposition='outside'
        ))
        
        fig.add_trace(go.Bar(
            name='Actual',
            x=data['Category'],
            y=data['Actual'],
            marker_color=self.color_scheme['primary'],
            text=data['Actual'].apply(lambda x: f'${x:,.0f}'),
            textposition='outside'
        ))
        
        fig.update_layout(
            title='Budget vs Actual',
            xaxis_title='Category',
            yaxis_title='Amount ($)',
            template=self.template,
            barmode='group',
            showlegend=True
        )
        
        return fig
    
    def create_waterfall_chart(self, data: pd.DataFrame, title: str = 'Waterfall Analysis') -> go.Figure:
        """
        Create waterfall chart for revenue/cost breakdown
        
        Args:
            data: DataFrame with columns ['Stage', 'Value']
            title: Chart title
        
        Returns:
            Plotly figure object
        """
        fig = go.Figure(go.Waterfall(
            name='',
            orientation='v',
            measure=['relative'] * (len(data) - 1) + ['total'],
            x=data['Stage'],
            y=data['Value'],
            text=data['Value'].apply(lambda x: f'${x:,.0f}'),
            textposition='outside',
            connector={'line': {'color': 'rgb(63, 63, 63)'}},
            increasing={'marker': {'color': self.color_scheme['success']}},
            decreasing={'marker': {'color': self.color_scheme['danger']}},
            totals={'marker': {'color': self.color_scheme['primary']}}
        ))
        
        fig.update_layout(
            title=title,
            template=self.template,
            showlegend=False
        )
        
        return fig
    
    def create_scatter_plot(self, data: pd.DataFrame, x_col: str, y_col: str, color_col: str = None, title: str = 'Scatter Plot') -> go.Figure:
        """
        Create scatter plot for segmentation analysis
        
        Args:
            data: DataFrame with data
            x_col: Column for x-axis
            y_col: Column for y-axis
            color_col: Optional column for color coding
            title: Chart title
        
        Returns:
            Plotly figure object
        """
        if color_col:
            fig = px.scatter(
                data,
                x=x_col,
                y=y_col,
                color=color_col,
                title=title,
                template=self.template
            )
        else:
            fig = go.Figure(data=[go.Scatter(
                x=data[x_col],
                y=data[y_col],
                mode='markers',
                marker=dict(
                    size=10,
                    color=self.color_scheme['primary'],
                    line=dict(width=1, color=self.color_scheme['secondary'])
                ),
                hovertemplate=f'<b>{x_col}</b>: %{{x}}<br><b>{y_col}</b>: %{{y}}<extra></extra>'
            )])
            
            fig.update_layout(
                title=title,
                xaxis_title=x_col,
                yaxis_title=y_col,
                template=self.template
            )
        
        return fig
    
    def create_funnel_chart(self, data: pd.DataFrame, stage_col: str, value_col: str, title: str = 'Sales Funnel') -> go.Figure:
        """
        Create funnel chart for pipeline stages
        
        Args:
            data: DataFrame with pipeline data
            stage_col: Column with stage names
            value_col: Column with values
            title: Chart title
        
        Returns:
            Plotly figure object
        """
        fig = go.Figure(go.Funnel(
            y=data[stage_col],
            x=data[value_col],
            textposition='inside',
            textinfo='value+percent initial',
            marker=dict(color=self.color_scheme['primary']),
            connector={'line': {'color': self.color_scheme['secondary'], 'width': 2}}
        ))
        
        fig.update_layout(
            title=title,
            template=self.template
        )
        
        return fig
    
    def create_heatmap(self, data: pd.DataFrame, title: str = 'Engagement Matrix') -> go.Figure:
        """
        Create heatmap for engagement or correlation analysis
        
        Args:
            data: DataFrame (matrix format)
            title: Chart title
        
        Returns:
            Plotly figure object
        """
        fig = go.Figure(data=go.Heatmap(
            z=data.values,
            x=data.columns,
            y=data.index,
            colorscale='Blues',
            hovertemplate='<b>%{y}</b> - <b>%{x}</b><br>Value: %{z}<extra></extra>'
        ))
        
        fig.update_layout(
            title=title,
            template=self.template
        )
        
        return fig
    
    def create_geographic_map(self, data: pd.DataFrame, title: str = 'Geographic Distribution') -> go.Figure:
        """
        Create choropleth map for geographic data
        
        Args:
            data: DataFrame with columns ['Country', 'Value', 'lat', 'lon']
            title: Chart title
        
        Returns:
            Plotly figure object
        """
        fig = go.Figure(data=go.Scattergeo(
            lon=data['lon'],
            lat=data['lat'],
            text=data['Country'],
            mode='markers',
            marker=dict(
                size=data['Value'] / data['Value'].max() * 50,
                color=self.color_scheme['primary'],
                line=dict(width=1, color=self.color_scheme['secondary']),
                sizemode='area'
            ),
            hovertemplate='<b>%{text}</b><br>Value: %{marker.size}<extra></extra>'
        ))
        
        fig.update_layout(
            title=title,
            geo=dict(
                scope='europe',
                projection_type='natural earth',
                showland=True,
                landcolor='rgb(243, 243, 243)',
                coastlinecolor='rgb(204, 204, 204)'
            ),
            template=self.template
        )
        
        return fig

    def create_revenue_trend(self, years: List[str], revenues: List[float], title: str = "Revenue Trend") -> go.Figure:
        """Create revenue trend chart from lists"""
        df = pd.DataFrame({'Year': years, 'Revenue': revenues})
        return self.create_revenue_trend_chart(df, 'Year', 'Revenue', title)

    def create_equipment_distribution(self, equipment_types: Dict[str, int], title: str = "Equipment Distribution") -> go.Figure:
        """Create equipment distribution donut chart"""
        return self.create_project_distribution_chart(equipment_types, title)

    def create_project_distribution(self, statuses: List[str], counts: List[int], title: str = "Project Distribution") -> go.Figure:
        """Create project distribution donut chart from lists"""
        data = dict(zip(statuses, counts))
        return self.create_project_distribution_chart(data, title)

    def create_cost_breakdown(self, categories: List[str], costs: List[float], title: str = "Cost Breakdown") -> go.Figure:
        """Create cost breakdown bar chart from lists"""
        data = dict(zip(categories, costs))
        return self.create_cost_breakdown_chart(data, title)

    def create_budget_variance(self, projects: List[str], budgets: List[float], actuals: List[float], title: str = "Budget vs Actual") -> go.Figure:
        """Create budget variance group bar chart from lists"""
        df = pd.DataFrame({
            'Category': projects,
            'Budgeted': budgets,
            'Actual': actuals
        })
        return self.create_budget_variance_chart(df)

    def create_cost_forecast(self, periods: List[int], forecasts: List[float], title: str = "Cost Forecast") -> go.Figure:
        """Create cost forecast line chart"""
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=periods,
            y=forecasts,
            mode='lines+markers',
            marker=dict(color=self.color_scheme['secondary']),
            line=dict(color=self.color_scheme['primary'], width=3, dash='dash'),
            name='Forecast'
        ))
        
        fig.update_layout(
            title=title,
            xaxis_title='Period (Months)',
            yaxis_title='Forecasted Amount ($)',
            template=self.template
        )
        
        return fig


# Singleton instance
visualization_service = VisualizationService()
