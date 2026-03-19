

import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:4000/api'
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      console.error('Erreur dauthentification détectée:', {
        status: error.response.status,
        url: error.config?.url,
        message: error.response?.data?.message
      });
      console.warn('Déconnexion forcée - redirection vers /login');
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
