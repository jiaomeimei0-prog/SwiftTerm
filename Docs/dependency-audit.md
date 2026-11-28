# Dependency audit — a-Shell không phải “20 submodule C”

**Updated:** 2026-11-28 (Asia/Saigon)  
**Kết luận:** **2** git submodule + **65** binary SPM targets (+ local port dirs). **Không** có `Podfile`. **Không** có ~20 git submodule kiểu llvm/vim/perl source trees.

## Bằng chứng `.gitmodules`

Path: `Apps/a-Shell/.gitmodules`

```
[submodule "cpython"]
	path = cpython
	url = https://github.com/holzschu/cpython.git
	branch = 3.13
[submodule "SwiftTerm"]
	path = SwiftTerm
	url = https://github.com/jiaomeimei0-prog/SwiftTerm.git
	branch = main
```

Đếm `submodule "` = **2**. Stop condition (>2 submodule) = **không kích hoạt**.

## Bằng chứng `Podfile`

```sh
test -f Apps/a-Shell/Podfile   # → NO_PODFILE (2026-11-28)
```

## Bằng chứng `xcfs/Package.swift`

- Path: `Apps/a-Shell/xcfs/Package.swift`
- `.binaryTarget(` count = **65**
- Thêm: `.package` FMake; target aggregator `build` — **không** tính thêm vào 65 binary
- Nguồn chủ yếu: release GitHub `holzschu/*` (ios_system v3.0.5, llvm-project 14.0.0, texlive-2022, vim, …)

### Danh sách 65 binary (name only)

`libssh2` `openssl` `ios_system` `awk` `curl_ios` `files` `shell` `ssh_cmd` `ssh_cmdA` `ssh_agent` `sshd` `tar` `text` `network_ios` `bc_ios` `lua_ios` `magick` `task` `lex` `calc` `vim` `xxd` `ar` `lld` `llc` `clang` `dis` `libLLVM` `link` `lli` `nm` `opt` `texlua53` `kpathsea` `makeindex` `luatex` `luahbtex` `pdftex` `bibtex` `kpsewhich` `texlua53A` `kpathseaA` `luatexA` `luahbtexA` `pdftexA` `freetype` `harfbuzz` `libpng` `perl` `perlA` `perlB` `lg2` `mandoc` `make` `dash` `dashA` `dashB` `dashC` `dashD` `dashE` `unrar` `vimproc` `ffmpeg` `ffprobe` `jq`

**Số chốt:** **65** (đếm `.binaryTarget(` trong `Package.swift`). Không dùng 67.

## Không phải submodule nhưng dễ nhầm

| Path | Loại |
|------|------|
| `node/`, `fd/`, `fzf/`, `rg/`, `helix/`, `gitoxide/`, `ruff/`, `navi/` | Source/port local — build trên Mac khi cần |
| `downloadFrameworks.sh` → `pythonInstall.tar.gz` | Artifact release — không phải git submodule |
| Nested `SwiftTerm` | Submodule #1 — fork SoT, pin `633a592e` |

## Graph (rút gọn)

```text
jiaomeimei0-prog/SwiftTerm (monorepo)
 └─ Apps/a-Shell @ e95741b8  →  jiaomeimei0-prog/a-shell
       ├─ submodule SwiftTerm @ 633a592e  →  jiaomeimei0-prog/SwiftTerm
       ├─ submodule cpython (holzschu) branch 3.13
       └─ xcfs/Package.swift → 65× binaryTarget (holzschu releases)
```
