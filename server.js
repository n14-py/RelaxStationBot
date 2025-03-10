const express = require('express');
const path = require('path');
const app = express();
const port = process.env.PORT || 3000;

// Ruta principal
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

// Health check básico
app.get('/health', (req, res) => {
  res.sendStatus(200);
});

// Iniciar servidor
app.listen(port, () => {
  console.log(`✅ Servidor listo en puerto ${port}`);
});
