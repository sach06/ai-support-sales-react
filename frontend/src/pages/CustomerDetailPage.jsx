import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useFilterStore } from '../store/useFilterStore';
import { getCustomerProfile, generateProfile } from '../api/customerApi';
import { exportDocx, exportPdf } from '../api/exportApi';

import ProfileSections from './ProfileSections';
import InventoryTable from './InventoryTable';
import './Customer.css';

const CustomerDetailPage = () => {
    const { companyName } = useFilterStore();

    const [profileData, setProfileData] = useState(null);
    const [isGenerating, setIsGenerating] = useState(false);
    const [isExporting, setIsExporting] = useState(false);
    const [errorMsg, setErrorMsg] = useState(null);

    // Fetch initial basic data from CRM/BCG
    const { data: rawCustomerData, isLoading: isLoadingRaw, isError: isErrorRaw } = useQuery({
        queryKey: ['raw_customer', companyName],
        queryFn: () => getCustomerProfile(companyName),
        enabled: companyName !== 'All',
    });

    const handleGenerateProfile = async () => {
        setIsGenerating(true);
        setErrorMsg(null);
        try {
            const result = await generateProfile(companyName);
            setProfileData(result);
        } catch (err) {
            console.error("Failed to generate profile:", err);
            setErrorMsg("Failed to generate AI profile. Ensure Azure OpenAI or OpenAI keys are configured.");
        } finally {
            setIsGenerating(false);
        }
    };

    const handleExport = async (format) => {
        if (!profileData) return;
        setIsExporting(true);

        try {
            if (format === 'docx') {
                await exportDocx(profileData, companyName);
            } else if (format === 'pdf') {
                await exportPdf(profileData, companyName);
            }
        } catch (err) {
            console.error(`Failed to export ${format}:`, err);
            alert(`Failed to export document. Check console for details.`);
        } finally {
            setIsExporting(false);
        }
    };

    if (companyName === 'All') {
        return (
            <div className="customer-empty-state">
                <h2>No Customer Selected</h2>
                <p>Please select a specific Company Name from the sidebar filters to view and generate a detail profile.</p>
            </div>
        );
    }

    if (isLoadingRaw) return <div className="loading-state">Loading customer data...</div>;

    if (isErrorRaw || !rawCustomerData) {
        return (
            <div className="error-state">
                Failed to load customer base data. Verify that {companyName} exists in the DuckDB tables.
            </div>
        );
    }

    const hasProfile = profileData !== null;

    return (
        <div className="customer-container">
            {/* Header Area */}
            <div className="customer-header-card">
                <div className="header-info">
                    <h2 className="customer-title">{rawCustomerData.customer_name}</h2>
                    <div className="customer-meta-tags">
                        <span className="meta-tag">
                            <span className="icon">📍</span> {rawCustomerData.crm_data.Country || 'Unknown'}
                        </span>
                        <span className="meta-tag">
                            <span className="icon">🏢</span> {rawCustomerData.crm_data.Industry || 'Unknown'}
                        </span>
                    </div>
                </div>

                <div className="header-actions">
                    {!hasProfile ? (
                        <button
                            className="btn-primary btn-generate"
                            onClick={handleGenerateProfile}
                            disabled={isGenerating}
                        >
                            {isGenerating ? 'Generating Steckbrief (GPT-4o)...' : '✨ Generate AI Steckbrief'}
                        </button>
                    ) : (
                        <div className="export-actions">
                            <span className="export-label">Export Profile:</span>
                            <button
                                className="btn-secondary btn-export"
                                onClick={() => handleExport('docx')}
                                disabled={isExporting}
                            >
                                📄 DOCX
                            </button>
                            <button
                                className="btn-secondary btn-export"
                                onClick={() => handleExport('pdf')}
                                disabled={isExporting}
                            >
                                📑 PDF
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {errorMsg && (
                <div className="error-banner">
                    {errorMsg}
                </div>
            )}

            {/* AI Generated Content Area */}
            {hasProfile && (
                <div className="profile-wrapper">
                    <div className="profile-header-strip">
                        <h3>AI Generated Customer Profile</h3>
                        <span className="status-badge success">Up-to-date</span>
                    </div>

                    <div className="profile-content-area">
                        <ProfileSections profile={profileData} />
                    </div>
                </div>
            )}

            {/* Raw Installed Base Area (Always visible if data exists) */}
            {rawCustomerData.installed_base && rawCustomerData.installed_base.length > 0 && (
                <div className="raw-data-section">
                    <h3>Known Installed Base</h3>
                    <div className="table-wrapper">
                        {/* Reuse Inventory Table from Dashboard */}
                        <InventoryTable data={rawCustomerData.installed_base} />
                    </div>
                </div>
            )}
        </div>
    );
};

export default CustomerDetailPage;
