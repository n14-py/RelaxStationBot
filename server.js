const express = require('express');
const http = require('http'); // Paquete necesario para hacer una petición HTTP a sí mismo
const app = express();

// Servir el archivo HTML
app.get('/', (req, res) => {
  res.sendFile(__dirname + '/index.html');
});

// Configurar el puerto que Render espera
const port = process.env.PORT || 3000;

// Iniciar el servidor
app.listen(port, () => {
  console.log(`Servidor web en línea en el puerto ${port}`);
  
  // Hacer ping al servidor cada 5 minutos (300000 ms)
  setInterval(() => {
    http.get(`http://localhost:${port}`, (response) => {
      console.log(`Ping al servidor exitoso: ${response.statusCode}`);
    }).on('error', (e) => {
      console.error('Error al hacer ping al servidor:', e);
    });
  }, 5 * 60 * 1000); // 5 minutos en milisegundos
});
