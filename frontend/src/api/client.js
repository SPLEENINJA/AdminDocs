import axios from 'axios';

// Docker build: VITE_API_URL=/api  -> nginx proxy to team-backend:4000
// Local dev: vite proxy /api -> localhost:4000
const baseURL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({ baseURL });

export default api;
