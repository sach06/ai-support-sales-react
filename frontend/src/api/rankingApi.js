import api from './client';

export const getModelStatus = async () => {
    const response = await api.get('/ranking/model-status');
    return response.data;
};

export const getRankedList = async ({ equipmentType, country, topK = 50, forceHeuristic = false }) => {
    const response = await api.get('/ranking/list', {
        params: {
            equipment_type: equipmentType,
            country: country,
            top_k: topK,
            force_heuristic: forceHeuristic
        }
    });
    return response.data.rankings;
};
