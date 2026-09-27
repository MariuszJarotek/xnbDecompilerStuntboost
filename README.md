# XNB Asset Tool

A small Python utility for **decompiling and recompiling MonoGame `.xnb` game assets** between their compiled container format and editable files.

The tool was created by reverse-engineering a specific game's content pipeline and supports four asset types:

| Asset kind | `.xnb` reader                                       | Editable format |
| ---------- | --------------------------------------------------- | --------------- |
| Image      | `BytingPipeline.QoiReader`                          | `.png`          |
| 3D Model   | `BytingPipeline.GLTFReader`                         | `.gltf`         |
| Texture    | `Microsoft.Xna.Framework.Content.Texture2DReader`   | `.tex.png`      |
| Raw Buffer | `Microsoft.Xna.Framework.Content.ArrayReader<Byte>` | `.bin`          |

See [`FORMATS.md`](FORMATS.md) for the technical details of the supported formats and the `.xnb` container structure.

## Requirements

* **Python 3.7+**
* **Pillow** — required only for image conversion

Install Pillow with:

```bash
pip install pillow
```

The `.gltf` and `.bin` formats do not require any additional dependencies.

## Files

```text
xnb_asset_tool.py       # Main converter
xnb_asset_batch.bat     # Windows drag-and-drop wrapper
FORMATS.md              # Technical format documentation
```

---

# Quick Start

## Windows

The easiest way to use the tool is with `xnb_asset_batch.bat`.

Simply **drag and drop one or more files or folders** onto the `.bat` file.

The tool will automatically detect the input format and convert it to the appropriate output format.

For example:

```text
Car.xnb
    ↓
Car.gltf
```

or:

```text
0.png
    ↓
0.xnb
```

The batch file checks that Python and Pillow are installed before running the converter.

## Command Line

You can also run the converter directly:

```bash
python xnb_asset_tool.py <file1> <file2> ... <folder> ...
```

Files and folders can be mixed in the same command.

Examples:

```bash
python xnb_asset_tool.py Car.xnb
```

```bash
python xnb_asset_tool.py Car.xnb Scooter.xnb Board.xnb
```

```bash
python xnb_asset_tool.py extracted_assets/
```

Folders are processed **non-recursively**. Only files directly inside the specified folder are processed.

---

# Decompiling `.xnb` Assets

When given an `.xnb` file, the tool automatically detects the asset type and exports the corresponding editable format.

### 3D Model

```text
Car.xnb
    ↓
Car.gltf
```

### Raw Buffer

```text
Car.bin.xnb
    ↓
Car.bin
```

### Custom QOI Image

```text
0.xnb
    ↓
0.png
```

### MonoGame Texture2D

```text
1Thumbnail.xnb
    ↓
1Thumbnail.tex.png
```

Example:

```bash
python xnb_asset_tool.py Car.xnb 0.xnb 1Thumbnail.xnb
```

Output:

```text
Car.gltf
0.png
1Thumbnail.tex.png
```

---

# Recompiling Assets

Editable files can be converted back into `.xnb` files.

The tool determines which `.xnb` reader to use from the editable file extension.

### 3D Model

```text
Car.gltf
    ↓
Car.xnb
```

### Raw Buffer

```text
Car.bin
    ↓
Car.bin.xnb
```

### Custom QOI Image

```text
0.png
    ↓
0.xnb
```

### MonoGame Texture2D

```text
1Thumbnail.tex.png
    ↓
1Thumbnail.xnb
```

Example:

```bash
python xnb_asset_tool.py Car.gltf Car.bin 0.png 1Thumbnail.tex.png
```

---

# The `.tex.png` Naming Convention

Both custom QOI images and MonoGame `Texture2D` assets are exported as PNG files.

The `.tex.png` suffix is used to distinguish between them.

```text
0.xnb
    ↓
0.png
```

means:

```text
BytingPipeline.QoiReader
```

while:

```text
1Thumbnail.xnb
    ↓
1Thumbnail.tex.png
```

means:

```text
Microsoft.Xna.Framework.Content.Texture2DReader
```

This distinction is important when recompiling.

### Correct

```text
1Thumbnail.tex.png
    ↓
1Thumbnail.xnb
```

### Incorrect

```text
1Thumbnail.png
    ↓
1Thumbnail.xnb
```

If the `.tex` part is removed, the tool will interpret the image as a QOI-based asset and produce an `.xnb` file that the game may not recognize.

**Keep the `.tex.png` suffix intact for stock `Texture2D` assets.**

---

# Files With Dots in Their Names

The tool only removes or adds the **outer `.xnb` extension**.

This means files whose logical names already contain extensions are handled correctly.

For example:

```text
Car.bin.xnb
```

is converted to:

```text
Car.bin
```

and can then be recompiled back to:

```text
Car.bin.xnb
```

No manual renaming is required.

```text
Car.bin.xnb
    ↓ decompile
Car.bin
    ↓ recompile
Car.bin.xnb
```

---

# Working With glTF Models

The `.xnb` containing a `BytingPipeline.GLTFReader` asset only contains the **glTF JSON scene/material data**.

External resources remain separate assets.

For example:

```text
Car.xnb
Car.bin.xnb
Car_Diffuse.xnb
```

may decompile to:

```text
Car.gltf
Car.bin
Car_Diffuse.png
```

The glTF file may contain a reference such as:

```json
{
    "buffers": [
        {
            "uri": "Car.bin"
        }
    ]
}
```

Keep the generated files in the locations expected by the glTF `uri` fields.

For example:

```text
assets/
├── Car.gltf
├── Car.bin
└── Car_Diffuse.png
```

Otherwise, the model may fail to load correctly in Blender or another glTF viewer.

### Custom Vertex Attributes

Some models may contain game-specific vertex attributes, for example:

```text
_COLOR_SHIFT
```

Generic 3D tools such as Blender may rename, split, or remove these attributes when the model is imported and exported again.

If the game relies on custom vertex attributes, check [`FORMATS.md`](FORMATS.md) before modifying and re-exporting the model.

---

# Batch Conversion

Multiple files can be converted in a single command:

```bash
python xnb_asset_tool.py Car.xnb 0.xnb 1Thumbnail.xnb
```

You can also provide a folder:

```bash
python xnb_asset_tool.py extracted_assets/
```

The tool automatically determines the direction of conversion:

```text
.xnb       → editable format
.png       → .xnb
.tex.png   → .xnb
.gltf      → .xnb
.bin       → .xnb
```

Generated files are written **next to the original files** using the same base name.

---

# Limitations

### Compressed `.xnb` Files

Compressed XNB files using **LZX or LZ4** are not supported.

Only uncompressed `.xnb` assets can currently be processed.

The tool will report an error when it encounters an unsupported compressed asset.

### Mipmaps

For stock `Texture2D` assets containing multiple mip levels:

* Only the largest/top mip level is exported.
* Recompiling creates a texture with a single mip level.

Therefore, mipmaps are **not preserved** during a round trip.

### External glTF Resources

glTF external buffers and textures are not bundled into the model `.xnb`.

They must be decompiled separately and kept at the paths referenced by the `.gltf` file.

### Custom Vertex Attributes

Game-specific vertex attributes are not interpreted by the tool.

Editing and exporting a model through third-party software may modify or remove them.

---

# Typical Modding Workflow

A typical workflow looks like this:

### 1. Extract the game's `.xnb` files

Place the files you want to work with in a separate directory.

```text
input/
├── Car.xnb
├── Car.bin.xnb
└── Car_Diffuse.xnb
```

### 2. Decompile them

```bash
python xnb_asset_tool.py input/
```

You may get:

```text
input/
├── Car.xnb
├── Car.gltf
├── Car.bin.xnb
├── Car.bin
├── Car_Diffuse.xnb
└── Car_Diffuse.png
```

### 3. Edit the assets

For example:

* Edit `.png` files in an image editor.
* Edit `.gltf` models in Blender or another compatible tool.
* Modify `.bin` files with a suitable binary editor/tool.

### 4. Recompile

```bash
python xnb_asset_tool.py input/Car.gltf input/Car.bin input/Car_Diffuse.png
```

The tool generates the corresponding `.xnb` files.

### 5. Replace the original assets

Back up the original files before replacing them.

---

# Disclaimer

This tool was created by reverse-engineering asset files from a specific game for personal modding and backup purposes.

It is **not affiliated with or endorsed by the game's developers**.

Use it only with content you have the rights to modify.
