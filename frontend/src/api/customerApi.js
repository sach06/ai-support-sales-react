import api from './client';

export const getCustomerProfile = async (customerName) => {
    const response = await api.get(`/customer/${encodeURIComponent(customerName)}`);
    return response.data;
};

export const generateProfile = async (customerName) => {
    const response = await api.post(`/customer/${encodeURIComponent(customerName)}/generate-profile`);
    return response.data.profile;
};
