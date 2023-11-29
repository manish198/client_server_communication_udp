import collections
def resolve_url(url):
    # spliting url with ? and seperating query params
    url_array=url.split("?")
    #for query parameters
    param=''
    if len(url_array)==2:
        param=url_array[1]
    #spliting host and the path
    url_parts = url_array[0].split("/")
    #spliting hostname and port number
    host = url_parts[2].split(":")
    hostname = host[0]
    #check for the custom port number
    if len(host)>1:
        port = int(host[1])
    else:
        port = 80
    #create a path for the resources
    path = "/" + "/".join(url_parts[3:])
    return(hostname,port,path,param)

def get_request(buffer):
    request=''
    for keys in buffer:
        request+=buffer[keys]
    return request
def sort_buffer(buffer):
    return collections.OrderedDict(sorted(buffer.items()))
def convert_to_type(udp_header):
    packet_type=udp_header[0]
    sequence_number=int.from_bytes(udp_header[1:5],'big')
    client_address='.'.join(map(str,udp_header[5:9]))
    client_port=int.from_bytes(udp_header[9:11],byteorder='big')
    return packet_type, sequence_number,client_address,client_port

def create_udp_header(packet_type,sequence_number,receiver_address,receiver_port):
    return (
        bytes([packet_type])+
        sequence_number.to_bytes(4,byteorder='big')+
        bytes(receiver_address)+
        receiver_port.to_bytes(2,byteorder='big')
    )

def convert_to_ip_address(address):
        ip=".".join(map(str,address))
        return ip

def get_payload(payload):
    request=''
    for _ in payload:
        request+=_
    return request

def get_datagram_header(hostname,port,packet_type,sequence_number):
    packet_type = packet_type
    sequence_number = sequence_number
    receiver_address = [int(part) for part in hostname.split('.')]
    receiver_port = port
    udp_header = create_udp_header(packet_type, sequence_number, receiver_address, receiver_port)
    return udp_header

def parse_response(response_text):
    headers, body = response_text.split('\r\n\r\n', 1)
    status_line=headers.split('\r\n')[0]
    status_code=status_line.split(' ')[1]
    status_message_list=status_line.split(' ')[2:]
    status_message=''
    for word in status_message_list:
        status_message=status_message+' '+word
    return(headers,body,status_line,status_code,status_message)

#method to output response
def display_response(headers,body,verbosity,filetowrite,status_code,status_message):
    final_output=''
    print('Displaying Responses: \n')
    #if verbose is used with the command
    if verbosity:
        #add headers and body
        final_output=headers+'\n'+body+'\n'
    else:
        #add body only
        final_output=body+'\n'
    #option to write on a file.
    if filetowrite:
        print('Response Status: ',status_code,' ',status_message)
        with open(filetowrite,"a+") as file:
            #write a final output.
            file.write(final_output)
            file.close()
        print('written in a file',filetowrite)
    #display in console.
    else:
        print('Response Status: ',status_code,' ',status_message,'\n')
        print(final_output)
#helper method to create a dict.
def create_dict(headers):
    dict={}
    #create a dictionary for the header components.
    headers_lines=headers.split('\r\n')
    #loop over the headers and create a key value pairs for the dictionary.
    for _ in headers_lines[1:]:
        headers_array=_.split(':')
        dict[headers_array[0].strip().lower()]=headers_array[1].strip()
    return dict