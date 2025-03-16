const express = require('express');
const app = express();
const port = 3000;

app.get('/', (req, res) => {
  res.send('Stream Manager Running');
});

app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});
