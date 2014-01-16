import socket
from rtsp import *


class WfdServer:
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
    URL = "rtsp://localhost/wfd1.0"

    def __init__(self):
        self.sink_rtp_port = 1028
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def serve_port(self, port):
        self.socket.bind(('', port))
        print("Listening on port {0}.".format(port))
        self.socket.listen(1)

        while True:
            print("Waiting for a client...")
            client_socket, address = self.socket.accept()
            print("Serving client {0} on port {1}.".format(address, port))
            try:
                self._serve_endpoint(RtspEndpoint(client_socket, self))
            except Exception as e:
                print("ERROR: {0}".format(e))
                client_socket.close()
            print("{0} disconnected.".format(address))

    def process_request(self, request):
        if request.method == "OPTIONS":
            return RtspResponse(headers={"Public": self.OPTIONS_RESPONSE_PUBLIC})
        elif request.method == "SETUP":
            return self._process_transport(request.headers["Transport"])
        elif request.method == "PLAY":
            return self._process_play()
        elif request.method == "PAUSE":
            return self._process_pause()
        elif request.method == "TEARDOWN":
            return self._process_teardown()
        raise Exception("Unexpected request!")

    def process_response(self, response, method):
        if response.status != 200:
            raise Exception("Reponse has error code {0}".format(response.status))

    def _serve_endpoint(self, endpoint):
        self.disconnecting = False

        endpoint.send_request(RtspRequest(
            "OPTIONS",
            headers={"Require": self.OPTIONS_REQUEST_REQUIRE}))
        endpoint.wait_for_request()
        endpoint.send_request(RtspRequest(
            "GET_PARAMETER",
            url=self.URL,
            content=RtspContent("text/parameters",
                                self.GET_PARAMETER)))
        endpoint.send_request(RtspRequest(
            "SET_PARAMETER",
            url=self.URL,
            content=RtspContent("text/parameters",
                                self.SET_PARAMETER.format(self.sink_rtp_port))))
        endpoint.send_request(RtspRequest(
            "SET_PARAMETER",
            url=self.URL,
            content=RtspContent("text/parameters",
                                self.TRIGGER_SETUP)))
        endpoint.wait_for_request()

        while not self.disconnecting:
            endpoint.wait_for_request()

        endpoint.teardown()

    def _process_transport(self, transport):
        params = transport.split(";")
        for param in params:
            if "client_port=" in param:
                return RtspResponse(headers={"Session": "01234567;timeout=30",
                                             "Transport": transport})
        raise Exception("Bad transport!")

    def _process_play(self):
        return RtspResponse()

    def _process_pause(self):
        return RtspResponse()

    def _process_teardown(self):
        self.disconnecting = True
        return RtspResponse()


def main():
    print("hello")
    server = WfdServer()
    server.serve_port(7236)


if __name__ == "__main__":
    main()
