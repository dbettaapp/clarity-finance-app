// client.js
// This script handles file selection, converts the file to base64 and
// sends it to the server for analysis. The server returns metrics
// extracted from the PDF which are displayed on the page.

/**
 * Convert a File object to a base64 string. Returns a Promise that
 * resolves with the base64 content (without the data URI prefix).
 * @param {File} file
 * @returns {Promise<string>}
 */
function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      // reader.result includes the data URI prefix. Remove it if present.
      const result = reader.result;
      if (typeof result === 'string') {
        // Find comma and take substring after comma
        const commaIndex = result.indexOf(',');
        const base64 = commaIndex >= 0 ? result.substring(commaIndex + 1) : result;
        resolve(base64);
      } else {
        reject(new Error('Unexpected result type'));
      }
    };
    reader.onerror = (error) => reject(error);
    // Read file as data URL to easily extract base64
    reader.readAsDataURL(file);
  });
}

/**
 * Display metrics or error in the result div.
 * @param {Object} data
 */
function displayResult(data) {
  const resultEl = document.getElementById('result');
  // Clear previous content
  resultEl.innerHTML = '';
  if (!data) {
    resultEl.textContent = 'Sin respuesta del servidor.';
    return;
  }
  if (data.error) {
    const p = document.createElement('p');
    p.className = 'error';
    p.textContent = `Error: ${data.error}`;
    resultEl.appendChild(p);
    return;
  }
  const { metrics, level } = data;
  // Show analysis level
  const header = document.createElement('h3');
  header.textContent = `Resultados del análisis (${level})`;
  resultEl.appendChild(header);
  if (!metrics || metrics.error) {
    const p = document.createElement('p');
    p.className = 'error';
    p.textContent = metrics && metrics.error ? metrics.error : 'No se pudieron obtener métricas.';
    resultEl.appendChild(p);
    return;
  }
  // Build a list of metrics
  const list = document.createElement('ul');
  Object.keys(metrics).forEach((key) => {
    const li = document.createElement('li');
    li.textContent = `${key}: ${metrics[key]}`;
    list.appendChild(li);
  });
  resultEl.appendChild(list);
}

// Hook up the event listener
document.addEventListener('DOMContentLoaded', () => {
  const uploadBtn = document.getElementById('upload-btn');
  const fileInput = document.getElementById('file-input');
  const levelSelect = document.getElementById('analysis-level');
  uploadBtn.addEventListener('click', async () => {
    const file = fileInput.files[0];
    if (!file) {
      alert('Por favor selecciona un archivo para subir.');
      return;
    }
    // Convert to base64
    try {
      const base64 = await fileToBase64(file);
      const payload = {
        fileName: file.name,
        content: base64,
        level: levelSelect.value,
      };
      const response = await fetch('/upload', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      displayResult(data);
    } catch (err) {
      console.error(err);
      displayResult({ error: err.message });
    }
  });
});