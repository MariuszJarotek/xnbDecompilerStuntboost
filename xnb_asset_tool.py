#!/usr/bin/env python3
"""
xnb_asset_tool.py
=================
One-stop decompile / recompile tool for all of this game's MonoGame
.xnb asset kinds discovered so far:

  - BytingPipeline.QoiReader        image (QOI)          <-> .png
  - BytingPipeline.GLTFReader       3D model (glTF JSON)  <-> .gltf
  - Texture2DReader (stock)         image (raw RGBA)      <-> .tex.png
  - ArrayReader<Byte> (stock)       raw binary buffer     <-> .bin

USAGE
-----
    python xnb_asset_tool.py file1.xnb file2.png file3.gltf some_folder ...

For every path given, the tool auto-detects what kind of file it is and
converts it the other direction, writing the result next to the input
with the same base name:

  - .xnb (QoiReader)         -> .png
  - .xnb (GLTFReader)        -> .gltf
  - .xnb (Texture2DReader)   -> .tex.png   (note the double extension!)
  - .xnb (ArrayReader<Byte>) -> .bin
  - .png                     -> .xnb (QoiReader)
  - .tex.png                 -> .xnb (Texture2DReader)
  - .gltf                    -> .xnb (GLTFReader)
  - .bin                     -> .xnb (ArrayReader<Byte>)
  - a folder                 -> every supported file inside it is processed

Why ".tex.png" and not just ".png" for stock textures?
Two different asset kinds both decode to a plain image (the custom QOI
ones, and the stock MonoGame Texture2D "thumbnail" ones), and the tool
needs to know which .xnb "shape" to rebuild when you hand a .png back
to it. It tags stock-texture PNGs with ".tex.png" so recompiling knows
to use the Texture2DReader format instead of the QOI one. Keep that
suffix intact on any file you intend to recompile as a stock texture -
if it loses the ".tex" part, the tool will just treat it as a QOI image
instead and build a .xnb the game won't recognize for that asset slot.

You can simply drag and drop files/folders onto xnb_asset_batch.bat
(Windows) and it will call this script automatically.

Note on glTF models: a model's .xnb only ever holds the JSON
scene/material graph. The mesh geometry (referenced in the JSON's
"buffers" as a "uri", e.g. "Car.bin") and any textures it points to are
SEPARATE .xnb assets - decompile those too, and keep the resulting
files named/placed exactly as the glTF's "uri" fields expect, or the
model won't load correctly in a 3D viewer.

Requires: Python 3.7+, Pillow  (pip install pillow)
"""

import os
import sys
import struct

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow is required. Install it with:  pip install pillow")
    sys.exit(1)


# ----------------------------------------------------------------------------
# QOI codec  (https://qoiformat.org/qoi-specification.pdf)
# ----------------------------------------------------------------------------

QOI_OP_INDEX = 0x00
QOI_OP_DIFF = 0x40
QOI_OP_LUMA = 0x80
QOI_OP_RUN = 0xc0
QOI_OP_RGB = 0xfe
QOI_OP_RGBA = 0xff


def _hash_idx(r, g, b, a):
    return (r * 3 + g * 5 + b * 7 + a * 11) % 64


def decode_qoi(data):
    """Return (width, height, rgba_bytes) from raw QOI file bytes."""
    if data[0:4] != b'qoif':
        raise ValueError("Not a valid QOI stream (bad magic)")
    width, height = struct.unpack('>II', data[4:12])
    pos = 14

    px_r, px_g, px_b, px_a = 0, 0, 0, 255
    index = [(0, 0, 0, 0)] * 64
    pixels = bytearray()
    n_pixels = width * height
    run = 0
    count = 0

    while count < n_pixels:
        if run > 0:
            run -= 1
        else:
            b0 = data[pos]
            pos += 1
            if b0 == QOI_OP_RGB:
                px_r, px_g, px_b = data[pos], data[pos + 1], data[pos + 2]
                pos += 3
            elif b0 == QOI_OP_RGBA:
                px_r, px_g, px_b, px_a = data[pos], data[pos + 1], data[pos + 2], data[pos + 3]
                pos += 4
            else:
                tag = b0 & 0xc0
                if tag == QOI_OP_INDEX:
                    px_r, px_g, px_b, px_a = index[b0 & 0x3f]
                elif tag == QOI_OP_DIFF:
                    dr = ((b0 >> 4) & 0x03) - 2
                    dg = ((b0 >> 2) & 0x03) - 2
                    db = (b0 & 0x03) - 2
                    px_r = (px_r + dr) & 0xff
                    px_g = (px_g + dg) & 0xff
                    px_b = (px_b + db) & 0xff
                elif tag == QOI_OP_LUMA:
                    b1 = data[pos]
                    pos += 1
                    dg = (b0 & 0x3f) - 32
                    dr_dg = (b1 >> 4) - 8
                    db_dg = (b1 & 0x0f) - 8
                    px_r = (px_r + dg + dr_dg) & 0xff
                    px_g = (px_g + dg) & 0xff
                    px_b = (px_b + dg + db_dg) & 0xff
                elif tag == QOI_OP_RUN:
                    run = b0 & 0x3f
            index[_hash_idx(px_r, px_g, px_b, px_a)] = (px_r, px_g, px_b, px_a)

        pixels += bytes((px_r, px_g, px_b, px_a))
        count += 1

    return width, height, bytes(pixels)


def encode_qoi(width, height, pixels, channels=4, colorspace=0):
    """pixels: RGBA bytes, length width*height*4. Returns raw QOI file bytes."""
    out = bytearray()
    out += b'qoif'
    out += struct.pack('>II', width, height)
    out += bytes((channels, colorspace))

    index = [(0, 0, 0, 0)] * 64
    px_r, px_g, px_b, px_a = 0, 0, 0, 255
    run = 0
    n_pixels = width * height

    for i in range(n_pixels):
        off = i * 4
        r, g, b, a = pixels[off], pixels[off + 1], pixels[off + 2], pixels[off + 3]

        if (r, g, b, a) == (px_r, px_g, px_b, px_a):
            run += 1
            if run == 62:
                out.append(QOI_OP_RUN | (run - 1))
                run = 0
        else:
            if run > 0:
                out.append(QOI_OP_RUN | (run - 1))
                run = 0

            idx = _hash_idx(r, g, b, a)
            if index[idx] == (r, g, b, a):
                out.append(QOI_OP_INDEX | idx)
            else:
                index[idx] = (r, g, b, a)
                if a == px_a:
                    dr = (r - px_r + 128) % 256 - 128
                    dg = (g - px_g + 128) % 256 - 128
                    db = (b - px_b + 128) % 256 - 128
                    dr_dg = dr - dg
                    db_dg = db - dg

                    if -2 <= dr <= 1 and -2 <= dg <= 1 and -2 <= db <= 1:
                        out.append(QOI_OP_DIFF | ((dr + 2) << 4) | ((dg + 2) << 2) | (db + 2))
                    elif -32 <= dg <= 31 and -8 <= dr_dg <= 7 and -8 <= db_dg <= 7:
                        out.append(QOI_OP_LUMA | (dg + 32))
                        out.append(((dr_dg + 8) << 4) | (db_dg + 8))
                    else:
                        out.append(QOI_OP_RGB)
                        out += bytes((r, g, b))
                else:
                    out.append(QOI_OP_RGBA)
                    out += bytes((r, g, b, a))

        px_r, px_g, px_b, px_a = r, g, b, a

    if run > 0:
        out.append(QOI_OP_RUN | (run - 1))

    out += b'\x00' * 7 + b'\x01'
    return bytes(out)


# ----------------------------------------------------------------------------
# XNB container helpers
# ----------------------------------------------------------------------------

QOI_READER_NAME = ("BytingPipeline.QoiReader, BytingPipeline, "
                    "Version=1.0.0.2, Culture=neutral, PublicKeyToken=null")
GLTF_READER_NAME = ("BytingPipeline.GLTFReader, BytingPipeline, "
                     "Version=1.0.0.2, Culture=neutral, PublicKeyToken=null")
TEXTURE2D_READER_NAME = "Microsoft.Xna.Framework.Content.Texture2DReader"
ARRAY_BYTE_READER_NAME = ("Microsoft.Xna.Framework.Content.ArrayReader`1"
                           "[[System.Byte, System.Private.CoreLib, "
                           "Version=8.0.0.0, Culture=neutral, "
                           "PublicKeyToken=7cec85d7bea7798e]]")
BYTE_READER_NAME = "Microsoft.Xna.Framework.Content.ByteReader"


def _read_7bit_int(data, pos):
    result, shift = 0, 0
    while True:
        b = data[pos]
        pos += 1
        result |= (b & 0x7f) << shift
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def _write_7bit_int(value):
    out = bytearray()
    while True:
        b = value & 0x7f
        value >>= 7
        if value:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def _write_xnb(xnb_path, reader_names, type_id, body, platform='d'):
    """reader_names: list of one or more fully-qualified reader type names.
    type_id: 7-bit encoded index (1-based) of the reader used for the
    top-level object (matches how MonoGame writes it)."""
    header = bytearray()
    header += b'XNB'
    header += platform.encode('ascii')
    header += bytes((5,))   # version
    header += bytes((0,))   # flags: uncompressed
    header += b'\x00\x00\x00\x00'  # filesize placeholder, patched below

    header += _write_7bit_int(len(reader_names))
    for name in reader_names:
        header += _write_7bit_int(len(name))
        header += name.encode('utf-8')
        header += struct.pack('<i', 0)  # reader version
    header += _write_7bit_int(0)  # 0 shared resources

    header += _write_7bit_int(type_id)

    out = bytearray(header) + body
    struct.pack_into('<I', out, 6, len(out))

    with open(xnb_path, 'wb') as f:
        f.write(out)


# ----------------------------------------------------------------------------
# Decompile (xnb -> other formats), auto-detected from the reader table
# ----------------------------------------------------------------------------

def xnb_decompile(xnb_path):
    with open(xnb_path, 'rb') as f:
        data = f.read()

    if data[0:3] != b'XNB':
        raise ValueError(f"{xnb_path}: not an XNB file")

    flags = data[5]
    if flags & 0x80 or flags & 0x40:
        raise ValueError(f"{xnb_path}: file is compressed (LZX/LZ4) - "
                          f"this tool only supports uncompressed XNB assets")

    pos = 10
    count, pos = _read_7bit_int(data, pos)
    reader_names = []
    for _ in range(count):
        strlen, pos = _read_7bit_int(data, pos)
        name = data[pos:pos + strlen].decode('utf-8')
        pos += strlen
        pos += 4  # reader version int32
        reader_names.append(name)

    shared_count, pos = _read_7bit_int(data, pos)
    type_id, pos = _read_7bit_int(data, pos)

    base = os.path.splitext(xnb_path)[0]

    if any('QoiReader' in n for n in reader_names):
        length = struct.unpack_from('<I', data, pos)[0]
        pos += 4
        qoi_bytes = data[pos:pos + length]
        width, height, pixels = decode_qoi(qoi_bytes)
        img = Image.frombytes('RGBA', (width, height), pixels)
        png_path = base + '.png'
        img.save(png_path)
        print(f"[decompiled] {xnb_path}  ->  {png_path}  ({width}x{height})")

    elif any('GLTFReader' in n for n in reader_names):
        strlen, pos = _read_7bit_int(data, pos)  # .NET BinaryWriter string prefix
        gltf_bytes = data[pos:pos + strlen]
        gltf_path = base + '.gltf'
        with open(gltf_path, 'wb') as f:
            f.write(gltf_bytes)
        print(f"[decompiled] {xnb_path}  ->  {gltf_path}  (glTF JSON, "
              f"{len(gltf_bytes)} bytes - note: references external "
              f"buffer/texture files not contained in this .xnb)")

    elif any(n == TEXTURE2D_READER_NAME for n in reader_names):
        surface_format, width, height, mip_count = struct.unpack_from('<4i', data, pos)
        pos += 16
        if surface_format != 0:
            raise ValueError(f"{xnb_path}: unsupported SurfaceFormat "
                              f"{surface_format} (only 0 / Color / uncompressed "
                              f"RGBA is supported)")
        if mip_count != 1:
            print(f"WARNING: {xnb_path} has {mip_count} mip levels - "
                  f"only the top-level (largest) mip will be exported")
        data_size = struct.unpack_from('<i', data, pos)[0]
        pos += 4
        pixels = data[pos:pos + data_size]
        img = Image.frombytes('RGBA', (width, height), pixels)
        png_path = base + '.tex.png'
        img.save(png_path)
        print(f"[decompiled] {xnb_path}  ->  {png_path}  ({width}x{height}, "
              f"stock Texture2D)")

    elif any('ArrayReader' in n and 'Byte' in n for n in reader_names):
        count = struct.unpack_from('<i', data, pos)[0]
        pos += 4
        raw = data[pos:pos + count]
        # Buffer assets in this game are typically named "Name.bin.xnb" -
        # i.e. the .xnb is appended onto the complete original filename,
        # which already ends in .bin. Don't double that suffix if it's
        # already there; only append .bin as a fallback if it isn't.
        bin_path = base if base.lower().endswith('.bin') else base + '.bin'
        with open(bin_path, 'wb') as f:
            f.write(raw)
        print(f"[decompiled] {xnb_path}  ->  {bin_path}  ({len(raw)} bytes, "
              f"raw binary buffer)")

    else:
        raise ValueError(f"{xnb_path}: unrecognized content reader(s) "
                          f"{reader_names} - this tool doesn't know this "
                          f"format yet")


# ----------------------------------------------------------------------------
# Compile (other formats -> xnb), dispatched by file extension
# ----------------------------------------------------------------------------

def png_to_xnb(png_path, xnb_path, platform='d'):
    img = Image.open(png_path).convert('RGBA')
    width, height = img.size
    pixels = img.tobytes()

    qoi_bytes = encode_qoi(width, height, pixels)
    body = struct.pack('<I', len(qoi_bytes)) + qoi_bytes
    _write_xnb(xnb_path, [QOI_READER_NAME], 1, body, platform)
    print(f"[compiled]   {png_path}  ->  {xnb_path}  ({width}x{height})")


def gltf_to_xnb(gltf_path, xnb_path, platform='d'):
    with open(gltf_path, 'rb') as f:
        gltf_bytes = f.read()

    body = _write_7bit_int(len(gltf_bytes)) + gltf_bytes
    _write_xnb(xnb_path, [GLTF_READER_NAME], 1, body, platform)
    print(f"[compiled]   {gltf_path}  ->  {xnb_path}  ({len(gltf_bytes)} bytes)")


def texture2d_to_xnb(png_path, xnb_path, platform='d'):
    img = Image.open(png_path).convert('RGBA')
    width, height = img.size
    pixels = img.tobytes()

    body = struct.pack('<4i', 0, width, height, 1)  # format=Color, mipCount=1
    body += struct.pack('<i', len(pixels))
    body += pixels
    _write_xnb(xnb_path, [TEXTURE2D_READER_NAME], 1, body, platform)
    print(f"[compiled]   {png_path}  ->  {xnb_path}  ({width}x{height}, stock Texture2D)")


def bin_to_xnb(bin_path, xnb_path, platform='d'):
    with open(bin_path, 'rb') as f:
        raw = f.read()

    body = struct.pack('<i', len(raw)) + raw
    _write_xnb(xnb_path, [ARRAY_BYTE_READER_NAME, BYTE_READER_NAME], 1, body, platform)
    print(f"[compiled]   {bin_path}  ->  {xnb_path}  ({len(raw)} bytes)")


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def process_path(path):
    if os.path.isdir(path):
        for name in sorted(os.listdir(path)):
            process_path(os.path.join(path, name))
        return

    lower = path.lower()
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == '.xnb':
            xnb_decompile(path)
        elif lower.endswith('.tex.png'):
            out = path[:-len('.tex.png')] + '.xnb'
            texture2d_to_xnb(path, out)
        elif ext == '.png':
            out = os.path.splitext(path)[0] + '.xnb'
            png_to_xnb(path, out)
        elif ext == '.gltf':
            out = os.path.splitext(path)[0] + '.xnb'
            gltf_to_xnb(path, out)
        elif ext == '.bin':
            # Buffer assets are named "Name.bin.xnb" - i.e. .xnb is simply
            # appended onto the full .bin filename, not swapped in for it.
            out = path + '.xnb'
            bin_to_xnb(path, out)
        else:
            print(f"[skipped]    {path} (not .xnb, .png, .tex.png, .gltf, or .bin)")
    except Exception as e:
        print(f"[ERROR]      {path}: {e}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    for arg in sys.argv[1:]:
        process_path(arg)


if __name__ == '__main__':
    main()
