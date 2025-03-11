// server.js minimizado
const express = require('express');
const app = express();
app.get('/health', (req, res) => res.sendStatus(200));
app.listen(3000, () => console.log("✅ Servidor listo"));
