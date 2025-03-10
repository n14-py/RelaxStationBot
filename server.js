const express = require('express');
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
  
 
