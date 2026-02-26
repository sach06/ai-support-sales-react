"""
Prediction service for sales hit rate forecasting
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple
from pathlib import Path


class PredictionService:
    """Service for predicting sales hit rates"""
    
    def __init__(self):
        self.model = None
        self.feature_columns = [
            'company_size', 'industry_code', 'region_code',
            'installed_base_age', 'past_projects_count',
            'last_purchase_months_ago', 'crm_rating'
        ]
    
    def predict_equipment_hit_rate(self, equipment_data: Dict, customer_data: Dict = None) -> Tuple[float, Dict]:
        """
        Predict sales hit rate for a specific equipment/installation
        
        Args:
            equipment_data: Equipment/installation information
            customer_data: Optional customer context
        
        Returns:
            Tuple of (probability_score, key_drivers)
        """
        features = self._extract_equipment_features(equipment_data, customer_data)
        score = self._heuristic_equipment_prediction(features)
        drivers = self._identify_equipment_drivers(features, score)
        
        return score, drivers
    
    def predict_hit_rate(self, customer_data: Dict) -> Tuple[float, Dict]:
        """
        Predict sales hit rate for a customer (aggregated across equipment)
        
        Args:
            customer_data: Customer information dictionary
        
        Returns:
            Tuple of (probability_score, key_drivers)
        """
        # If customer has installed base, calculate per-equipment and aggregate
        if 'installed_base' in customer_data and customer_data['installed_base']:
            equipment_scores = []
            for equipment in customer_data['installed_base']:
                score, _ = self.predict_equipment_hit_rate(equipment, customer_data.get('crm', {}))
                equipment_scores.append(score)
            
            # Average score across all equipment
            avg_score = sum(equipment_scores) / len(equipment_scores) if equipment_scores else 50.0
            
            # Get drivers based on aggregated features
            features = self._extract_features(customer_data)
            drivers = self._identify_drivers(features, avg_score)
            
            return round(avg_score, 1), drivers
        else:
            # Fallback to customer-level prediction
            features = self._extract_features(customer_data)
            score = self._heuristic_prediction(features)
            drivers = self._identify_drivers(features, score)
            
            return score, drivers
        
        # For now, use a simple heuristic model
        # TODO: Replace with trained XGBoost model
        score = self._heuristic_prediction(features)
        
        # Identify key drivers
        drivers = self._identify_drivers(features, score)
        
        return score, drivers
    
    def _extract_features(self, customer_data: Dict) -> Dict:
        """Extract features from customer data"""
        features = {}
        
        crm = customer_data.get('crm', {})
        if crm is None: crm = {}
        
        installed = customer_data.get('installed_base', [])
        if installed is None: installed = []
        
        # Company size (employees)
        fte = crm.get('fte', crm.get('employees', 0))
        if fte is None: 
            fte = 0
        
        if isinstance(fte, str):
            try:
                fte = int(fte.replace(',', '').split('.')[0])
            except:
                fte = 0
        features['company_size'] = fte
        
        # Industry (simplified encoding)
        industry = str(crm.get('industry', 'unknown') or 'unknown')
        features['industry_code'] = hash(industry) % 10
        
        # Region
        region = str(crm.get('region', crm.get('country', 'unknown')) or 'unknown')
        features['region_code'] = hash(region) % 5
        
        # Installed base age (average)
        if installed:
            ages = []
            for item in installed:
                year = item.get('installation_year', item.get('year', 2020))
                if pd.notna(year):
                    try:
                        ages.append(2026 - int(float(year)))
                    except:
                        pass
            features['installed_base_age'] = float(np.mean(ages)) if ages else 5.0
        else:
            features['installed_base_age'] = 0.0
        
        # Past projects
        proj_count = crm.get('projects_count')
        if proj_count is None:
            proj_count = len(installed)
        features['past_projects_count'] = int(proj_count)
        
        # Last purchase
        last_purch = crm.get('last_purchase_months')
        if last_purch is None:
            last_purch = 24
        features['last_purchase_months_ago'] = float(last_purch)
        
        # CRM rating
        rating = str(crm.get('rating', crm.get('crm_rating', 'C')) or 'C')
        rating_map = {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'E': 1}
        features['crm_rating'] = rating_map.get(rating, 3)
        
        return features
    
    def _heuristic_prediction(self, features: Dict) -> float:
        """Simple heuristic prediction (placeholder for ML model)"""
        score = 50.0  # Base score
        
        # Company size factor
        if features['company_size'] > 1000:
            score += 10
        elif features['company_size'] > 500:
            score += 5
        
        # Installed base age (older = more likely to need modernization)
        if features['installed_base_age'] > 15:
            score += 20
        elif features['installed_base_age'] > 10:
            score += 10
        
        # Past projects (relationship strength)
        score += min(features['past_projects_count'] * 2, 15)
        
        # Recent activity
        if features['last_purchase_months_ago'] < 12:
            score += 10
        elif features['last_purchase_months_ago'] > 36:
            score -= 10
        
        # CRM rating
        score += (features['crm_rating'] - 3) * 5
        
        # Normalize to 0-100
        score = max(0, min(100, score))
        
        return round(score, 1)
    
    def _identify_drivers(self, features: Dict, score: float) -> Dict:
        """Identify key drivers of the prediction"""
        drivers = {
            "positive": [],
            "negative": [],
            "neutral": []
        }
        
        # Installed base age
        age = features['installed_base_age']
        if age > 15:
            drivers['positive'].append(f"Equipment age ({age:.0f} years) indicates high modernization potential")
        elif age > 10:
            drivers['positive'].append(f"Equipment age ({age:.0f} years) suggests upcoming modernization needs")
        elif age < 5:
            drivers['negative'].append(f"Recent equipment ({age:.0f} years) reduces immediate modernization need")
        
        # Company size
        size = features['company_size']
        if size > 1000:
            drivers['positive'].append(f"Large company ({size:,} employees) with significant budget")
        elif size < 100:
            drivers['negative'].append(f"Small company ({size} employees) may have budget constraints")
        
        # Relationship
        projects = features['past_projects_count']
        if projects > 5:
            drivers['positive'].append(f"Strong relationship ({projects} past projects)")
        elif projects == 0:
            drivers['negative'].append("No previous project history")
        
        # Recent activity
        last_purchase = features['last_purchase_months_ago']
        if last_purchase < 12:
            drivers['positive'].append(f"Recent purchase ({last_purchase} months ago) shows active engagement")
        elif last_purchase > 36:
            drivers['negative'].append(f"No recent purchases ({last_purchase} months since last order)")
        
        # CRM rating
        rating = features['crm_rating']
        if rating >= 4:
            drivers['positive'].append(f"High CRM rating (A/B tier customer)")
        elif rating <= 2:
            drivers['negative'].append(f"Low CRM rating (D/E tier customer)")
        
        return drivers
    
    def _extract_equipment_features(self, equipment_data: Dict, customer_data: Dict = None) -> Dict:
        """Extract features from equipment/installation data"""
        features = {}
        
        # Equipment age
        year = equipment_data.get('installation_year', equipment_data.get('year', 2020))
        if pd.notna(year):
            try:
                features['equipment_age'] = 2026 - int(float(year))
            except (ValueError, TypeError):
                features['equipment_age'] = 5
        else:
            features['equipment_age'] = 5
        
        # Equipment type/criticality
        equipment_type = str(equipment_data.get('equipment', equipment_data.get('equipment_type', ''))).lower()
        
        # Critical equipment types that are more likely to need modernization
        critical_types = ['furnace', 'blast', 'arc', 'casting', 'rolling']
        features['is_critical'] = any(ct in equipment_type for ct in critical_types)
        
        # OEM (SMS equipment gets higher score)
        oem = str(equipment_data.get('oem', equipment_data.get('manufacturer', ''))).lower()
        features['is_sms_equipment'] = 'sms' in oem
        
        # Last maintenance
        last_maint = equipment_data.get('last_maintenance', equipment_data.get('last_service', ''))
        if last_maint:
            try:
                from datetime import datetime
                maint_date = pd.to_datetime(last_maint)
                days_since = (datetime.now() - maint_date).days
                features['months_since_maintenance'] = days_since / 30
            except:
                features['months_since_maintenance'] = 12
        else:
            features['months_since_maintenance'] = 12
        
        # Customer context (if available)
        if customer_data:
            rating = customer_data.get('rating', customer_data.get('crm_rating', 'C'))
            rating_map = {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'E': 1}
            features['customer_rating'] = rating_map.get(rating, 3)
        else:
            features['customer_rating'] = 3
        
        return features
    
    def _heuristic_equipment_prediction(self, features: Dict) -> float:
        """Predict hit rate for specific equipment"""
        score = 40.0  # Base score (lower than customer-level)
        
        # Equipment age is the primary driver
        age = features['equipment_age']
        if age > 20:
            score += 35
        elif age > 15:
            score += 25
        elif age > 10:
            score += 15
        elif age < 5:
            score -= 10
        
        # Critical equipment types
        if features['is_critical']:
            score += 10
        
        # SMS equipment (existing relationship)
        if features['is_sms_equipment']:
            score += 10
        
        # Maintenance history
        months_maint = features['months_since_maintenance']
        if months_maint > 24:
            score += 10
        elif months_maint > 12:
            score += 5
        
        # Customer rating
        score += (features['customer_rating'] - 3) * 5
        
        # Normalize
        score = max(0, min(100, score))
        
        return round(score, 1)
    
    def _identify_equipment_drivers(self, features: Dict, score: float) -> Dict:
        """Identify key drivers for equipment-level prediction"""
        drivers = {
            "positive": [],
            "negative": [],
            "neutral": []
        }
        
        # Equipment age
        age = features['equipment_age']
        if age > 20:
            drivers['positive'].append(f"Very old equipment ({age} years) - high modernization priority")
        elif age > 15:
            drivers['positive'].append(f"Aging equipment ({age} years) - modernization recommended")
        elif age > 10:
            drivers['positive'].append(f"Mature equipment ({age} years) - approaching modernization window")
        elif age < 5:
            drivers['negative'].append(f"Recent installation ({age} years) - low immediate need")
        
        # Equipment type
        if features['is_critical']:
            drivers['positive'].append("Critical equipment type - high business impact")
        
        # OEM relationship
        if features['is_sms_equipment']:
            drivers['positive'].append("SMS equipment - existing relationship advantage")
        else:
            drivers['neutral'].append("Non-SMS equipment - opportunity for conversion")
        
        # Maintenance
        months_maint = features['months_since_maintenance']
        if months_maint > 24:
            drivers['positive'].append(f"No recent maintenance ({months_maint:.0f} months) - potential reliability issues")
        elif months_maint > 12:
            drivers['positive'].append(f"Maintenance due ({months_maint:.0f} months since last service)")
        
        return drivers



# Singleton instance
prediction_service = PredictionService()
