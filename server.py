import socket
import sys
from datetime import datetime
import multiprocessing as mp

SERVER_ADDRESS = HOST, PORT = '', 8080 #TODO Make this configurable

class EnvironBuilder():
    
    #Initialise with defaults
    def __init__(self):
        env = {}
        env['wsgi.version']      = (1, 0)
        env['wsgi.url_scheme']   = 'http'
        env['wsgi.input']        = sys.stdin.buffer
        env['wsgi.errors']       = sys.stderr
        env['wsgi.multithread']  = False
        env['wsgi.multiprocess'] = True
        env['wsgi.run_once']     = False
        # Required CGI variables
        env['SERVER_NAME']       = socket.getfqdn(HOST)      # localhost
        env['SERVER_PORT']       = PORT  # 8888
        
        self.env = env
    
    def set_path(self, path):
        self.env['PATH_INFO'] = path
        return self
    
    def set_method(self, method):
        self.env['REQUEST_METHOD'] = method
        return self
    
    def build_environ(self):
        return self.env


class Worker():
    def __init__(self, host, port, application):
        self.host = host
        self.port = port
        self.headers = []
        self.application = application
    
    def run(self, socket):
        while True:
            process = mp.Process(target=self.execute, args=socket.accept())
            process.start()
            process.join(0)

    def execute(self, connection, address):
        (method, path, version) = self.parse_request(connection)
        env_builder = EnvironBuilder()
        env = env_builder.set_method(method).set_path(path).build_environ()

        result = self.application(env, self.start_response)
        with connection:
            status, headers = self.headers
            response = self.build_response(version, status, headers, result)
            print(''.join( #TODO Actual async logging implementation
                 f'> {line}\n' for line in response.splitlines()
             ))
            connection.sendall(response.encode())

    def parse_request(self, connection):
        request = connection.recv(1024)
        request = request.decode('utf-8')
        
        status_line = request.split('\n', 1)[0].rstrip('\r\n')
        
        return status_line.split()

    def start_response(self, status, response_headers, exc_info=None):
        server_headers = [
            ('Date', datetime.utcnow().strftime("%a, %d %b %G %T %Z")),
            ('Server', 'WSGIServer 0.2')
        ]
        
        self.headers = [status, response_headers + server_headers]
    
    def build_response(self, version, status, headers, data):
        response = f'{version} {status}\r\n'
        for header in headers:
            response += '{0}: {1}\r\n'.format(*header)
        response += '\r\n'
        for d in data:
            response += d.decode('utf-8')
        return response

class WSGIServer(object):
    address_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    request_queue_size = 5 #TODO Dynamic queue size
    
    def __init__(self, server_address, application):
        self.application = application

        self.listen_socket = listen_socket = socket.socket(self.address_family, self.socket_type)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind(server_address)
        listen_socket.listen(self.request_queue_size)
        HOST, PORT = self.listen_socket.getsockname()[:2]
        
    def serve_forever(self):
        listen_socket = self.listen_socket
        worker = Worker(HOST, PORT, self.application)
        while True:
            worker.run(listen_socket)

if __name__ == '__main__':
    if len(sys.argv) < 2: #TODO Proper arg validation
        sys.exit('Provide a WSGI application object as module:callable')
    
    app_path = sys.argv[1]
    module, application = app_path.split(':')
    module = __import__(module)
    application = getattr(module, application)
    server = WSGIServer(SERVER_ADDRESS, application)
    print(f'WSGIServer: Serving HTTP on {PORT}\n')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)