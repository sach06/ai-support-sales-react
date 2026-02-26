import axios from 'axios';

// The Vite proxy handles /api -> http://localhost:8000/api
const api = axios.create({
    baseURL: '/api',
    headers: {
        'Content-Type': 'application/json',
    },
});

export default api;
