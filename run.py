import sys

from yowsup.layers.auth                        import YowAuthenticationProtocolLayer
from yowsup.layers.protocol_messages           import YowMessagesProtocolLayer
from yowsup.layers.protocol_receipts           import YowReceiptProtocolLayer
from yowsup.layers.protocol_acks               import YowAckProtocolLayer
from yowsup.layers.network                     import YowNetworkLayer
from yowsup.layers.coder                       import YowCoderLayer
from yowsup.layers.protocol_media              import YowMediaProtocolLayer

from yowsup.stacks import YowStack
from yowsup.common import YowConstants
from yowsup.layers import YowLayerEvent
from yowsup.stacks import YowStack, YOWSUP_CORE_LAYERS
from yowsup import env
from yowsup.layers.axolotl import YowAxolotlLayer

from yowsup_server import ServerLayer

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from SocketServer import ThreadingMixIn
import threading
import logging
import json
import urllib2
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

stack = None
def connect_whatsapp(phone, password):
    layers = (
        ServerLayer,
        (YowAuthenticationProtocolLayer, YowMessagesProtocolLayer, YowReceiptProtocolLayer, YowAckProtocolLayer, YowMediaProtocolLayer),
        #YowAxolotlLayer,
    ) + YOWSUP_CORE_LAYERS

    stack = YowStack(layers)
    stack.setProp(YowAuthenticationProtocolLayer.PROP_CREDENTIALS, (phone, password))         #setting credentials
    stack.setProp(YowNetworkLayer.PROP_ENDPOINT, YowConstants.ENDPOINTS[0])    #whatsapp server address
    stack.setProp(YowCoderLayer.PROP_DOMAIN, YowConstants.DOMAIN)
    stack.setProp(YowCoderLayer.PROP_RESOURCE, env.CURRENT_ENV.getResource())          #info about us as WhatsApp client

    return stack

class ApiRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write("Working.")

    def do_POST(self):
        out = {}
        try:
            ret = self._do_POST()
            self.send_response(200)
            out['success'] = True
            out['message'] = ret
        except Exception, e:
            out['success'] = False
            out['message'] = str(e)
            self.send_response(500)

        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(out))

    def _do_POST(self):
        data_string = self.rfile.read(int(self.headers['Content-Length']))
        logging.info("api data: %s"%data_string)
        data = json.loads(data_string)
        if stack is not None:
            ServerLayer.send_message(stack, data['phone'], data['message'])
            return "Queued for delivery"
        else:
            raise StandardError("stack not ready yet.")

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass

class AppPinger(threading.Thread):
    def __init__(self, delay, app_name):
        threading.Thread.__init__(self)
        self.app_name = app_name
        self.delay = delay

    def run(self):
        while True:
            time.sleep(self.delay)
            self.ping_app()

    def ping_app(self):
        try:
            url ='http://%s.herokuapp.com'%self.app_name
            logging.info("pinging app @ %s"%url)
            response = urllib2.urlopen(url)
            html = response.read()
            logging.info("app returned: %s"%html)
        except Exception,e:
            logging.error(e)

if __name__==  "__main__":
    logging.info("command args %s"%sys.argv)
    phone = sys.argv[1]
    password = sys.argv[2]
    port = int(sys.argv[3])
    try:
        app_name = sys.argv[4]
    except IndexError,e:
        app_name = None

    global stack
    stack = connect_whatsapp(phone, password)

    # start http api server for sending messages
    logging.info("Starting server on port %s"%port)
    server = ThreadedHTTPServer(('0.0.0.0', port), ApiRequestHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    # start a Timer to ping every minute so heroku keeps our dyno alive
    pinger = AppPinger(60, app_name)
    pinger.start()

    # start yowsup loop
    while True:
        logging.info("connecting to whatsup")
        stack.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT))   #sending the connect signal
        stack.loop()
        logging.info("connection done.")


