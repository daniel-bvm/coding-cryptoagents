# Tailwind CSS Setup

This project uses Tailwind CSS v3.4.10 via the standalone CLI (no Node.js required).

## Files

- `tailwind.config.js` - Tailwind configuration
- `input.css` - Source CSS with Tailwind directives and custom styles
- `public/tailwind.css` - Generated CSS file (do not edit manually)
- `tailwindcss` - Standalone Tailwind CLI binary (v3.4.10)

## Development

To start development with auto-rebuilding CSS:

```bash
./watch-css.sh
```

Or manually:

```bash
./tailwindcss -i ./input.css -o ./public/tailwind.css --watch
```

## Production Build

To build minified CSS for production:

```bash
./build-css.sh
```

Or manually:

```bash
./tailwindcss -i ./input.css -o ./public/tailwind.css --minify
```

## Adding Custom Styles

Add custom CSS to `input.css` after the Tailwind directives. The custom styles will be included in the generated `public/tailwind.css` file.

## Configuration

Modify `tailwind.config.js` to customize Tailwind's configuration, including:
- Content paths (what files to scan for classes)
- Theme extensions (custom colors, animations, etc.)
- Plugins

The current configuration includes custom animations and keyframes that were previously defined inline in the HTML.
