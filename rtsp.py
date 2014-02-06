VERSION = "RTSP/1.0"
DEFAULT_SERVER_PORT = 7236

def message_from_string(string):
    if string.startswith('RTSP'):
        return response_from_string(string)
    else:
        return request_from_string(string)

def request_from_string(string):
  if "\r\n\r\n" not in string:
    return (None, 0)

  length = string.find("\r\n\r\n") + 4
  message = string.split("\r\n\r\n")

  lines = message[0].split("\r\n")

  status_line=lines[0]
  header_pairs = [line.split(": ") for line in lines[1:]]
  headers = {split[0]: split[1] for split in header_pairs if len(split) > 1}
  content = None

  if len(message) == 2 and message[1]:
    content_length = int(headers["Content-Length"])
    content = RtspContent(headers["Content-Type"], message[1][:content_length])
    length += content_length

  method, url, version = status_line.split(" ")

  return (RtspRequest(method, url, headers, content), length)


def response_from_string(string):
  if "\r\n\r\n" not in string:
    return (None, 0)

  length = string.find("\r\n\r\n") + 4
  message = string.split("\r\n\r\n")

  lines = message[0].split("\r\n")

  status_line=lines[0]
  header_pairs = [line.split(": ") for line in lines[1:]]
  headers = {split[0]: split[1] for split in header_pairs if len(split) > 1}
  content = None

  if len(message) == 2 and message[1]:
    content_length = int(headers["Content-Length"])
    content = RtspContent(headers["Content-Type"], message[1][:content_length])
    length += content_length

  version, status = status_line.split(" ")[:2]

  return (RtspResponse(int(status), headers, content), length)


class RtspMessage(object):

  def __init__(self, headers={}, content=None):
    self.version = VERSION
    self.headers = headers
    self.set_content(content)

  def set_content(self, content):
    if content:
      self.content = content.data
      self.headers["Content-Type"] = content.type
      self.headers["Content-Length"] = len(content.data)
    else:
      self.content = None

  @property
  def cseq(self):
      return int(self.headers['CSeq'])

  @cseq.setter
  def cseq(self, value):
      self.headers['CSeq'] = str(value)

  def __str__(self):
    lines = []
    lines.append(self._get_status_line())

    for header_name in self.headers.keys():
      lines.append("{0}: {1}".format(header_name, self.headers[header_name]))

    lines.append("")

    lines.append(self.content if self.content else "")

    return "\r\n".join(lines)


class RtspRequest(RtspMessage):

  def __init__(self, method, url="*", headers={}, content=None):
    super(RtspRequest, self).__init__(headers, content)
    self.method = method
    self.url = url

  def _get_status_line(self):
    return "{0} {1} {2}".format(self.method, self.url, self.version)


class RtspResponse(RtspMessage):
  STATUSES = {
      100: 'Continue',
      200: 'OK',
      201: 'Created',
      250: 'Low on Storage Space',
      300: 'Multiple Choices',
      301: 'Moved Permanently',
      302: 'Moved Temporarily',
      303: 'See Other',
      304: 'Not Modified',
      305: 'Use Proxy',
      400: 'Bad Request',
      401: 'Unauthorized',
      402: 'Payment Required',
      403: 'Forbidden',
      404: 'Not Found',
      405: 'Method Not Allowed',
      406: 'Not Acceptable',
      407: 'Proxy Authentication Required',
      408: 'Request Time-out',
      410: 'Gone',
      411: 'Length Required',
      412: 'Precondition Failed',
      413: 'Request Entity Too Large',
      414: 'Request-URI Too Large',
      415: 'Unsupported Media Type',
      451: 'Parameter Not Understood',
      452: 'Conference Not Found',
      453: 'Not Enough Bandwidth',
      454: 'Session Not Found',
      455: 'Method Not Valid in This State',
      456: 'Header Field Not Valid for Resource',
      457: 'Invalid Range',
      458: 'Parameter Is Read-Only',
      459: 'Aggregate operation not allowed',
      460: 'Only aggregate operation allowed',
      461: 'Unsupported transport',
      462: 'Destination unreachable',
      463: 'Key management Failure',
      500: 'Internal Server Error',
      501: 'Not Implemented',
      502: 'Bad Gateway',
      503: 'Service Unavailable',
      504: 'Gateway Time-out',
      505: 'RTSP Version not supported',
      551: 'Option not supported',
  }

  def __init__(self, status=200, headers={}, content=None):
    super(RtspResponse, self).__init__(headers, content)
    self.status = status

  def _get_status_line(self):
    return "{0} {1} {2}".format(self.version, self.status, self.STATUSES[self.status])


class RtspContent(object):

  def __init__(self, type, data):
    self.type = type
    self.data = data


class RtspEndpoint(object):

  def __init__(self, socket, receiver):
    self.socket = socket
    self.receiver = receiver
    self.request_cseq = 0
    self.buffer = ""

  def send_request(self, request):
    request.headers["CSeq"] = self.request_cseq
    self._send(request)

    print("Waiting for response...")

    response, length = response_from_string(self.buffer)
    if not response:
      self._recv()
      response, length = response_from_string(self.buffer)
    if not response:
      raise Exception("Response not received")
    self.buffer = self.buffer[length:]

    if int(response.headers["CSeq"]) != self.request_cseq:
      raise Exception("Bad CSeq in received response.")
    self.request_cseq += 1
    self.receiver.process_response(response, request.method)

  def wait_for_request(self):
    print("Waiting for request...")

    request, length = request_from_string(self.buffer)
    if not request:
      self._recv()
      request, length = request_from_string(self.buffer)
    if not request:
      raise Exception("Request not received")
    self.buffer = self.buffer[length:]

    response = self.receiver.process_request(request)
    response.headers["CSeq"] = request.headers["CSeq"]
    self._send(response)

  def teardown(self):
    self.socket.close()

  def _recv(self):
    data = self.socket.recv(2048)
    self.buffer += data.decode('ascii')
    print("BUFFER: '{0}'".format(self.buffer))

  def _send(self, data):
    self.socket.send(str(data).encode("ascii"))
    print("SEND:'{0}'".format(str(data)))
