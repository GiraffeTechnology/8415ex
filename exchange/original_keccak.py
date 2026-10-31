"""Python port of original Wallet src/codec/keccak.ts (Ethereum Keccak, not SHA3).
Used solely to compare the existing child wire commitment; no signing/authority.
"""
MASK=(1<<64)-1
RC=[
  0x0000000000000001, 0x0000000000008082, 0x800000000000808a, 0x8000000080008000,
  0x000000000000808b, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
  0x000000000000008a, 0x0000000000000088, 0x0000000080008009, 0x000000008000000a,
  0x000000008000808b, 0x800000000000008b, 0x8000000000008089, 0x8000000000008003,
  0x8000000000008002, 0x8000000000000080, 0x000000000000800a, 0x800000008000000a,
  0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
ROT=[
  0, 1, 62, 28, 27,
  36, 44, 6, 55, 20,
  3, 10, 43, 25, 39,
  41, 45, 15, 21, 8,
  18, 2, 61, 56, 14,
]
def keccak256(message):
    if type(message) is not bytes: raise ValueError('exact bytes required')
    data=bytearray(((len(message)+1+135)//136)*136)
    data[:len(message)]=message;data[len(message)]=1;data[-1]|=128
    s=[0]*25
    def rol(x,n):return ((x<<n)|(x>>(64-n)))&MASK if n else x
    for off in range(0,len(data),136):
        for lane in range(17):s[lane]^=int.from_bytes(data[off+lane*8:off+lane*8+8],'little')
        for rc in RC:
            c=[s[x]^s[x+5]^s[x+10]^s[x+15]^s[x+20] for x in range(5)]
            d=[c[(x+4)%5]^rol(c[(x+1)%5],1) for x in range(5)]
            for y in range(5):
                for x in range(5):s[x+5*y]^=d[x]
            b=[0]*25
            for y in range(5):
                for x in range(5):b[y+5*((2*x+3*y)%5)]=rol(s[x+5*y],ROT[x+5*y])
            for y in range(5):
                for x in range(5):s[x+5*y]=b[x+5*y]^((~b[(x+1)%5+5*y]&b[(x+2)%5+5*y])&MASK)
            s[0]^=rc
    return '0x'+b''.join(x.to_bytes(8,'little') for x in s[:4]).hex()
