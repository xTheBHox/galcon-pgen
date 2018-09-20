import socket, threading
import pickle
import queue
from queue import Queue

PORT = 15112
HEADERSIZE = 2 ** 8
B_ORDER = 'big'


# Some of this code is inspired by Rohan's optional socket lecture.
# Nonetheless, I wrote every line myself and understand what is going on.

def connectToServer(sck, address, recvQ):
    if address == "": address = 'localhost'

    try: sck.connect((address, PORT))
    except (ConnectionRefusedError, OSError): return

    connected = True

    recvQ.put('connected')

    while connected:
        # get a header specifying the body size
        try:
            msgSizeB = sck.recv(HEADERSIZE, socket.MSG_WAITALL)
            msgSize = int.from_bytes(msgSizeB, B_ORDER)
        # get the body
            msgP = sck.recv(msgSize, socket.MSG_WAITALL)
        except (OSError, OverflowError):
            print("Error in connection to server")
            break
        try:
            msg = pickle.loads(msgP)
        except EOFError:
            print("EOF Error")
            continue
        if msg == 'exit': connected = False
        recvQ.put(msg, False)

    sck.close()

    print("Closing connection to server!")

class ServerBridge():

    def __init__(self, address):
        self.sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.recvQ = Queue()

        self.connectThread = threading.Thread(target=connectToServer,
                                              args=(self.sck, address,
                                              self.recvQ))
        self.connectThread.start()

    def connecting(self):
        return self.connectThread.is_alive()

    def sendMsg(self, msg):
        msgP = pickle.dumps(msg)
        msgSizeB = len(msgP).to_bytes(HEADERSIZE, B_ORDER)
        try:
            self.sck.send(msgSizeB)
            self.sck.send(msgP)
        except OSError:
            print("Unable to connect to game server.")


    def disconnect(self):
        self.sendMsg('exit')
        print('Server bridge attempting to disconnect.')

    def getMsg(self):
        try:
            msg = self.recvQ.get_nowait()
        except queue.Empty:
            return
        return msg

#### server

def serverListener(server, IP, players, inQ, outQ):
    if IP == "": IP = 'localhost'

    try: server.bind((IP, PORT))
    except socket.gaierror: return

    server.listen()

    inQ.put('serverup')
    print('Listening...')

    clientDict = dict()

    broadcastThread = threading.Thread(target=broadcastServer,
                                       args=(clientDict, outQ))
    broadcastThread.start()

    for i in range(players):
        incSocket, address = server.accept()
        clientDict[i] = ((address, incSocket))
        clientThread = threading.Thread(target=startIncoming,
                                        args=(incSocket, address, inQ, i))
        clientThread.start()
        inQ.put('1connect')


    inQ.put('allconnected')
    server.close()
    print("All players connected. Listener closed.")

def broadcastServer(clientDict, broadcastQueue):
    broadcastActive = True

    dc = []
    while broadcastActive:
        p, msg = broadcastQueue.get(True)
        msgP = pickle.dumps(msg)
        msgSizeB = len(msgP).to_bytes(HEADERSIZE, B_ORDER)
        if p == -1:
            for i in clientDict:
                address, incSocket = clientDict[i]
                try:
                    incSocket.send(msgSizeB)
                    incSocket.send(msgP)
                except OSError: # socket closed
                    print(address, 'connection error')
                    dc.append(i)
            if msg == 'exit':
                print('Closing all active sockets...')
                for i in clientDict:
                    address, incSocket = clientDict[i]
                    try: incSocket.shutdown(socket.SHUT_RDWR)
                    except OSError: pass
                    incSocket.close()
                break
            if dc:
                for i in dc:
                    clientDict.pop(i)
                dc.clear()
        elif p in clientDict:
            address, incSocket = clientDict[p]
            try:
                incSocket.send(msgSizeB)
                incSocket.send(msgP)
            except OSError:
                print(address, 'connection error')
                clientDict.pop(p)
        if not clientDict: break

    print("Closing server broadcast thread!")


def startIncoming(incSocket, address, commandQueue, pNo):
    print("Connected to", address)
    connected = True

    while connected:
        # get the header specifying body size
        try:
            msgSizeB = incSocket.recv(HEADERSIZE, socket.MSG_WAITALL)
            msgSize = int.from_bytes(msgSizeB, B_ORDER)
        # get the body
            msgP = incSocket.recv(msgSize, socket.MSG_WAITALL)
        except (OSError, OverflowError):
            print(address, 'connection error')
            break
        try: msg = pickle.loads(msgP)
        except EOFError:
            break
        if msg == 'exit':
            exitP = pickle.dumps(msg)
            exitSizeB = len(msgP).to_bytes(HEADERSIZE, B_ORDER)
            try:
                incSocket.send(exitSizeB)
                incSocket.send(exitP)
            except OSError: pass
            break
        commandQueue.put((pNo, msg))

    incSocket.close()
    print(address, "disconnected from server")


class Server():

    def __init__(self, IP, players):
        self.inQ = Queue()
        self.outQ = Queue(1)

        self.sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listenThread = threading.Thread(target=serverListener,
                                             args=(self.sck, IP, players,
                                                   self.inQ, self.outQ))
        self.listenThread.start()

    def connecting(self):
        return self.listenThread.is_alive()

    def broadcast(self, obj, p=-1):
        if obj is not None:
            self.outQ.put((p, obj))

    def shutdown(self):
        self.broadcast("exit")
        self.sck.close()
        print('Server attempting to shut down.')

    def getMsg(self):
        try:
            msg = self.inQ.get_nowait()
        except queue.Empty:
            return None
        return msg

    def startGame(self):
        pass



