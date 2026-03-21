from flask import Flask, request, jsonify, Response, send_file
from kiteconnect import KiteConnect
import json
import os
import threading

app = Flask(__name__)

api_key = "tsm9w570sr8un8kj"
access_token = "Ika9gOlRs1KUm3bnJhEEKUVjCr4Fqcc7"

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

@app.route('/')
def index():
    return '''<!DOCTYPE html>
<html>
<head>
<title>FMS Super Graph</title>
<style>
  body { background:#111; font-family:monospace; color:#eee; padding:20px; margin:0; }
  h1 { color:#4af; margin-bottom:4px; }
  #search-box { 
    width:400px; padding:10px 14px; background:#1a1a1a; 
    border:1px solid #333; color:#eee; font-family:monospace; 
    font-size:14px; border-radius:6px; outline:none;
  }
  #search-box:focus { border-color:#4af; }
  #results { 
    width:428px; background:#161616; border:1px solid #222; 
    border-radius:6px; margin-top:4px; max-height:300px; 
    overflow-y:auto; display:none;
  }
  .result-item {
    padding:8px 14px; cursor:pointer; border-bottom:1px solid #1a1a1a;
    font-size:12px;
  }
  .result-item:hover { background:#222; }
  .result-symbol { color:#4af; font-weight:bold; }
  .result-name { color:#888; margin-left:8px; }
  .result-type { color:#555; margin-left:8px; font-size:10px; }
  #progress-box {
    margin-top:16px; padding:14px; background:#161616; 
    border:1px solid #222; border-radius:6px; width:400px;
    display:none;
  }
  .progress-step {
    padding:4px 0; font-size:11px; color:#555;
  }
  .progress-step.active { color:#4af; }
  .progress-step.done { color:#4f8; }
  #graph-frame {
    margin-top:16px; width:100%; border:none;
    display:none; background:#111;
  }
  #recent {
    margin-top:16px;
  }
  .recent-item {
    display:inline-block; margin-right:8px; margin-bottom:6px;
    padding:4px 10px; background:#1a1a1a; border:1px solid #333;
    border-radius:4px; cursor:pointer; font-size:11px; color:#888;
  }
  .recent-item:hover { border-color:#4af; color:#4af; }
</style>
</head>
<body>
<h1>FMS Super Graph</h1>
<p style="color:#555; font-size:11px;">Search any NSE stock or ETF to load macro correlation visual</p>

<input type="text" id="search-box" placeholder="Search stock or ETF... (e.g. RELIANCE, SUNPHARMA)" autocomplete="off"/>
<div id="results"></div>

<div id="progress-box">
  <div style="color:#4af; font-size:12px; margin-bottom:8px;" id="progress-title">Loading...</div>
  <div class="progress-step" id="step-0">⬜ Loading regime context from SQLite...</div>
  <div class="progress-step" id="step-1">⬜ Fetching hourly macro data...</div>
  <div class="progress-step" id="step-2">⬜ Fetching hourly stock data from Zerodha...</div>
  <div class="progress-step" id="step-3">⬜ Calculating macro attribution...</div>
  <div class="progress-step" id="step-4">⬜ Generating super graph...</div>
</div>

<div id="recent">
  <div style="color:#444; font-size:10px; margin-bottom:6px;">RECENTLY VIEWED</div>
  <div id="recent-items"></div>
</div>

<iframe id="graph-frame" id="graph-frame"></iframe>

<script>
const steps = [
  "Loading regime context from SQLite...",
  "Fetching hourly macro data...",
  "Fetching hourly stock data from Zerodha...",
  "Calculating macro attribution...",
  "Generating super graph..."
];

// Load recent instruments
function loadRecent() {
  const recent = JSON.parse(localStorage.getItem('fms_recent') || '[]');
  const div = document.getElementById('recent-items');
  div.innerHTML = '';
  recent.forEach(item => {
    const el = document.createElement('div');
    el.className = 'recent-item';
    el.textContent = item.symbol;
    el.onclick = () => loadGraph(item.token, item.symbol);
    div.appendChild(el);
  });
}

function saveRecent(token, symbol) {
  let recent = JSON.parse(localStorage.getItem('fms_recent') || '[]');
  recent = recent.filter(r => r.token !== token);
  recent.unshift({token, symbol});
  recent = recent.slice(0, 8);
  localStorage.setItem('fms_recent', JSON.stringify(recent));
  loadRecent();
}

// Search
let searchTimeout;
document.getElementById('search-box').addEventListener('input', function() {
  clearTimeout(searchTimeout);
  const q = this.value.trim();
  if (q.length < 2) {
    document.getElementById('results').style.display = 'none';
    return;
  }
  searchTimeout = setTimeout(() => {
    fetch('/search?q=' + encodeURIComponent(q))
      .then(r => r.json())
      .then(data => {
        const div = document.getElementById('results');
        if (!data.length) { div.style.display = 'none'; return; }
        div.innerHTML = data.map(item => 
          `<div class="result-item" onclick="loadGraph(${item.token}, '${item.symbol}')">
            <span class="result-symbol">${item.symbol}</span>
            <span class="result-name">${item.name}</span>
            <span class="result-type">${item.instrument_type}</span>
          </div>`
        ).join('');
        div.style.display = 'block';
      });
  }, 300);
});

// Close results on outside click
document.addEventListener('click', function(e) {
  if (!e.target.closest('#search-box') && !e.target.closest('#results')) {
    document.getElementById('results').style.display = 'none';
  }
});

function loadGraph(token, symbol) {
  document.getElementById('results').style.display = 'none';
  document.getElementById('search-box').value = symbol;
  document.getElementById('graph-frame').style.display = 'none';

  const progressBox = document.getElementById('progress-box');
  progressBox.style.display = 'block';
  document.getElementById('progress-title').textContent = `Loading ${symbol}...`;

  // Reset steps
  for (let i = 0; i < 5; i++) {
    const el = document.getElementById(`step-${i}`);
    el.className = 'progress-step';
    el.textContent = `⬜ ${steps[i]}`;
  }

  // Stream progress via SSE
  const evtSource = new EventSource(`/generate?token=${token}&name=${encodeURIComponent(symbol)}`);
  
  evtSource.onmessage = function(e) {
    const data = JSON.parse(e.data);
    
    if (data.step !== undefined) {
      // Mark previous steps done
      for (let i = 0; i < data.step; i++) {
        const el = document.getElementById(`step-${i}`);
        el.className = 'progress-step done';
        el.textContent = `✅ ${steps[i]}`;
      }
      // Mark current step active
      const el = document.getElementById(`step-${data.step}`);
      el.className = 'progress-step active';
      el.textContent = `⏳ ${steps[data.step]}`;
    }
    
    if (data.done) {
      // Mark all done
      for (let i = 0; i < 5; i++) {
        const el = document.getElementById(`step-${i}`);
        el.className = 'progress-step done';
        el.textContent = `✅ ${steps[i]}`;
      }
      document.getElementById('progress-title').textContent = `✅ ${symbol} loaded`;
      
      // Load graph in iframe
      const frame = document.getElementById('graph-frame');
      frame.src = '/graph/' + data.filename;
      frame.style.display = 'block';
      frame.style.height = '700px';
      saveRecent(token, symbol);
      evtSource.close();
    }
    
    if (data.error) {
      document.getElementById('progress-title').textContent = `❌ Error: ${data.error}`;
      evtSource.close();
    }
  };

  evtSource.onerror = function() {
    document.getElementById('progress-title').textContent = '❌ Connection error';
    evtSource.close();
  };
}

loadRecent();
</script>
</body>
</html>'''

@app.route('/search')
def search():
    q = request.args.get('q', '').upper()
    if len(q) < 2:
        return jsonify([])
    try:
        instruments = kite.instruments('NSE')
        results = []
        for inst in instruments:
            if (q in inst['tradingsymbol'] or q in inst['name'].upper()):
                results.append({
                    'token': inst['instrument_token'],
                    'symbol': inst['tradingsymbol'],
                    'name': inst['name'],
                    'instrument_type': inst['instrument_type']
                })
            if len(results) >= 10:
                break
        return jsonify(results)
    except Exception as e:
        return jsonify([])

@app.route('/generate')
def generate():
    token = request.args.get('token', type=int)
    name = request.args.get('name', 'UNKNOWN')

    def event_stream():
        try:
            from fms_supergraph import generate_supergraph

            def progress_callback(step, done=False, filename=None):
                if done:
                    data = json.dumps({'done': True, 'filename': filename})
                else:
                    data = json.dumps({'step': step})
                yield f"data: {data}\n\n"

            # Run generation
            steps_queue = []
            result = {'filename': None}

            def progress(step, done=False, filename=None):
                steps_queue.append({'step': step, 'done': done, 'filename': filename})

            import threading
            gen_thread = threading.Thread(
                target=lambda: result.update({'filename': generate_supergraph(name, token, progress)})
            )
            gen_thread.start()

            last_sent = -1
            while gen_thread.is_alive() or steps_queue:
                if steps_queue:
                    item = steps_queue.pop(0)
                    yield f"data: {json.dumps(item)}\n\n"
                import time
                time.sleep(0.2)

            gen_thread.join()

            # Final done signal
            if result['filename']:
                yield f"data: {json.dumps({'done': True, 'filename': result['filename']})}\n\n"
            else:
                yield f"data: {json.dumps({'error': 'Generation failed'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(event_stream(), mimetype='text/event-stream')

@app.route('/graph/<path:filename>')
def serve_graph(filename):
    return send_file(filename)

if __name__ == '__main__':
    print("FMS Search running at http://127.0.0.1:5001")
    app.run(debug=False, port=5001, threaded=True)
