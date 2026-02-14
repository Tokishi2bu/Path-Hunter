#!/usr/bin/env python3
"""
PathHunter - Cyberpunk Directory Scanner
Similar to dirsearch - Performs directory and subdomain enumeration
"""

import requests
import threading
from queue import Queue
from urllib.parse import urljoin, urlparse
import time
from datetime import datetime
import sys

class DirScanner:
    def __init__(self, target, wordlists, threads=10, timeout=5, user_agent=None, extensions=None):
        self.target = target.rstrip('/')
        self.wordlists = wordlists
        self.threads = threads
        self.timeout = timeout
        self.user_agent = user_agent or "DirScanner/1.0"
        self.extensions = extensions or ['']
        self.queue = Queue()
        self.results = []
        self.scanned = 0
        self.total = 0
        self.lock = threading.Lock()
        self.start_time = None
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})
        self.stop_flag = lambda: False  # Function to check if stop requested
        
    def load_wordlists(self):
        """Load all wordlists into memory"""
        paths = []
        for wordlist_file in self.wordlists:
            try:
                with open(wordlist_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        path = line.strip()
                        if path and not path.startswith('#'):
                            paths.append(path)
            except Exception as e:
                print(f"[!] Error loading {wordlist_file}: {str(e)}")
        
        # Remove duplicates
        paths = list(set(paths))
        return paths
    
    def generate_urls(self, paths):
        """Generate URLs with extensions (like dirsearch)"""
        urls = []
        for path in paths:
            # Ensure path starts with / for proper URL construction
            if not path.startswith('/'):
                path = '/' + path
            
            for ext in self.extensions:
                if ext:
                    # Path with extension
                    url = f"{self.target}{path}{ext}"
                else:
                    # Path without extension
                    url = f"{self.target}{path}"
                
                urls.append(url)
        return urls
    
    def test_url(self, url):
        """Test a single URL"""
        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                allow_redirects=False,
                verify=False
            )
            
            with self.lock:
                self.scanned += 1
                
            status_code = response.status_code
            content_length = len(response.content)
            
            # Get redirect location if present
            redirect_location = None
            if status_code in [301, 302, 303, 307, 308] and 'Location' in response.headers:
                redirect_location = response.headers['Location']
            
            # FILTER FALSE POSITIVES like dirsearch does
            
            # Skip redirects to different domains (wildcard redirects - FALSE POSITIVE)
            if redirect_location:
                from urllib.parse import urlparse
                original_domain = urlparse(url).netloc
                redirect_domain = urlparse(redirect_location).netloc
                
                # If redirecting to different domain, it's a false positive
                if redirect_domain and redirect_domain != original_domain:
                    return
                
                # If redirecting to homepage/root, it's a false positive
                redirect_path = urlparse(redirect_location).path
                if redirect_path in ['/', '', '/index.html', '/index.php']:
                    return
            
            # ONLY record status codes that indicate resource EXISTS (like dirsearch)
            # DO NOT record redirects unless they're to the SAME path on same domain
            if status_code in [200, 201, 204, 401, 403, 405, 500, 503]:
                result = {
                    'url': url,
                    'status': status_code,
                    'size': content_length,
                    'redirect': redirect_location,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                with self.lock:
                    self.results.append(result)
                    self.print_result(result)
            # Only show 301/302 if it's redirecting within the same domain to a different path
            elif status_code in [301, 302] and redirect_location:
                from urllib.parse import urlparse
                redirect_path = urlparse(redirect_location).path
                original_path = urlparse(url).path
                
                # Only show if redirecting to a DIFFERENT path on SAME domain
                if redirect_path != original_path:
                    result = {
                        'url': url,
                        'status': status_code,
                        'size': content_length,
                        'redirect': redirect_location,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    with self.lock:
                        self.results.append(result)
                        self.print_result(result)
                    
        except requests.exceptions.Timeout:
            pass
        except requests.exceptions.ConnectionError:
            pass
        except requests.exceptions.TooManyRedirects:
            pass
        except Exception:
            pass
    
    def print_result(self, result):
        """Print a result to console (dirsearch style)"""
        status = result['status']
        size = result['size']
        url = result['url']
        redirect = result.get('redirect')
        
        # Simple color coding like dirsearch
        if status == 200:
            status_str = f"\033[92m{status}\033[0m"  # Green
        elif status in [301, 302]:
            status_str = f"\033[93m{status}\033[0m"  # Yellow
        elif status in [401, 403]:
            status_str = f"\033[91m{status}\033[0m"  # Red
        else:
            status_str = f"\033[94m{status}\033[0m"  # Blue
        
        # Format output like dirsearch
        output = f"[{status_str}] {size:>8}B  {url}"
        
        # Add redirect location if present
        if redirect:
            output += f"  -> {redirect}"
        
        print(output)
    
    def worker(self):
        """Worker thread that processes URLs from queue"""
        while not self.stop_flag():
            try:
                url = self.queue.get(timeout=0.05)  # Very short timeout for fast response
                if url is None:
                    self.queue.task_done()
                    break
                    
                # Check stop flag before processing
                if not self.stop_flag():
                    self.test_url(url)
                    
                self.queue.task_done()
            except:
                # Queue empty or timeout - check stop flag and continue
                if self.stop_flag():
                    break
                continue
    
    def print_progress(self):
        """Print progress periodically"""
        while self.scanned < self.total:
            with self.lock:
                progress = (self.scanned / self.total) * 100 if self.total > 0 else 0
                elapsed = time.time() - self.start_time
                rate = self.scanned / elapsed if elapsed > 0 else 0
                print(f"\r[*] Progress: {self.scanned}/{self.total} ({progress:.1f}%) - {rate:.1f} req/s", end='', flush=True)
            time.sleep(0.5)
        print()  # New line after completion
    
    def scan(self):
        """Start the scanning process"""
        print(f"\n[*] Target: {self.target}")
        print(f"[*] Wordlists: {', '.join(self.wordlists)}")
        print(f"[*] Threads: {self.threads}")
        print(f"[*] Timeout: {self.timeout}s")
        print(f"[*] Extensions: {', '.join(self.extensions) if self.extensions != [''] else 'None'}")
        print("\n[*] Loading wordlists...")
        
        paths = self.load_wordlists()
        print(f"[*] Loaded {len(paths)} unique paths")
        
        urls = self.generate_urls(paths)
        self.total = len(urls)
        print(f"[*] Testing {self.total} URLs\n")
        
        self.start_time = time.time()
        
        # Start worker threads
        threads = []
        for _ in range(self.threads):
            t = threading.Thread(target=self.worker)
            t.daemon = True
            t.start()
            threads.append(t)
        
        # Start progress thread
        progress_thread = threading.Thread(target=self.print_progress)
        progress_thread.daemon = True
        progress_thread.start()
        
        # Add URLs to queue (but stop if flag set)
        added = 0
        for url in urls:
            if self.stop_flag():
                print("\n[!] Stop requested, cancelling remaining URLs...")
                break
            self.queue.put(url)
            added += 1
        
        # If stopped early, signal workers to stop
        if self.stop_flag():
            print(f"[!] Scan stopped after adding {added}/{self.total} URLs")
            # Stop workers immediately
            for _ in range(self.threads):
                self.queue.put(None)
        else:
            # Normal completion - wait for queue to empty
            try:
                self.queue.join()
            except:
                pass
            
            # Stop workers
            for _ in range(self.threads):
                self.queue.put(None)
        
        # Don't wait too long for threads
        for t in threads:
            t.join(timeout=0.5)
        
        # Don't wait for progress thread
        
        elapsed = time.time() - self.start_time
        
        if self.stop_flag():
            print(f"\n[!] Scan stopped after {elapsed:.2f}s")
        else:
            print(f"\n[+] Scan completed in {elapsed:.2f}s")
            
        print(f"[+] Found {len(self.results)} results")
        
        return self.results
    
    def save_report(self, output_file):
        """Save results to a text file"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write(f"PathHunter Scan Report\n")
                f.write(f"Target: {self.target}\n")
                f.write(f"Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total URLs Tested: {self.total}\n")
                f.write(f"Results Found: {len(self.results)}\n")
                f.write("=" * 80 + "\n\n")
                
                if not self.results:
                    f.write("No results found.\n")
                else:
                    # Sort results by status code
                    sorted_results = sorted(self.results, key=lambda x: (x['status'], x['url']))
                    
                    for result in sorted_results:
                        f.write(f"[{result['status']}] {result['size']:>8}B  {result['url']}\n")
                        if result.get('redirect'):
                            f.write(f"    Redirect: {result['redirect']}\n")
                        f.write(f"    Timestamp: {result['timestamp']}\n")
                        f.write("\n")
                
                f.write("\n" + "=" * 80 + "\n")
                f.write(f"Scan completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            print(f"[+] Report saved to: {output_file}")
            return True
        except Exception as e:
            print(f"[!] Error saving report: {str(e)}")
            return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='PathHunter - Cyberpunk Directory Scanner (Similar to dirsearch)',
        epilog='⚡ Hunt paths. Find secrets. Own systems. ⚡'
    )
    parser.add_argument('-u', '--url', required=True, help='Target URL')
    parser.add_argument('-w', '--wordlists', nargs='+', required=True, help='Wordlist file(s)')
    parser.add_argument('-t', '--threads', type=int, default=10, help='Number of threads (default: 10)')
    parser.add_argument('-o', '--output', default='scan_report.txt', help='Output report file')
    parser.add_argument('--timeout', type=int, default=5, help='Request timeout (default: 5s)')
    parser.add_argument('-e', '--extensions', help='File extensions (comma-separated, e.g., .php,.html)')
    
    args = parser.parse_args()
    
    # Parse extensions
    extensions = ['']
    if args.extensions:
        extensions = [''] + ['.' + ext.strip().lstrip('.') for ext in args.extensions.split(',')]
    
    # Disable SSL warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Create scanner
    scanner = DirScanner(
        target=args.url,
        wordlists=args.wordlists,
        threads=args.threads,
        timeout=args.timeout,
        extensions=extensions
    )
    
    # Run scan
    try:
        results = scanner.scan()
        scanner.save_report(args.output)
    except KeyboardInterrupt:
        print("\n\n[!] Scan interrupted by user")
        if scanner.results:
            print("[*] Saving partial results...")
            scanner.save_report(args.output)
        sys.exit(0)