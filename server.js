const express = require('express');
const app = express();

// Railway injects process.env.PORT automatically at runtime
const PORT = process.env.PORT || 3000;

app.use(express.json());

const path = require('path');

// Serve all static files (index.html, graph.html, CSS, JS) from your root folder
app.use(express.static(__dirname));

// OPTIONAL: If you specifically want graph.html to open as the main homepage instead of index.html, use this:
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});
// Binding to '0.0.0.0' enables Railway's router to direct public traffic to your container
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server started and listening on port ${PORT}`);
});
