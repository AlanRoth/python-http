import socket, io, sys, os
from datetime import datetime
import multiprocessing as mp

SERVER_ADDRESS = HOST, PORT = '', 8080 #TODO Make this configurable

class WSGIServer(object):
    address_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    request_queue_size = 5 #TODO Dynamic queue size
    
    def __init__(self, server_address):
        self.listen_socket = listen_socket = socket.socket(self.address_family, self.socket_type)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind(server_address)
        listen_socket.listen(self.request_queue_size)
        HOST, PORT = self.listen_socket.getsockname()[:2]
        #self.server_name = socket.getfqdn(host)
        #self.server_port = self.port
        self.headers_set = []
    
    def set_app(self, application):
        self.application = application
        
    def serve_forever(self): #TODO Serve while active and upto a timeout
        listen_socket = self.listen_socket
        while True: #TODO Process pool, reusing processes? Close processes elegantly
            self.client_connection, client_address = listen_socket.accept()
            process = mp.Process(target=self.handle_request) #TODO Make multiprocessing optional
            process.start()
            print(f"started process {process.pid}") #TODO Proper logging
            process.join(0)
    
    def handle_request(self):
        request_data = self.client_connection.recv(1024)
        self.request_data = request_data = request_data.decode('utf-8')
        
        self.parse_request(request_data)
        
        #Construct environment dictionary
        env = self.get_environ()
        result = self.application(env, self.start_response)
        
        self.finish_response(result)
        
    def parse_request(self, data):
        request_line = data.splitlines()[0] #TODO Fix IndexError
        request_line = request_line.rstrip('\r\n')
        
        #Break into components
        (self.request_method,
        self.path,
        self.request_version) = request_line.split()
        
    def get_environ(self):
        #TODO Refactor with PEP8
        env = {}
        
        env['wsgi.version']      = (1, 0)
        env['wsgi.url_scheme']   = 'http'
        env['wsgi.input']        = io.StringIO(self.request_data)
        env['wsgi.errors']       = sys.stderr
        env['wsgi.multithread']  = False
        env['wsgi.multiprocess'] = False
        env['wsgi.run_once']     = False
        # Required CGI variables
        env['REQUEST_METHOD']    = self.request_method    # GET
        env['PATH_INFO']         = self.path              # /hello
        env['SERVER_NAME']       = socket.getfqdn(HOST)      # localhost
        env['SERVER_PORT']       = PORT  # 8888
        
        return env
        
    def start_response(self, status, response_headers, exc_info=None):
        server_headers = [
            ('Date', datetime.utcnow().strftime("%a, %d %b %G %T %Z")),
            ('Server', 'WSGIServer 0.2')
        ]
        
        self.headers_set = [status, response_headers + server_headers]
        
    def finish_response(self, result):
        try:
            status, response_headers = self.headers_set
            response = f'HTTP/1.1 {status}\r\n'
            for header in response_headers:
                response += '{0}: {1}\r\n'.format(*header)
            response += '\r\n'
            for data in result:
                response += data.decode('utf-8') #TODO Check for encoding before decoding
            print(''.join( #TODO Actual async logging implementation
                f'> {line}\n' for line in response.splitlines()
            ))
            response_bytes = response.encode()
            self.client_connection.sendall(response_bytes)
            print(os.getpid())
        finally:
            self.client_connection.close() #TODO Try with resources

def make_server(server_address, application):
    server = WSGIServer(server_address)
    server.set_app(application)
    return server

if __name__ == '__main__':
    if len(sys.argv) < 2: #TODO Proper arg validation
        sys.exit('Provide a WSGI application object as module:callable')
    
    app_path = sys.argv[1]
    module, application = app_path.split(':')
    module = __import__(module)
    application = getattr(module, application)
    httpd = make_server(SERVER_ADDRESS, application)
    print(f'WSGIServer: Serving HTTP on port {PORT}\n')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)