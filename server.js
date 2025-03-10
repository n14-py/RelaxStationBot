const express = require('express');
const { exec } = require('child_process');
const app = express();

// Servir el archivo HTML
app.get('/', (req, res) => {
  res.sendFile(__dirname + '/index.html');
});

// Configurar el puerto que Render espera
const port = process.env.PORT || 3000;

// Iniciar la transmisión en vivo con el comando de Python
const startStreaming = () => {
  exec('python3 main.py', (error, stdout, stderr) => {
    if (error) {
      console.error(`Error al ejecutar el script: ${error}`);
      return;
    }
    console.log(`Transmisión en vivo iniciada: ${stdout}`);
  });
};

// Asegúrate de que la transmisión empiece cuando el servidor se inicie
startStreaming();

// Iniciar el servidor
app.listen(port, () => {
  console.log(`Servidor web en línea en el puerto ${port}`);
});
