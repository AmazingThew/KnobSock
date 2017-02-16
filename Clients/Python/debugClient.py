import socket
HOST, PORT = "localhost", 8008

NUM_KNOBS = 24

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.connect((HOST, PORT))
    while True:
        received = bytearray(sock.recv(NUM_KNOBS))
        print('\n')
        print('\n'.join("{}:\t{}".format(i, float(b) / 127.0) for i, b in enumerate(received)))

        if len(received) == 0:
            print('Zero bytes received; terminating')
            break