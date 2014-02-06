import rtsp
import logging
import sys
from twisted.internet import reactor
from twisted.internet.protocol import ServerFactory, Protocol


_default_log_handler = logging.StreamHandler(stream=sys.stdout)
_default_log_handler.setFormatter(logging.Formatter(
        '%(asctime)s\t[%(name)s]\t%(message)s'))


class WfdServerState(object):
    Initial = 'Initial'
    Handshake = 'Handshake'
    Trigger = 'Trigger'
    Play = 'Play'
    Pause = 'Pause'

    HandshakeOptions = 'HandshakeOptions'
    HandshakeParameters = 'HandshakeParameters'
    HandshakeOptions = 'HandshakeOptions'


class WfdProtocol(Protocol):
    cseq = 0

    def connectionMade(self):
        self.name = 'WfdClient:{0}:{1}'.format(self.transport.getPeer().host,
                                               self.transport.getPeer().port)
        self.logger = logging.Logger(self.name, logging.DEBUG)
        self.logger.addHandler(_default_log_handler)
        self.logger.debug('Connection made')
        self.cseq = 0
        self.pendingRequests = {}
        self.messageHandlers = {
                rtsp.RtspRequest: self._handleRequest,
                rtsp.RtspResponse: self._handleResponse,
            }
        self.requestHandlers = {
#                'OPTIONS': self._handleOptionsRequest,
            }

        self.state = WfdServerState.Handshake
        self.handshakeState = WfdServerState.HandshakeOptions

        self._sendRequest(rtsp.RtspRequest(
            'OPTIONS',
            headers={'Require': 'org.wfa.wfd1.0'}),
            responseHandler=self._flushResponse)

    def dataReceived(self, data):
        self.logger.debug('Data received:\n'+data)
        string = data.decode('ascii')
        while True:
            message, length = rtsp.message_from_string(string)
            if not message:
                break
            self.messageHandlers[message.__class__](message)
            string = string[length:]

    def connectionLost(self, reason):
        self.logger.debug('Connection lost')

    def _sendRequest(self, request, responseHandler):
        request.cseq = self.cseq
        self._sendMessage(request)
        self.pendingRequests[self.cseq] = (request, responseHandler)
        self.cseq += 1

    def _handleRequest(self, request):
        self.logger.debug('Handling request {0}:{1}'.format(request.method, request.headers['CSeq']))
        if request.method in self.requestHandlers.keys():
            response = self.requestHandlers[request.method](request)
        else: # unhandled response error
            self.logger.warning('Unhandled request: {0}'.format(request))
            response = rtsp.RtspResponse(status=406)
        response.cseq = request.cseq
        self._sendMessage(response)

    def _handleResponse(self, response):
        self.logger.debug('Handling response {0}'.format(response.cseq))
        request, responseHandler = self.pendingRequests[response.cseq]
        del self.pendingRequests[response.cseq]
        responseHandler(request, response)

    def _sendMessage(self, rtspMessage):
        data = str(rtspMessage)
        self.transport.write(data.encode('ascii'))
        self.logger.debug('Data sent:\n' + data)

    def _handleOptionsRequest(self, request):
        if self.state is not WfdServerState.Handshake:
            raise Exception('{0} request not expected at state {1}'.format(request.method, self.state))
        if self.handshakeState is not WfdServerState.HandshakeOptions:
            raise Exception('{0} request not expected at state {1}'.format(request.method, self.handshakeState))

        return rtsp.RtspResponse(headers={
                'Public': 'org.wfa.wfd1.0, GET_PARAMETER, SET_PARAMETER'
            })

    def _flushResponse(self, request, response):
        pass

    def _cbResponse(self, request, response):
        pass


class WfdServerFactory(ServerFactory):

    protocol = WfdProtocol

    def __init__(self, port=rtsp.DEFAULT_SERVER_PORT):
        self.port = port
        self.clients = []
        self.logger = logging.Logger('WfdServer:{0}'.format(port), logging.DEBUG)
        self.logger.addHandler(_default_log_handler)

    def startFactory(self):
        self.logger.info('Start listening on port {0}'.format(self.port))
        ServerFactory.startFactory(self)

    def buildProtocol(self, addr):
        self.logger.info('Client connected: '+repr(addr))
        return ServerFactory.buildProtocol(self, addr)


def main():
    logger = logging.Logger('MAIN', level=logging.DEBUG)
    logger.addHandler(_default_log_handler)
    logger.info('Test WFD Server v0.2 - powered by Twisted')

    wfdFactory = WfdServerFactory()
    reactor.listenTCP(wfdFactory.port, wfdFactory)
    reactor.run()


if __name__ == '__main__':
    main()
