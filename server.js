const http = require('http');
const fs = require('fs');
const { spawn } = require('child_process');
const path = require('path');

/**
 * Simple helper to read the request body and return it as a string.
 * JSON bodies are expected for POST /upload requests.
 * @param {http.IncomingMessage} req
 * @param {function} callback
 */
function parseBody(req, callback) {
  let body = '';
  req.on('data', chunk => {
    body += chunk;
  });
  req.on('end', () => {
    callback(body);
  });
}

/**
 * Create an HTTP server to serve a minimal front‑end and handle
 * file uploads encoded as base64. Uploaded PDFs are written to a
 * temporary directory and then passed to the Python parser via
 * child_process.spawn. The metrics are returned as JSON.
 */
const server = http.createServer((req, res) => {
  if (req.method === 'GET') {
    // Serve the home page
    if (req.url === '/' || req.url === '/index.html') {
      fs.readFile(path.join(__dirname, 'index.html'), (err, data) => {
        if (err) {
          res.writeHead(500, { 'Content-Type': 'text/plain' });
          res.end('Internal Server Error');
          return;
        }
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(data);
      });
    // Serve the client script
    } else if (req.url === '/client.js') {
      fs.readFile(path.join(__dirname, 'client.js'), (err, data) => {
        if (err) {
          res.writeHead(404, { 'Content-Type': 'text/plain' });
          res.end('Not Found');
          return;
        }
        res.writeHead(200, { 'Content-Type': 'application/javascript' });
        res.end(data);
      });
    } else {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not Found');
    }
  } else if (req.method === 'POST' && req.url === '/upload') {
    // Handle upload requests
    parseBody(req, (body) => {
      try {
        const payload = JSON.parse(body);
        const { fileName, content, level } = payload;
        // Validate fields
        if (!fileName || !content) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'fileName and content are required' }));
          return;
        }
        // Decode base64 content and write to temporary file
        const buffer = Buffer.from(content, 'base64');
        const uploadsDir = path.join(__dirname, 'uploads');
        if (!fs.existsSync(uploadsDir)) {
          fs.mkdirSync(uploadsDir);
        }
        const filePath = path.join(uploadsDir, fileName);
        fs.writeFileSync(filePath, buffer);
        // Spawn the Python parser on the uploaded file
        const scriptPath = path.join(__dirname, 'extract_financial_metrics.py');
        const python = spawn('python3', [scriptPath, filePath]);
        let output = '';
        let errorOutput = '';
        python.stdout.on('data', (data) => {
          output += data.toString();
        });
        python.stderr.on('data', (data) => {
          errorOutput += data.toString();
        });
        python.on('close', (code) => {
          let result;
          if (errorOutput) {
            result = { error: errorOutput.trim() };
          } else {
            try {
              result = JSON.parse(output);
            } catch (e) {
              result = { error: 'Failed to parse metrics from parser output.' };
            }
          }
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ metrics: result, level }));
        });
      } catch (err) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Invalid JSON payload' }));
      }
    });
  } else {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not Found');
  }
});

// Start the server on port 3000
const PORT = 3000;
server.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});