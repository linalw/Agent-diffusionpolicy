// Load opencode-pty's V2 entry point.
//
// The package root is its V1 plugin, which OpenCode 2 refuses to load ("Plugin must
// export a default definition with an id and an effect or setup function"). The V2
// implementation ships at the `./v2` subpath, but the `plugins` config field only
// accepts package names (a spec like `opencode-pty/v2` is treated as a package name
// and fails to install - measured), so this local wrapper re-exports it.
export { default } from "opencode-pty/v2"
