#!/usr/bin/env python3
"""
PathHunter - Cyberpunk Web Interface
Directory scanner with dark theme and neon blue accents
"""

from flask import Flask, render_template, request, jsonify, send_file
import os
import threading
from scanner import DirScanner
from datetime import datetime
import json
import tempfile

app = Flask(__name__)

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'wordlists')
app.config['REPORTS_FOLDER'] = os.path.join(BASE_DIR, 'reports')

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['REPORTS_FOLDER'], exist_ok=True)

# Store temporary uploaded wordlists in memory (cleared on server restart)
temp_wordlists = {}

# Global variables to track scan status
current_scan = {
    'running': False,
    'progress': 0,
    'total': 0,
    'results': [],
    'scanner': None,
    'stop_requested': False  # Flag to stop the scan
}

@app.route('/')
def index():
    """Main page"""
    # Get permanent wordlists from disk
    permanent_wordlists = []
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        permanent_wordlists = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if f.endswith('.txt')]
    
    # Combine with temporary uploaded wordlists
    temp_wordlist_names = list(temp_wordlists.keys())
    
    return render_template('index.html', 
                         permanent_wordlists=permanent_wordlists,
                         temp_wordlists=temp_wordlist_names)

@app.route('/upload_wordlist', methods=['POST'])
def upload_wordlist():
    """Upload a temporary wordlist (stored in memory, not saved to disk)"""
    if 'wordlist' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'})
    
    file = request.files['wordlist']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})
    
    if file and file.filename.endswith('.txt'):
        try:
            # Read file content into memory
            content = file.read().decode('utf-8')
            
            # Store in memory with temporary flag
            temp_wordlists[file.filename] = content
            
            return jsonify({
                'success': True, 
                'filename': file.filename,
                'temporary': True
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    return jsonify({'success': False, 'error': 'Invalid file type'})

@app.route('/start_scan', methods=['POST'])
def start_scan():
    """Start a new scan"""
    global current_scan
    
    # If a scan is running, force stop it IMMEDIATELY
    if current_scan['running']:
        print("[!] Stopping previous scan...")
        current_scan['stop_requested'] = True
        current_scan['running'] = False  # Force it to stop immediately
        
        # Give it a tiny moment
        import time
        time.sleep(0.2)
    
    data = request.json
    target = data.get('target', '').strip()
    wordlists = data.get('wordlists', [])
    threads = int(data.get('threads', 10))
    timeout = int(data.get('timeout', 5))
    extensions = data.get('extensions', '').strip()
    
    if not target:
        return jsonify({'success': False, 'error': 'Target URL required'})
    
    if not wordlists:
        return jsonify({'success': False, 'error': 'At least one wordlist required'})
    
    # Parse extensions
    ext_list = ['']
    if extensions:
        ext_list = [''] + ['.' + ext.strip().lstrip('.') for ext in extensions.split(',')]
    
    # Prepare wordlist paths - handle both permanent and temporary wordlists
    wordlist_paths = []
    temp_files = []
    
    for wl in wordlists:
        if wl in temp_wordlists:
            # Temporary wordlist - create a temp file for this scan
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
            temp_file.write(temp_wordlists[wl])
            temp_file.close()
            wordlist_paths.append(temp_file.name)
            temp_files.append(temp_file.name)
        else:
            # Permanent wordlist from disk
            wordlist_paths.append(os.path.join(app.config['UPLOAD_FOLDER'], wl))
    
    # RESET current scan - clear previous results
    current_scan = {
        'running': True,
        'progress': 0,
        'total': 0,
        'results': [],
        'scanner': None,
        'target': target,
        'temp_files': temp_files,
        'stop_requested': False
    }
    
    # Create scanner
    scanner = DirScanner(
        target=target,
        wordlists=wordlist_paths,
        threads=threads,
        timeout=timeout,
        extensions=ext_list
    )
    
    current_scan['scanner'] = scanner
    
    # Start scan in background thread
    def run_scan():
        global current_scan
        try:
            # Disable SSL warnings
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Pass stop flag to scanner
            scanner.stop_flag = lambda: current_scan.get('stop_requested', False)
            results = scanner.scan()
            
            current_scan['results'] = results
            current_scan['running'] = False
            
            # Clean up temporary files
            for temp_file in current_scan.get('temp_files', []):
                try:
                    os.unlink(temp_file)
                except:
                    pass
                    
        except Exception as e:
            print(f"Scan error: {str(e)}")
            current_scan['running'] = False
            # Clean up temporary files on error too
            for temp_file in current_scan.get('temp_files', []):
                try:
                    os.unlink(temp_file)
                except:
                    pass
    
    thread = threading.Thread(target=run_scan)
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True})

@app.route('/scan_status')
def scan_status():
    """Get current scan status"""
    global current_scan
    
    scanner = current_scan.get('scanner')
    if scanner:
        return jsonify({
            'running': current_scan['running'],
            'progress': scanner.scanned,
            'total': scanner.total,
            'results_count': len(scanner.results),
            'results': scanner.results[-10:]  # Last 10 results
        })
    
    return jsonify({
        'running': current_scan['running'],
        'progress': current_scan['progress'],
        'total': current_scan['total'],
        'results_count': len(current_scan['results']),
        'results': []
    })

@app.route('/stop_scan', methods=['POST'])
def stop_scan():
    """Stop the current scan"""
    global current_scan
    
    if current_scan['running']:
        current_scan['stop_requested'] = True
        return jsonify({'success': True, 'message': 'Stopping scan...'})
    
    return jsonify({'success': False, 'message': 'No scan running'})

@app.route('/get_results')
def get_results():
    """Get all scan results"""
    global current_scan
    
    scanner = current_scan.get('scanner')
    if scanner:
        return jsonify({
            'results': scanner.results,
            'target': current_scan.get('target', '')
        })
    
    return jsonify({
        'results': current_scan['results'],
        'target': current_scan.get('target', '')
    })

@app.route('/download_report')
def download_report():
    """Download scan report"""
    global current_scan
    
    scanner = current_scan.get('scanner')
    if not scanner or not scanner.results:
        return "No results available", 404
    
    # Generate report filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = os.path.join(app.config['REPORTS_FOLDER'], f'scan_report_{timestamp}.txt')
    
    # Save report
    scanner.save_report(report_file)
    
    return send_file(report_file, as_attachment=True, download_name=f'scan_report_{timestamp}.txt')

if __name__ == '__main__':
    print("\n" + "="*70)
    print(" ██████╗  █████╗ ████████╗██╗  ██╗██╗  ██╗██╗   ██╗███╗   ██╗████████╗")
    print(" ██╔══██╗██╔══██╗╚══██╔══╝██║  ██║██║  ██║██║   ██║████╗  ██║╚══██╔══╝")
    print(" ██████╔╝███████║   ██║   ███████║███████║██║   ██║██╔██╗ ██║   ██║   ")
    print(" ██╔═══╝ ██╔══██║   ██║   ██╔══██║██╔══██║██║   ██║██║╚██╗██║   ██║   ")
    print(" ██║     ██║  ██║   ██║   ██║  ██║██║  ██║╚██████╔╝██║ ╚████║   ██║   ")
    print(" ╚═╝     ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ")
    print("="*70)
    print("⚡ CYBERPUNK DIRECTORY SCANNER ⚡")
    print("Hunt paths. Find secrets. Own systems.")
    print("="*70)
    print("\n🌐 Server starting on http://localhost:5000")
    print("🔷 Press Ctrl+C to stop\n")
    
    if __name__ == "__main__":
        app.run(host="0.0.0.0", port=5000)
