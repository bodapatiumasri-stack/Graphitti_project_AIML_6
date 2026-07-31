const path = require('path');
app.use(express.static(path.join(__dirname, 'public'))); // or 'build' / 'dist'
