import axios from 'axios';

// The Vite proxy handles /api -> http://localhost:8000/api
const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
    timeout: 15000,
    headers: {
        'Content-Type': 'application/json',
    },
});

export default api;
