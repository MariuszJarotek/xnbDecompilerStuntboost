# xnbDecompilerStuntboost
XNB Asset Tool

A small Python utility for decompiling and recompiling MonoGame .xnb game assets back and forth between their compiled container format and plain, editable files (PNG images, glTF 3D models, and raw binary buffers).

It was built by reverse-engineering a specific game's content pipeline, and supports four distinct asset kinds — two custom, two stock MonoGame:

Asset kind	.xnb reader	Editable format
Image (custom)	BytingPipeline.QoiReader	.png
3D model (custom)	BytingPipeline.GLTFReader	.gltf
Texture (stock)	Microsoft.Xna.Framework.Content.Texture2DReader	.tex.png
Raw buffer (stock)	Microsoft.Xna.Framework.Content.ArrayReader<Byte>	.bin

See FORMATS.md for the full technical write-up of each format and how the .xnb container itself is structured.

Requirements
Python 3.7 or later
Pillow (pip install pillow) — only needed for the image formats; the glTF and raw-buffer formats have no dependencies.
Files
xnb_asset_tool.py — the converter itself. Works as a command-line tool on any platform.
xnb_asset_batch.bat — a Windows convenience wrapper: drag and drop files onto it instead of using the command line. It checks for Python and Pillow automatically.
Usage
Windows (drag and drop)

Drag one or more files — or a whole folder — onto xnb_asset_batch.bat. A console window will show what was converted and where.

Command line (any platform)
python xnb_asset_tool.py <file1> <file2> ... <folder> ...

Each argument can be a .xnb file, an editable file (.png / .tex.png / .gltf / .bin), or a folder — folders are processed recursively... actually non-recursively, every file directly inside them.

The tool auto-detects what each file is and converts it the other way, writing the result next to the input with the same base name:

Car.xnb          (BytingPipeline.GLTFReader)   ->  Car.gltf
Car.bin.xnb       (ArrayReader<Byte>)           ->  Car.bin
0.xnb             (BytingPipeline.QoiReader)    ->  0.png
1Thumbnail.xnb    (Texture2DReader)             ->  1Thumbnail.tex.png

Car.gltf                                        ->  Car.xnb
Car.bin                                         ->  Car.bin.xnb
0.png                                           ->  0.xnb
1Thumbnail.tex.png                              ->  1Thumbnail.xnb
The .tex.png naming convention

Two of the four asset kinds both decode to a plain image — the custom QOI-based images, and the stock MonoGame Texture2D ones — and the tool needs some way to know which .xnb "shape" to rebuild when you hand a .png back to it. It marks stock-texture images with a double extension, .tex.png, to tell them apart from ordinary .png (QOI) images.

Keep the .tex.png suffix intact on any file you intend to recompile as a stock texture. If it loses the .tex part and becomes plain .png, the tool will treat it as a QOI image instead and build a .xnb the game won't recognize for that asset slot.

Filenames that already contain a dot

Some assets in this pipeline are named with an extension baked into their logical name — e.g. the real, on-disk file is Car.bin.xnb (not Car_bin.xnb). The tool only ever strips/appends the outer .xnb extension, so this round-trips correctly without any manual renaming:

Car.bin.xnb  --[decompile]-->  Car.bin  --[recompile]-->  Car.bin.xnb
What this tool does not do
Compressed .xnb files (LZX/LZ4) are not supported — only uncompressed assets. The tool will tell you if it hits one.
Mipmaps: stock Texture2D assets with more than one mip level will only have their largest (top) mip exported; recompiling always produces a single-mip texture.
glTF external references aren't bundled: a model's .xnb only ever holds the JSON scene/material graph. The mesh geometry buffer (referenced via a "buffers" "uri", e.g. Car.bin) and any textures the model points to are separate .xnb assets — decompile those too, and keep the resulting files named/placed exactly as the glTF's uri fields expect, or the model won't load correctly in a 3D viewer.
Custom vertex attributes (e.g. a game-specific _COLOR_SHIFT paint-shift channel) are not understood by generic 3D editing tools. If you round-trip a .gltf through Blender or similar, custom attributes can be renamed, split, or dropped entirely. See FORMATS.md for how to spot and work around this.
Disclaimer

This tool was built by reverse-engineering asset files from a specific game for personal modding/backup purposes. It is not affiliated with or endorsed by the game's developers. Use it only on content you have the rights to modify.
