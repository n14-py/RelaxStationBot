const express = require('express');
const path = require('path');
const http = require('http');
const app = express();
const port = process.env.PORT || 3000;

// Ruta principal
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

// Endpoint de salud
app.get('/health', (req, res) => {
  res.status(200).json({ 
    status: 'online',
    stream: 'active',
    timestamp: new Date().toISOString()
  });
});

// Iniciar servidor
const server = app.listen(port, () => {
  console.log(`✅ Servidor web activo en puerto ${port}`);
  
  // Sistema de ping automático
  setInterval(() => {
    http.get(`http://localhost:${port}/health`, (res) => {
      console.log(`🔄 Ping exitoso - ${new Date().toLocaleTimeString()}`);
    }).on('error', (err) => {
      console.error('❌ Error en ping:', err.message);
    });
  }, 300000); // 5 minutos
});
