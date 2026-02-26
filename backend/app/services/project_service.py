"""
Project Service - Track projects, sub-projects, timelines, and budgets
"""
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ProjectService:
    """Service for managing project data and analytics"""
    
    def get_project_summary(self, customer_data: Dict) -> Dict:
        """
        Generate project summary for a customer
        
        Returns:
            {
                'total_projects': int,
                'active_projects': int,
                'completed_projects': int,
                'total_value': float,
                'projects': List[Dict]
            }
        """
        # Extract project data from CRM
        # This would be enhanced based on actual CRM schema
        projects = customer_data.get('projects', [])
        
        if not projects:
            return {
                'total_projects': 0,
                'active_projects': 0,
                'completed_projects': 0,
                'total_value': 0.0,
                'projects': []
            }
        
        active = sum(1 for p in projects if p.get('status') == 'Active')
        completed = sum(1 for p in projects if p.get('status') == 'Completed')
        total_value = sum(p.get('value', 0) for p in projects)
        
        return {
            'total_projects': len(projects),
            'active_projects': active,
            'completed_projects': completed,
            'total_value': total_value,
            'projects': projects
        }
    
    def get_project_timeline_data(self, projects: List[Dict]) -> List[Dict]:
        """
        Prepare data for Gantt chart visualization
        
        Returns:
            [
                {
                    'Task': str,
                    'Start': datetime,
                    'Finish': datetime,
                    'Resource': str,
                    'Progress': float
                },
                ...
            ]
        """
        timeline_data = []
        
        for project in projects:
            if not project.get('start_date') or not project.get('end_date'):
                continue
            
            try:
                start = pd.to_datetime(project['start_date'])
                end = pd.to_datetime(project['end_date'])
                
                timeline_data.append({
                    'Task': project.get('name', 'Unnamed Project'),
                    'Start': start,
                    'Finish': end,
                    'Resource': project.get('type', 'General'),
                    'Progress': project.get('progress', 0) / 100.0 if project.get('progress') else 0
                })
            except Exception as e:
                logger.warning(f"Could not parse project timeline: {e}")
                continue
        
        return timeline_data
    
    def calculate_project_health(self, project: Dict) -> str:
        """
        Calculate project health status
        
        Returns:
            'On Track', 'At Risk', 'Delayed', or 'Unknown'
        """
        progress = project.get('progress', 0)
        status = project.get('status', '').lower()
        
        if status == 'completed':
            return 'Completed'
        
        if status == 'cancelled' or status == 'on hold':
            return 'On Hold'
        
        try:
            start = pd.to_datetime(project.get('start_date'))
            end = pd.to_datetime(project.get('end_date'))
            now = datetime.now()
            
            if now > end:
                return 'Delayed'
            
            # Calculate expected progress
            total_duration = (end - start).days
            elapsed = (now - start).days
            expected_progress = (elapsed / total_duration) * 100 if total_duration > 0 else 0
            
            # Compare actual vs expected
            if progress >= expected_progress - 10:
                return 'On Track'
            elif progress >= expected_progress - 25:
                return 'At Risk'
            else:
                return 'Delayed'
                
        except Exception:
            return 'Unknown'
    
    def get_project_risks(self, project: Dict) -> List[Dict]:
        """
        Identify project risks
        
        Returns:
            [
                {
                    'risk': str,
                    'severity': str,  # 'High', 'Medium', 'Low'
                    'mitigation': str
                },
                ...
            ]
        """
        risks = []
        
        # Budget risk
        budget = project.get('budget', 0)
        spent = project.get('spent', 0)
        if budget > 0:
            if spent > budget * 0.9:
                risks.append({
                    'risk': 'Budget Overrun',
                    'severity': 'High',
                    'mitigation': 'Review cost controls and seek budget amendment'
                })
            elif spent > budget * 0.75:
                risks.append({
                    'risk': 'Budget Pressure',
                    'severity': 'Medium',
                    'mitigation': 'Monitor spending closely'
                })
        
        # Timeline risk
        health = self.calculate_project_health(project)
        if health == 'Delayed':
            risks.append({
                'risk': 'Schedule Delay',
                'severity': 'High',
                'mitigation': 'Resource reallocation and schedule compression'
            })
        elif health == 'At Risk':
            risks.append({
                'risk': 'Schedule Risk',
                'severity': 'Medium',
                'mitigation': 'Increase monitoring frequency'
            })
        
        return risks
    
    def get_sub_projects(self, parent_project_id: str, all_projects: List[Dict]) -> List[Dict]:
        """
        Get hierarchical sub-projects
        
        Returns:
            List of sub-projects with their dependencies
        """
        sub_projects = [
            p for p in all_projects 
            if p.get('parent_id') == parent_project_id
        ]
        
        return sub_projects
    
    def calculate_project_metrics(self, projects: List[Dict]) -> Dict:
        """
        Calculate aggregate project metrics
        
        Returns:
            {
                'average_duration_days': float,
                'completion_rate': float,
                'on_time_delivery_rate': float,
                'average_budget_variance': float,
                'total_value': float
            }
        """
        if not projects:
            return {
                'average_duration_days': 0,
                'completion_rate': 0,
                'on_time_delivery_rate': 0,
                'average_budget_variance': 0,
                'total_value': 0
            }
        
        completed = [p for p in projects if p.get('status', '').lower() == 'completed']
        
        # Average duration
        durations = []
        for p in completed:
            try:
                start = pd.to_datetime(p.get('start_date'))
                end = pd.to_datetime(p.get('end_date'))
                durations.append((end - start).days)
            except:
                continue
        
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Completion rate
        completion_rate = (len(completed) / len(projects)) * 100 if projects else 0
        
        # On-time delivery
        on_time = sum(1 for p in completed if p.get('delivered_on_time', False))
        on_time_rate = (on_time / len(completed)) * 100 if completed else 0
        
        # Budget variance
        variances = []
        for p in projects:
            budget = p.get('budget', 0)
            spent = p.get('spent', 0)
            if budget > 0:
                variance = ((spent - budget) / budget) * 100
                variances.append(variance)
        
        avg_variance = sum(variances) / len(variances) if variances else 0
        
        # Total value
        total_value = sum(p.get('value', 0) for p in projects)
        
        return {
            'average_duration_days': avg_duration,
            'completion_rate': completion_rate,
            'on_time_delivery_rate': on_time_rate,
            'average_budget_variance': avg_variance,
            'total_value': total_value
        }


# Singleton instance
project_service = ProjectService()
