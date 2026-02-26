import api from './client';

export const loadData = async () => {
    const response = await api.post('/data/load');
    return response.data;
};

export const getDataStatus = async () => {
    const response = await api.get('/data/status');
    return response.data;
};

export const getCountries = async () => {
    const response = await api.get('/data/countries');
    return response.data.countries;
};

export const getRegions = async () => {
    const response = await api.get('/data/regions');
    return response.data.regions;
};

export const getEquipmentTypes = async () => {
    const response = await api.get('/data/equipment-types');
    return response.data.equipment_types;
};

export const getCustomers = async (filters) => {
    const response = await api.get('/data/customers', { params: filters });
    return response.data;
};
