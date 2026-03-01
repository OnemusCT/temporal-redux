import struct
import zlib

_LCG_BASE = 0x19000000   # BASE_SEED (i32)
_LCG_VAL1 = 0x41C64E6D  # multiplier (i32)
_LCG_VAL2 = 12345        # increment  (i32)


def to_i32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def xor_decrypt(data: bytes, block_seed: int) -> bytes:
    """XOR-decrypt a block using the LCG keystream."""
    num1 = to_i32(_LCG_BASE + block_seed)
    out = bytearray(len(data))
    for i, b in enumerate(data):
        num1 = to_i32(num1 * _LCG_VAL1 + _LCG_VAL2)
        out[i] = b ^ ((num1 >> 24) & 0xFF)
    return bytes(out)


def decrypt_then_decompress(data: bytes, block_seed: int) -> bytes:
    """
    Decrypt with LCG then strip the 4-byte big-endian decompressed-length
    prefix and gzip-decompress.
    """
    decrypted = xor_decrypt(data, block_seed)
    decompressed_len = struct.unpack_from('>I', decrypted, 0)[0]
    decompressed = zlib.decompress(decrypted[4:], wbits=47)
    return decompressed[:decompressed_len]
