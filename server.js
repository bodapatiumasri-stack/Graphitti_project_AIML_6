const express = require('express');
const app = express();

const PORT = process.env.PORT || 3000;

app.use(express.json());

const path = require('path');

app.use(express.static(__dirname));

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server started and listening on port ${PORT}`);
});
