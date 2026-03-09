import api from './client';

export const getCustomerProfile = async (customerName, filters = {}) => {
    const params = {
        country: filters.country || 'All',
        region: filters.region || 'All',
        equipment_type: filters.equipmentType || 'All'
    };
    const response = await api.get(`/customer/${encodeURIComponent(customerName)}`, { params });
    return response.data;
};

export const generateProfile = async (customerName) => {
    const response = await api.post(`/customer/${encodeURIComponent(customerName)}/generate-profile`);
    return response.data.profile;
};
