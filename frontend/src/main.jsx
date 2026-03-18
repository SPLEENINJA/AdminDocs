

//main.jsx initialise l’application React et active le système de routing. 
//Il importe les modules nécessaires, crée une racine pour l’application et
//rend le composant App à l’intérieur d’un BrowserRouter pour permettre la navigation entre les différentes pages de l’application.


import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App.jsx';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
 
