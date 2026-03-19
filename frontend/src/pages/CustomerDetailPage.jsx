import React, { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useFilterStore } from '../store/useFilterStore';
import { getCustomerProfile, generateProfile, getInternalKnowledgeStatus, reindexInternalKnowledge, getReindexStatus } from '../api/customerApi';
import { exportDocx, exportPdf, exportPptx } from '../api/exportApi';

import ProfileSections from './ProfileSections';
import InventoryTable from './InventoryTable';
import './Customer.css';

const CustomerDetailPage = () => {
    const filters = useFilterStore();
    const { companyName } = filters;

    const [profileData, setProfileData] = useState(null);
    const [isGenerating, setIsGenerating] = useState(false);
    const [isExporting, setIsExporting] = useState(false);
    const [activeExportFormat, setActiveExportFormat] = useState(null);
    const [exportStatus, setExportStatus] = useState({
        docx: 'idle',
        pdf: 'idle',
        pptx: 'idle',
    });
    const [exportProgressMsg, setExportProgressMsg] = useState('');
    const [isReindexing, setIsReindexing] = useState(false);
    const [errorMsg, setErrorMsg] = useState(null);
    const [knowledgeActionMsg, setKnowledgeActionMsg] = useState(null);
    const reindexPollRef = useRef(null);

    // Clear polling on unmount
    useEffect(() => () => { if (reindexPollRef.current) clearInterval(reindexPollRef.current); }, []);

    // Fetch initial basic data from CRM/BCG
    const { data: rawCustomerData, isLoading: isLoadingRaw, isError: isErrorRaw } = useQuery({
        queryKey: ['raw_customer', companyName, filters.country, filters.region, filters.equipmentType],
        queryFn: () => getCustomerProfile(companyName, filters),
        enabled: companyName !== 'All',
    });

    const { data: knowledgeStatus, refetch: refetchKnowledgeStatus } = useQuery({
        queryKey: ['internal_knowledge_status'],
        queryFn: getInternalKnowledgeStatus,
    });

    const handleGenerateProfile = async () => {
        setIsGenerating(true);
        setErrorMsg(null);
        try {
            const result = await generateProfile(companyName);
            setProfileData(result);
            if (result?.generation_mode === 'fallback') {
                const detail = result?.generation_error ? ` Details: ${String(result.generation_error).slice(0, 220)}` : '';
                setErrorMsg(`AI profile generation did not complete cleanly, so a data-driven fallback profile is being shown.${detail}`);
            }
        } catch (err) {
            console.error("Failed to generate profile:", err);
            const detail = err?.response?.data?.detail || err?.message || 'Unknown backend error.';
            setErrorMsg(`Failed to generate customer profile. ${detail}`);
        } finally {
            setIsGenerating(false);
        }
    };

    const handleReindexKnowledge = async () => {
        setIsReindexing(true);
        setKnowledgeActionMsg('Reindexing started...');
        try {
            await reindexInternalKnowledge();
            // Poll until done
            if (reindexPollRef.current) clearInterval(reindexPollRef.current);
            reindexPollRef.current = setInterval(async () => {
                try {
                    const s = await getReindexStatus();
                    if (s.status === 'done') {
                        clearInterval(reindexPollRef.current);
                        reindexPollRef.current = null;
                        setIsReindexing(false);
                        await refetchKnowledgeStatus();
                        setKnowledgeActionMsg(
                            `Indexed ${s.result?.document_count || 0} internal documents. Regenerate the profile to apply the latest evidence.`
                        );
                    } else if (s.status === 'error') {
                        clearInterval(reindexPollRef.current);
                        reindexPollRef.current = null;
                        setIsReindexing(false);
                        setKnowledgeActionMsg(`Reindex failed: ${s.message}`);
                    }
                } catch (_) { /* ignore transient poll errors */ }
            }, 2000);
        } catch (err) {
            console.error('Failed to start reindex:', err);
            setKnowledgeActionMsg('Failed to start reindex. Check backend access to the P: drive.');
            setIsReindexing(false);
        }
    };

    const handleExport = async (format) => {
        if (!profileData) return;
        setErrorMsg(null);
        setIsExporting(true);
        setActiveExportFormat(format);
        setExportStatus((prev) => ({ ...prev, [format]: 'running' }));
        setExportProgressMsg(`Preparing ${format.toUpperCase()} export...`);

        try {
            if (format === 'docx') {
                await exportDocx(profileData, companyName);
            } else if (format === 'pdf') {
                await exportPdf(profileData, companyName);
            } else if (format === 'pptx') {
                await exportPptx(profileData, companyName);
            }
            setExportStatus((prev) => ({ ...prev, [format]: 'success' }));
            setExportProgressMsg(`${format.toUpperCase()} export ready. Download started.`);
        } catch (err) {
            console.error(`Failed to export ${format}:`, err);
            const detail = err?.message || `Failed to export ${format.toUpperCase()} document.`;
            setExportStatus((prev) => ({ ...prev, [format]: 'error' }));
            setExportProgressMsg(`${format.toUpperCase()} export failed.`);
            setErrorMsg(detail);
        } finally {
            setIsExporting(false);
            setActiveExportFormat(null);
        }
    };

    const renderExportButtonLabel = (format, defaultLabel) => {
        if (activeExportFormat === format && isExporting) return `${defaultLabel} Generating...`;
        if (exportStatus[format] === 'success') return `${defaultLabel} Done`;
        if (exportStatus[format] === 'error') return `${defaultLabel} Retry`;
        return defaultLabel;
    };

    if (companyName === 'All') {
        return (
            <div className="customer-empty-state">
                <h2>No Customer Selected</h2>
                <p>Please select a specific Company Name from the sidebar filters to view and generate a customer profile.</p>
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
                    <button
                        className="btn-secondary btn-knowledge"
                        onClick={handleReindexKnowledge}
                        disabled={isReindexing}
                    >
                        {isReindexing ? 'Reindexing Knowledge...' : 'Reindex Internal Knowledge'}
                    </button>

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
                            <span className="export-label">Export Customer Profile:</span>
                            <button
                                className="btn-secondary btn-export"
                                onClick={() => handleExport('docx')}
                                disabled={isExporting}
                            >
                                📄 {renderExportButtonLabel('docx', 'DOCX')}
                            </button>
                            <button
                                className="btn-secondary btn-export"
                                onClick={() => handleExport('pdf')}
                                disabled={isExporting}
                            >
                                📑 {renderExportButtonLabel('pdf', 'PDF')}
                            </button>
                            <button
                                className="btn-secondary btn-export"
                                onClick={() => handleExport('pptx')}
                                disabled={isExporting}
                            >
                                📊 {renderExportButtonLabel('pptx', 'PPTX')}
                            </button>
                        </div>
                    )}

                    {exportProgressMsg && (
                        <div className="export-progress-panel">
                            <div className="export-progress-msg">{exportProgressMsg}</div>
                            <div className="export-progress-chips">
                                <span className={`export-chip export-chip-${exportStatus.docx}`}>DOCX: {exportStatus.docx}</span>
                                <span className={`export-chip export-chip-${exportStatus.pdf}`}>PDF: {exportStatus.pdf}</span>
                                <span className={`export-chip export-chip-${exportStatus.pptx}`}>PPTX: {exportStatus.pptx}</span>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {errorMsg && (
                <div className="error-banner">
                    {errorMsg}
                </div>
            )}

            {(knowledgeActionMsg || knowledgeStatus) && (
                <div className="knowledge-status-banner">
                    <div>
                        <strong>Internal knowledge index:</strong>{' '}
                        {knowledgeActionMsg || `${knowledgeStatus?.manifest_rows || 0} documents indexed`}
                    </div>
                    {knowledgeStatus?.last_indexed_at && (
                        <div className="knowledge-status-meta">Last index: {knowledgeStatus.last_indexed_at}</div>
                    )}
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
