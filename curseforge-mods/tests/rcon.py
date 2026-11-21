#!/usr/bin/env python3
"""Minimal RCON client. usage: rcon.py PORT 'cmd' ['cmd'...]  (or import Rcon)"""
import socket,struct,sys
class Rcon:
    def __init__(s,port,pw='test',host='127.0.0.1'):
        s.s=socket.create_connection((host,port),timeout=30); s.i=0
        s._send(3,pw); s.s.settimeout(5)
    def _send(s,t,body):
        s.i+=1; b=body.encode()
        p=struct.pack('<ii',s.i,t)+b+b'\0\0'
        s.s.sendall(struct.pack('<i',len(p))+p)
        while True:  # some servers (Forge) send no reply for commands with no output: skip stale ids, time out to ''
            try: hdr=s._rd(4)
            except socket.timeout: return ''
            n=struct.unpack('<i',hdr)[0]; d=s._rd(n)
            if struct.unpack('<i',d[:4])[0]>=s.i: return d[8:-2].decode('utf8','replace')
    def _rd(s,n):
        b=b''
        while len(b)<n:
            c=s.s.recv(n-len(b))
            if not c: raise EOFError
            b+=c
        return b
    def __call__(s,cmd): return s._send(2,cmd)
if __name__=='__main__':
    r=Rcon(int(sys.argv[1]))
    for c in sys.argv[2:]: print('>',c,'\n ',r(c))
