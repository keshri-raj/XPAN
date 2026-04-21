import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from sim.run import run_simulation
import os

class APIHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/api/compare":
            query = parse_qs(parsed_path.query)
            scenario = query.get('scenario', ['walk_away'])[0]
            strategy = query.get('strategy', ['adaptive_twt'])[0]
            
            try:
                res_reactive = run_simulation("xpan_reactive", scenario, strategy)
                res_predictive = run_simulation("xpan_predictive", scenario, strategy)
                
                response_data = {
                    "reactive": res_reactive,
                    "predictive": res_predictive
                }
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        elif parsed_path.path == "/":
            self.path = "/static/index.html"
            super().do_GET()
        else:
            super().do_GET()

if __name__ == '__main__':
    server_address = ('', 8000)
    httpd = HTTPServer(server_address, APIHandler)
    print("Serving UI on http://127.0.0.1:8000")
    httpd.serve_forever()
