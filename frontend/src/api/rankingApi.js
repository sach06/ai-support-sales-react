import api from './client';

export const getModelStatus = async () => {
    const response = await api.get('/ranking/model-status');
    return response.data;
};

export const getRankedList = async ({ equipmentType, country, companyName, topK = 50, forceHeuristic = false }) => {
    const response = await api.get('/ranking/list', {
        params: {
            equipment_type: equipmentType,
            country: country,
            company_name: companyName,
            top_k: topK,
            force_heuristic: forceHeuristic
        }
    });
    return response.data.rankings;
};

export const retrainRankingModel = async (snapshotId = 'live_duckdb') => {
    const response = await api.post('/ranking/retrain', null, {
        params: {
            snapshot_id: snapshotId
        }
    });
    return response.data;
};

export const getRetrainStatus = async () => {
    const response = await api.get('/ranking/retrain-status');
    return response.data;
};

export const getCompanyIntelligence = async ({ companyName, equipmentType, country }) => {
    const response = await api.get('/ranking/company-intelligence', {
        params: {
            company_name: companyName,
            equipment_type: equipmentType,
            country,
        },
    });
    return response.data;
};
