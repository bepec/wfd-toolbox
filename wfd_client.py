import socket
from rtsp import * 


class WfdClient:
  GET_PARAMETER = ("wfd_audio_codecs: LPCM 00000003 00\r\n"
                   "wfd_client_rtp_ports: RTP/AVP/UDP;unicast 1028 0 mode=play\r\n"
                   "wfd_content_protection: none\r\n"
                   "wfd_uibc_capability: none\r\n"
                   "wfd_video_formats: 00 00 01 01 00000021 00000000 00000000 00 0000 0000 00 none none\r\n")
  SET_PARAMETER = ("wfd_video_formats: 00 00 01 01 00000020 00000000 00000000 00 0000 0000 00 none none\r\n"
                   "wfd_audio_codecs: LPCM 00000002 00\r\n"
                   "wfd_presentation_URL: rtsp://172.16.222.110/wfd1.0/streamid=0 none\r\n"
                   "wfd_client_rtp_ports: RTP/AVP/UDP;unicast {0} 0 mode=play\r\n")
  TRANSPORT="RTP/AVP/UDP;unicast;client_port={0}"
  TRIGGER_SETUP="wfd_trigger_method: SETUP\r\n"
  TRIGGER_PLAY="wfd_trigger_method: PLAY\r\n"
  TRIGGER_PAUSE="wfd_trigger_method: PAUSE\r\n"
  TRIGGER_TEARDOWN="wfd_trigger_method: TEARDOWN\r\n"
  URL="rtsp://localhost/wfd1.0"

  def __init__(self):
    self.rtp_port = 1028

  def connect(self, address, port):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((address, port))

    endpoint = RtspEndpoint(client_socket, self)
    endpoint.wait_for_request() # M1
    endpoint.send_request(RtspRequest("OPTIONS", headers={"Require": "org.wfa.wfd1.0"})) # M2
    endpoint.wait_for_request() # M3
    endpoint.wait_for_request() # M4
    endpoint.wait_for_request() # M5
    endpoint.send_request(RtspRequest("SETUP", headers={"Transport": self.TRANSPORT.format(self.rtp_port)})) # M6
    endpoint.send_request(RtspRequest("PLAY")) # M7
    endpoint.send_request(RtspRequest("PAUSE")) # M7
    endpoint.send_request(RtspRequest("TEARDOWN")) # M7
    endpoint.teardown()

  def process_request(self, request):
    if request.method == "OPTIONS":
      return RtspResponse(200, headers={"Public": "org.wfa.wfd1.0, GET_PARAMETER, SET_PARAMETER"})
    elif request.method == "GET_PARAMETER":
      return RtspResponse(200, content=RtspContent("text/parameters", self.GET_PARAMETER))
    elif request.method == "SET_PARAMETER":
      if "wfd_trigger_method" in request.content:
        method = request.content.split(": ")[1]
        return RtspResponse(200)
      else:
        return RtspResponse(content=RtspContent("text/parameters", self.SET_PARAMETER))
    raise Exception("Unexpected request!")

  def process_response(self, response, method):
    if response.status != 200:
      raise Exception("Reponse has error code {0}".format(response.status))


def main():
  print("hello")
  client = WfdClient()
  client.connect('127.0.0.1', 7236)
    

if __name__ == "__main__":
  main()
