from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import pandas as pd

from app.services.data_service import data_service


class InteractionService:
    """Load and summarize customer interaction timelines from SAP Sales Cloud exports."""

    def __init__(self) -> None:
        self._data_dir = Path(__file__).resolve().parent.parent.parent / 'data'

    def _find_latest_report(self) -> Path | None:
        candidates = sorted(
            self._data_dir.glob('*Visit Report*.xlsx'),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

    @lru_cache(maxsize=4)
    def _load_report(self, cache_key: str) -> pd.DataFrame:
        report_path = Path(cache_key)
        if not report_path.exists():
            return pd.DataFrame()

        raw = pd.read_excel(report_path, header=0)
        if raw.empty or len(raw.columns) < 11:
            return pd.DataFrame()

        raw = raw.iloc[:, :11].copy()
        raw.columns = [
            'visit_subject',
            'visit_status',
            'visit_account',
            'installed_base',
            'meeting_location',
            'account_country_region',
            'employee_responsible',
            'employee_department',
            'start_dt',
            'end_dt',
            'distribution_channel',
        ]
        raw = raw.dropna(subset=['visit_account'])

        for col in ['visit_subject', 'visit_status', 'visit_account', 'meeting_location', 'account_country_region', 'employee_responsible', 'employee_department', 'distribution_channel']:
            raw[col] = raw[col].fillna('').astype(str).str.strip()

        raw['start_dt'] = pd.to_datetime(raw['start_dt'], errors='coerce')
        raw['end_dt'] = pd.to_datetime(raw['end_dt'], errors='coerce')
        raw['visit_account_norm'] = raw['visit_account'].apply(data_service._normalize_company_name)
        raw['visit_account_group_key'] = raw['visit_account'].apply(data_service._extract_company_group_key)
        raw['duration_hours'] = (raw['end_dt'] - raw['start_dt']).dt.total_seconds().div(3600).round(1)
        return raw

    def _get_report_df(self) -> tuple[pd.DataFrame, Path | None]:
        report_path = self._find_latest_report()
        if not report_path:
            return pd.DataFrame(), None
        return self._load_report(str(report_path)), report_path

    def _match_rows(self, df: pd.DataFrame, company_name: str) -> tuple[pd.DataFrame, Dict[str, object]]:
        selection = data_service.resolve_company_selection(company_name)
        target_names = selection.get('company_names', []) or [selection.get('display_name', company_name)]
        target_norms = {data_service._normalize_company_name(name) for name in target_names if str(name).strip()}
        target_norms = {name for name in target_norms if name}
        target_group_key = selection.get('group_key') or data_service._extract_company_group_key(selection.get('display_name', company_name))

        def _matches(row: pd.Series) -> bool:
            candidate_norm = str(row.get('visit_account_norm') or '')
            if not candidate_norm:
                return False
            if candidate_norm in target_norms:
                return True
            for target_norm in target_norms:
                if candidate_norm.startswith(target_norm) or target_norm.startswith(candidate_norm):
                    return True
                if selection.get('selection_type') == 'company' and (target_norm in candidate_norm or candidate_norm in target_norm):
                    return True
            return bool(selection.get('selection_type') == 'group' and target_group_key and row.get('visit_account_group_key') == target_group_key)

        matched = df[df.apply(_matches, axis=1)].copy()
        matched = matched.sort_values('start_dt', ascending=False, na_position='last')
        return matched, selection

    def get_customer_interactions(self, company_name: str, limit: int = 12) -> Dict[str, object]:
        df, report_path = self._get_report_df()
        if df.empty:
            return {
                'summary': {},
                'interactions': [],
                'source': str(report_path) if report_path else None,
            }

        matched, selection = self._match_rows(df, company_name)
        if matched.empty:
            return {
                'summary': {
                    'display_name': selection.get('display_name', company_name),
                    'selection_type': selection.get('selection_type', 'company'),
                    'member_companies': selection.get('company_names', []),
                    'total_interactions': 0,
                },
                'interactions': [],
                'source': str(report_path) if report_path else None,
            }

        top_channels = [name for name, _count in Counter(v for v in matched['distribution_channel'] if v).most_common(3)]
        top_contacts = [name for name, _count in Counter(v for v in matched['employee_responsible'] if v).most_common(5)]
        latest = matched.iloc[0]

        records: List[Dict[str, object]] = []
        for _, row in matched.head(limit).iterrows():
            records.append({
                'subject': row.get('visit_subject', ''),
                'status': row.get('visit_status', ''),
                'account': row.get('visit_account', ''),
                'meeting_location': row.get('meeting_location', ''),
                'account_country_region': row.get('account_country_region', ''),
                'employee_responsible': row.get('employee_responsible', ''),
                'employee_department': row.get('employee_department', ''),
                'distribution_channel': row.get('distribution_channel', ''),
                'start_dt': row.get('start_dt').isoformat() if pd.notna(row.get('start_dt')) else '',
                'end_dt': row.get('end_dt').isoformat() if pd.notna(row.get('end_dt')) else '',
                'duration_hours': None if pd.isna(row.get('duration_hours')) else float(row.get('duration_hours')),
            })

        summary = {
            'display_name': selection.get('display_name', company_name),
            'selection_type': selection.get('selection_type', 'company'),
            'member_companies': selection.get('company_names', []),
            'total_interactions': int(len(matched)),
            'last_contact_date': latest.get('start_dt').isoformat() if pd.notna(latest.get('start_dt')) else '',
            'last_contact_location': latest.get('meeting_location', ''),
            'last_contact_owner': latest.get('employee_responsible', ''),
            'last_contact_subject': latest.get('visit_subject', ''),
            'top_channels': top_channels,
            'top_contacts': top_contacts,
        }

        return {
            'summary': summary,
            'interactions': records,
            'source': str(report_path) if report_path else None,
        }


interaction_service = InteractionService()