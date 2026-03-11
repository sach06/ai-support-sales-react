"""
Export API Routes — Handle downloading the generated profile as DOCX or PDF.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Path as URLPath, Body
from fastapi.responses import StreamingResponse
from typing import Dict, Any
import sys
from pathlib import Path
from urllib.parse import quote

# Ensure the backend root is on the path so services resolve correctly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.export_service import export_service
from app.services.enhanced_export_service import enhanced_export_service
from app.services.data_service import data_service
from app.services.historical_service import get_yearly_performance, get_ib_summary
from app.services.web_enrichment_service import web_enrichment_service
import plotly.express as px
import pandas as pd

def _generate_export_charts(customer_name: str, details: Dict[str, Any] = None) -> Dict[str, Any]:
    charts = {}
    try:
        if details is None:
            details = data_service.get_customer_detail(customer_name)
        ib_data = details.get('installed_base', [])
        if ib_data:
            df = pd.DataFrame(ib_data)
            
            # Map Chart
            if 'latitude_internal' in df.columns and 'longitude_internal' in df.columns:
                geo_df = df.dropna(subset=['latitude_internal', 'longitude_internal'])
                if not geo_df.empty:
                    fig = px.scatter_geo(
                        geo_df, lat='latitude_internal', lon='longitude_internal', 
                        hover_name='city_internal' if 'city_internal' in df.columns else None,
                        title=f"Global Footprint - {customer_name}",
                        color_discrete_sequence=['#1f4788']
                    )
                    fig.update_layout(geo=dict(showland=True, landcolor="#f3f4f6", countrycolor="#d1d5db"), margin={"r":0,"t":40,"l":0,"b":0})
                    charts['Locations Map'] = fig
                    
            # Equipment Breakdown Chart (Pie)
            equip_col = 'equipment' if 'equipment' in df.columns else 'equipment_type'
            if equip_col in df.columns:
                counts = df[equip_col].value_counts().reset_index()
                counts.columns = ['Equipment', 'Count']
                fig2 = px.pie(counts, values='Count', names='Equipment', title=f"Portfolio Mix")
                fig2.update_traces(textposition='inside', textinfo='percent+label')
                charts['Equipment Distribution'] = fig2

            # Operational Status Distribution
            if 'status' in df.columns:
                stat_counts = df['status'].value_counts().reset_index()
                stat_counts.columns = ['Status', 'Count']
                fig3 = px.bar(stat_counts, x='Status', y='Count', title="Asset Status", color='Status')
                charts['Status Distribution'] = fig3

            # Age Distribution (If available)
            if 'age_years' in df.columns:
                df_age = df.dropna(subset=['age_years'])
                if not df_age.empty:
                    fig4 = px.histogram(df_age, x='age_years', nbins=10, title="Fleet Age (Years)", color_discrete_sequence=['#ff6b6b'])
                    charts['Age Distribution'] = fig4

            # Capacity Distribution (If available)
            if 'capacity' in df.columns:
                df_cap = df.dropna(subset=['capacity'])
                if not df_cap.empty:
                    fig5 = px.box(df_cap, y='capacity', title="Capacity Profile", color_discrete_sequence=['#4ecdc4'])
                    charts['Capacity Profile'] = fig5
                
    except Exception as e:
        print(f"Failed to generate charts: {e}")
    return charts

router = APIRouter()

@router.post("/docx")
def export_docx(payload: Dict[str, Any] = Body(...)):
    """Export profile to Enhanced DOCX."""
    profile = payload.get("profile")
    customer_name = payload.get("customer_name")
    
    if not profile or not customer_name:
        raise HTTPException(status_code=400, detail="Missing profile or customer_name in payload")
        
    try:
        details = data_service.get_customer_detail(customer_name)
        charts = _generate_export_charts(customer_name, details)
        crm_history = get_yearly_performance(customer_name)
        ib_summary = get_ib_summary(customer_name)
        
        # Inject news dynamically if it was missing from the AI profile output
        if 'recent_news' not in profile:
            news = web_enrichment_service.get_recent_news(customer_name, limit=5)
            if news:
                profile['recent_news'] = news
        
        buffer = enhanced_export_service.generate_comprehensive_docx(
            customer_name=customer_name,
            profile_data=profile,
            customer_data={'projects': details.get('crm', {}).get('projects', []), 'installed_base': details.get('installed_base', [])},
            charts=charts,
            crm_history=crm_history,
            ib_data=ib_summary
        )
        filename = enhanced_export_service.generate_filename(customer_name, "docx")
        
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename*=utf-8''{quote(filename)}"}
        )
    except Exception as e:
        import traceback
        print(f"DOCX Export error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pdf")
def export_pdf(payload: Dict[str, Any] = Body(...)):
    """Export profile to PDF by first generating DOCX, then converting it."""
    profile = payload.get("profile")
    customer_name = payload.get("customer_name")
    
    if not profile or not customer_name:
        raise HTTPException(status_code=400, detail="Missing profile or customer_name in payload")
        
    try:
        details = data_service.get_customer_detail(customer_name)
        charts = _generate_export_charts(customer_name, details)
        crm_history = get_yearly_performance(customer_name)
        ib_summary = get_ib_summary(customer_name)
        
        # Inject news dynamically if it was missing from the AI profile output
        if 'recent_news' not in profile:
            news = web_enrichment_service.get_recent_news(customer_name, limit=5)
            if news:
                profile['recent_news'] = news
        
        docx_buffer = enhanced_export_service.generate_comprehensive_docx(
            customer_name=customer_name,
            profile_data=profile,
            customer_data={'projects': details.get('crm', {}).get('projects', []), 'installed_base': details.get('installed_base', [])},
            charts=charts,
            crm_history=crm_history,
            ib_data=ib_summary
        )

        try:
            buffer = enhanced_export_service.convert_docx_to_pdf(docx_buffer)
        except Exception as conv_err:
            # Keep export functional even when Word/docx2pdf is not available.
            print(f"DOCX->PDF conversion failed, falling back to native PDF renderer: {conv_err}")
            buffer = enhanced_export_service.generate_comprehensive_pdf(
                customer_name=customer_name,
                profile_data=profile,
                customer_data={'projects': details.get('crm', {}).get('projects', []), 'installed_base': details.get('installed_base', [])},
                charts=charts,
                crm_history=crm_history,
                ib_data=ib_summary
            )
        filename = enhanced_export_service.generate_filename(customer_name, "pdf")
        
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename*=utf-8''{quote(filename)}"}
        )
    except Exception as e:
        import traceback
        print(f"PDF Export error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
