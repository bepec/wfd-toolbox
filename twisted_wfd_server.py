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
    HandshakeGetParameters = 'HandshakeGetParameters'
    HandshakeSetParameters = 'HandshakeSetParameters'
    HandshakeSetup = 'HandshakeSetup'


class WfdProtocol(Protocol):
    OPTIONS_RESPONSE_PUBLIC = "org.wfa.wfd1.0, GET_PARAMETER, SET_PARAMETER"
    OPTIONS_REQUEST_REQUIRE = "org.wfa.wfd1.0"
    GET_PARAMETER = (
        "wfd_video_formats\r\n"
        "wfd_audio_codecs\r\n"
        "wfd_client_rtp_ports\r\n"
        "wfd_content_protection\r\n"
        "wfd_uibc_capability\r\n")
    SET_PARAMETER = (
        "wfd_video_formats: "
        "00 00 01 01 00000020 00000000 00000000 00 0000 0000 00 none none\r\n"
        "wfd_audio_codecs: LPCM 00000002 00\r\n"
        "wfd_presentation_URL: rtsp://172.16.222.110/wfd1.0/streamid=0 none\r\n"
        "wfd_client_rtp_ports: RTP/AVP/UDP;unicast {0} 0 mode=play\r\n")
    TRIGGER_SETUP = "wfd_trigger_method: SETUP\r\n"
    TRIGGER_PLAY = "wfd_trigger_method: PLAY\r\n"
    TRIGGER_PAUSE = "wfd_trigger_method: PAUSE\r\n"
    TRIGGER_TEARDOWN = "wfd_trigger_method: TEARDOWN\r\n"
    DEFAULT_URL = 'rtsp://localhost/wfd1.0'

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
                'OPTIONS': self._handleOptionsRequest,
                'SETUP': self._handleSetupRequest,
                'PLAY': self._handleRequestPositive,
                'PAUSE': self._handleRequestPositive,
                'TEARDOWN': self._handleTeardownRequest,
            }

        self.state = WfdServerState.Handshake
        self.handshakeState = WfdServerState.HandshakeOptions

        self._sendRequest(rtsp.RtspRequest(
            'OPTIONS',
            headers={'Require': self.OPTIONS_REQUEST_REQUIRE}),
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

    def _sendMessage(self, rtspMessage):
        data = str(rtspMessage)
        self.transport.write(data.encode('ascii'))
        self.logger.debug('Data sent:\n' + data)

    def _handleRequest(self, request):
        self.logger.debug('Handling request {0}:{1}'.format(request.method, request.headers['CSeq']))
        handler = self._unhandledRequest
        if request.method in self.requestHandlers.keys():
            handler = self.requestHandlers[request.method]
        for response in handler(request):
            response.cseq = request.cseq
            self._sendMessage(response)

    def _handleResponse(self, response):
        self.logger.debug('Handling response {0}'.format(response.cseq))
        request, responseHandler = self.pendingRequests[response.cseq]
        del self.pendingRequests[response.cseq]
        responseHandler(request, response)

    def _handleOptionsRequest(self, request):
        if self.state is not WfdServerState.Handshake:
            raise Exception('{0} request not expected at state {1}'.format(request.method, self.state))
        if self.handshakeState is not WfdServerState.HandshakeOptions:
            raise Exception('{0} request not expected at state {1}'.format(request.method, self.handshakeState))

        yield rtsp.RtspResponse(headers={
                'Public': self.OPTIONS_RESPONSE_PUBLIC,
            })

        self._sendRequest(
            rtsp.RtspRequest('GET_PARAMETER',
                url=self.DEFAULT_URL,
                content=rtsp.RtspContent('text/parameters',
                                         self.GET_PARAMETER)),
            self._handleGetParameterResponse)

        self.handshakeState = WfdServerState.HandshakeGetParameters

    def _handleSetupRequest(self, request):
        if self.state is not WfdServerState.Handshake:
            raise Exception('{0} request not expected at state {1}'.format(request.method, self.state))
        if self.handshakeState is not WfdServerState.HandshakeSetup:
            raise Exception('{0} request not expected at state {1}'.format(request.method, self.handshakeState))

        yield rtsp.RtspResponse(headers={
                'Transport': request.headers['Transport'],
                'Session': '01234567',
            })

        self.state = WfdServerState.Pause

    def _handleTeardownRequest(self, request):
        yield rtsp.RtspResponse()
        self.transport.loseConnection()

    def _handleGetParameterResponse(self, request, response):
        # TODO: should perform some parsing here
        self.sink_rtp_port = 1028 

        self._sendRequest(
            rtsp.RtspRequest('SET_PARAMETER',
                url=self.DEFAULT_URL,
                content=rtsp.RtspContent('text/parameters',
                                         self.SET_PARAMETER)),
            self._handleSetParameterResponse)

    def _handleSetParameterResponse(self, request, response):
        self._sendRequest(
            rtsp.RtspRequest('SET_PARAMETER',
                url=self.DEFAULT_URL,
                content=rtsp.RtspContent('text/parameters',
                                         self.TRIGGER_SETUP)),
            self._flushResponse)

        self.handshakeState = WfdServerState.HandshakeSetup

    def _unhandledRequest(self, request):
        yield rtsp.RtspResponse(status=406)

    def _handleRequestPositive(self, request):
        yield rtsp.RtspResponse()

    def _flushResponse(self, request, response):
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
