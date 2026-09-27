# Asset Format Reference

Technical notes on the `.xnb` container format and each of the four
asset kinds this tool supports, gathered by reverse-engineering the
game's compiled content files. Useful if you want to extend the tool,
or just want to understand what's actually inside these files.

## The `.xnb` container

Every `.xnb` file (MonoGame/XNA "compiled content") shares the same
outer structure:

| Bytes | Meaning |
|---|---|
| `0..2` | Magic `"XNB"` |
| `3` | Target platform (`'d'` = DesktopGL, `'w'` = Windows, `'x'` = Xbox, ...) |
| `4` | Format version (`5` for the files this tool was built against) |
| `5` | Flags byte — bit `0x80` = LZX compressed, `0x40` = LZ4 compressed |
| `6..9` | Total file size, `uint32` little-endian |
| ... | Type reader table (see below) |
| ... | Shared resource count (7-bit encoded int; `0` for everything this tool has seen) |
| ... | The object itself |

This tool only supports **uncompressed** files (flags byte `0x00`). If
you hit a compressed one, it'll tell you rather than producing garbage.

### The type reader table

Right after the 10-byte header comes a list of "type readers" — the
.NET class names MonoGame will use to deserialize the object that
follows:

```
7-bit-encoded int:  reader count
for each reader:
    7-bit-encoded int:  name length
    UTF-8 string:       fully-qualified .NET type name
    int32 (4 bytes):    reader version (always 0 in practice)
```

**7-bit encoded int** here is .NET's `Read7BitEncodedInt` /
`Write7BitEncodedInt` scheme (also called LEB128-ish): each byte holds
7 bits of the value in its low bits, and the high bit is a
"continue" flag. Most values in these files are small enough to fit in
a single byte.

After the reader table comes the shared-resource count (another 7-bit
int, always `0` here), then the object itself, which starts with a
7-bit-encoded **type ID** — a 1-based index into the reader table
(`0` would mean "null").

## Format 1 — custom QOI images (`BytingPipeline.QoiReader`)

A custom reader, not part of stock MonoGame. The object body is:

```
int32 (4 bytes, little-endian):  byte-array length
raw bytes:                        a standard QOI image file
```

[QOI](https://qoiformat.org/) ("Quite OK Image") is a simple,
losslessly-compressed image format — much smaller and simpler than
PNG. `xnb_asset_tool.py` includes a complete pure-Python QOI
encoder/decoder (`decode_qoi` / `encode_qoi`) so no image library is
needed for the QOI step itself; Pillow is only used to read/write the
`.png` files on the editable side.

Decompiles to / recompiles from a plain `.png`.

## Format 2 — custom glTF models (`BytingPipeline.GLTFReader`)

Also custom. The object body is a **plain UTF-8 JSON string** (a
[glTF](https://www.khronos.org/gltf/) scene document), prefixed with a
.NET `BinaryWriter.Write(string)`-style length:

```
7-bit-encoded int:  UTF-8 byte length of the JSON
UTF-8 bytes:        the glTF JSON document itself
```

Note this is a **different length prefix style** than Format 1 (7-bit
encoded here, vs. a flat `int32` there) — that distinction matters if
you're extending this tool to a new asset type; always check which
convention a given reader actually uses rather than assuming.

Decompiles to / recompiles from a `.gltf` file.

### glTF models reference external files

A glTF `.xnb` only ever contains the **JSON scene/material graph** —
node hierarchy, meshes' accessor/bufferView definitions, materials.
The **actual vertex/index data lives in a separate binary buffer**,
referenced by the JSON's `"buffers"` array as a `"uri"` (e.g.
`"uri": "Car.bin"`), and any textures the materials use are referenced
under `"images"` as their own `"uri"`. Both are **separate `.xnb`
assets** in the game's content — decompile those too (see Format 4 for
the buffer), and make sure the resulting files are named and placed
exactly as the JSON's `uri` fields expect, or the model won't resolve
correctly in a 3D viewer.

### Editing glTF models safely

This game's `GLTFReader` is a minimal, hand-rolled loader — not a
full-spec glTF renderer. A few things that a standards-compliant
viewer would tolerate can break in-game:

- **Custom vertex attributes.** This game uses at least one
  non-standard per-vertex attribute (`_COLOR_SHIFT`, a `FLOAT VEC4`
  used for a paint-palette shader). Generic DCC tools (Blender, etc.)
  don't know what to do with an attribute name they don't recognize,
  and can re-export it as something else entirely (in one observed
  case, a single `_COLOR_SHIFT VEC4` got split into two *standard*
  `COLOR_0` (byte VEC4) / `COLOR_1` (ushort VEC4) attributes on
  re-export). If a mesh's vertex count is unchanged between your
  edited version and the original, you can restore the exact original
  attribute data by copying the accessor bytes across directly —
  vertex *order* is preserved as long as the count matches. If you
  added or removed vertices in a region, there's no 1:1 mapping back
  to the old data for the new vertices; that data has to be
  re-authored.
- **`doubleSided` may be ignored.** Every material in this game's
  models has `"doubleSided": true`, but a minimal custom loader may not
  actually read that flag and could apply a fixed backface-culling /
  winding assumption instead. If normals look inverted in-game despite
  the mesh data itself being internally consistent (winding matches
  the stored normals when checked by hand), suspect a mismatched
  up-axis/handedness convention between your exporter and whatever
  originally produced the asset, rather than the vertex data itself.
- **Don't reuse a "dirty" scene.** Re-importing a model into a DCC
  scene that already has a previous import of the same asset sitting
  in it is a common source of `Name.001`-style duplicate objects on
  export (Blender's collision-renaming behavior). If named nodes act
  as engine-recognized anchor points (as they appear to in this game —
  e.g. `Origin*`, `TailAxis`, `NoseAxis`, `GrindMin*`, `GrindMax*`,
  `Mask#`, matched by exact name rather than scene hierarchy), a stray
  duplicate can make the game pick the wrong instance, which shows up
  as parts of the model being positioned incorrectly. Always start
  from a fresh scene when re-importing a model to edit.

## Format 3 — stock textures (`Texture2DReader`)

Standard MonoGame/XNA, not custom. The object body is:

```
int32:  SurfaceFormat enum value (this tool only supports 0 = Color,
        i.e. uncompressed 8-bit-per-channel RGBA)
int32:  width
int32:  height
int32:  mip level count
for each mip level:
    int32:  data size in bytes
    raw bytes: RGBA pixel data, data_size bytes (width*height*4 for
               the top mip)
```

This tool only reads/writes a **single mip level**; if a source
`.xnb` has more than one, only the top (largest) is exported, and a
warning is printed.

Decompiles to / recompiles from `.tex.png` (see the README for why the
double extension exists).

## Format 4 — raw binary buffers (`ArrayReader<Byte>`)

Also standard MonoGame/XNA — this is what `ArrayReader<T>` /
`ByteReader` compiles to for a plain `byte[]` content item, typically
used here for a glTF model's mesh-geometry buffer. Two readers appear
in the type table (`ArrayReader<Byte>` and `ByteReader`), but only the
first is invoked directly for the top-level object; `ByteReader` isn't
separately referenced in the object body because primitive value-type
array elements don't get individual type-ID markers.

```
int32:  element count (= byte count, since T = byte)
raw bytes: the buffer contents, exactly `count` bytes
```

Decompiles to / recompiles from `.bin`.

### Naming: the `.xnb` is appended, not swapped in

Unlike the other three formats, this game's buffer assets keep their
**complete original filename, including its own extension**, and the
compiled asset name is formed by simply appending `.xnb` onto that
whole name — e.g. a source file called `Car.bin` compiles to
`Car.bin.xnb`, not `Car.xnb`. The tool mirrors this: it strips/appends
*only* the trailing `.xnb`, so `Car.bin.xnb` decompiles straight to
`Car.bin` and recompiles straight back to `Car.bin.xnb`, with no
manual renaming needed at any point.

## Extending this tool to a new asset type

If you find a `.xnb` with a reader this tool doesn't recognize, it'll
print the reader name(s) it found rather than guessing. To add
support:

1. Parse the type reader table (`_read_7bit_int` / the loop in
   `xnb_decompile`) to confirm the exact reader name(s) and order.
2. Figure out the object body's layout — this is genuinely
   trial-and-error: dump the raw bytes right after the type-ID byte
   and compare plausible field values (widths, lengths, magic numbers)
   against what you'd expect. Cross-referencing against MonoGame's
   open-source reader implementations for stock types is the fastest
   path when the reader is a stock one; for custom readers (anything
   not under `Microsoft.Xna.Framework.*`), you're reverse-engineering
   from scratch.
3. Watch for **length-prefix style differences** — this pipeline alone
   uses at least two different conventions (flat `int32` for the QOI
   byte array; 7-bit-encoded int, .NET string-write style, for the
   glTF JSON). Don't assume one applies to a new format without
   checking.
4. Add a decode branch to `xnb_decompile` and a matching `*_to_xnb`
   encode function, following the existing ones as a template, and
   verify round-trips are byte-identical (for deterministic formats)
   or pixel/data-identical (for anything with encoder choices, like
   QOI) against real files before trusting it.
