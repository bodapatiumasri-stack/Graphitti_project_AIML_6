const path = require('path');
const express = require('express');
const app = express();

// Serve static files from the "public" directory
app.use(express.static(path.join(__dirname, 'public')));
