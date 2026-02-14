PathHunter is a modern, professional web-based directory enumeration and vulnerability scanning tool that combines the power of command-line scanners like dirsearch with an intuitive, business-grade web interface. Built with Python and Flask, it's designed for security professionals, penetration testers, and bug bounty hunters who need both power and usability.
Why PathHunter?

🌐 Dual Interface - Beautiful web UI + powerful CLI
⚡ Fast Scanning - Multi-threaded architecture (up to 50 threads)
🎯 Advanced Fuzzing - Built-in path traversal detection
📊 Real-time Monitoring - Live progress and results
💼 Business Ready - Professional design for client presentations
🔄 Smart Features - Redirect tracking, temporary uploads, detailed reports


🔍 Scanning Capabilities

✅ Multi-threaded scanning with configurable thread pools (1-50 threads)
✅ Path traversal detection with 100+ fuzzing patterns
✅ Redirect tracking showing exact destination URLs
✅ Multiple encoding support (URL, double, null-byte)
✅ File extension fuzzing (.php, .asp, .jsp, .html, etc.)
✅ Multi-wordlist combining for comprehensive coverage

💻 Command Line

✅ Complete CLI interface for automation
✅ Color-coded terminal output
✅ Pipeline-friendly for tool integration
✅ Batch scanning support
✅ Flexible configuration

🚀 Installation
Prerequisites

Python 3.7 or higher
pip (Python package manager)

Method 1: Clone from GitHub
bash# Clone the repository
git clone https://github.com/Tokishi2bu/Path-Hunter.git
cd Path-Hunter

# Install dependencies
pip install -r requirements.txt
Method 2: Install Dependencies Manually
bashpip install flask requests urllib3
Verify Installation
bashpython3 app.py

⚡ Quick Start
Web Interface (Recommended)

Start the server:

bash   python3 app.py

Open your browser:

   http://localhost:5000

Start scanning:

Select wordlists (or upload your own)
Enter target URL
Configure threads and timeout
Click "Start Scan"
Watch real-time results
Download report when complete

# Basic scan
python3 scanner.py -u https://example.com -w wordlists/common.txt

# Advanced scan
python3 scanner.py -u https://example.com \
    -w wordlists/common.txt wordlists/directories.txt \
    -e php,html,js \
    -t 25 \
    -o report.txt