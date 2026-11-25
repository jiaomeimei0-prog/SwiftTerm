# Apps

Host applications and samples that consume SwiftTerm.

## a-Shell (`Apps/a-Shell`)

Git submodule: https://github.com/jiaomeimei0-prog/a-shell  
Pinned to that fork’s branch that retargets the Xcode local package to this monorepo.

a-Shell is an iOS terminal. It no longer vendors a nested SwiftTerm git submodule. The Xcode project resolves SwiftTerm at `../SwiftTerm` relative to `Apps/a-Shell` — in this monorepo that is the `Apps/SwiftTerm` symlink to the parent package root.

### Init

```sh
git submodule update --init Apps/a-Shell
# Optional — only if you need a-Shell’s nested cpython pin:
# cd Apps/a-Shell && git submodule update --init cpython
```

Build instructions remain those of a-Shell (prefer the `a-Shell-noPython` scheme). See `Apps/a-Shell/README.md`.

### Layout

```text
SwiftTerm/                 ← Package.swift (this repo)
├── Apps/
│   ├── SwiftTerm -> ..    ← local package path for a-Shell.xcodeproj
│   └── a-Shell/           ← submodule (jiaomeimei0-prog/a-shell)
│       └── a-Shell.xcodeproj  (relativePath = ../SwiftTerm)
└── Sources/SwiftTerm/
```
