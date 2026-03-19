import api from './client';

// /data/load should return quickly after spawning a background worker.
// Keep this request short and rely on /data/progress polling for long operations.
const DATA_LOAD_TIMEOUT_MS = 10000;
const DATA_STATUS_TIMEOUT_MS = 120000; // long timeout, but bounded so polling can recover

export const loadData = async () => {
    const response = await api.post('/data/load', null, {
        timeout: DATA_LOAD_TIMEOUT_MS,
    });
    return response.data;
};

export const getDataStatus = async (jobId = null) => {
    const response = await api.get('/data/status', {
        params: jobId ? { job_id: jobId } : undefined,
        timeout: DATA_STATUS_TIMEOUT_MS,
    });
    return response.data;
};

export const getCountries = async () => {
    const response = await api.get('/data/countries');
    return response.data.countries;
};

export const getCompanyNames = async (filters = {}) => {
    const response = await api.get('/data/company-names', { params: filters });
    return response.data.company_names || [];
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

export const getLoadProgress = async (jobId = null) => {
    const response = await api.get('/data/progress', {
        params: jobId ? { job_id: jobId } : undefined,
        timeout: DATA_STATUS_TIMEOUT_MS,
    });
    return response.data;
};

export const getPlants = async (filters) => {
    const response = await api.get('/data/plants', { params: filters });
    return response.data;
};
