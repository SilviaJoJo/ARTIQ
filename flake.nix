{
  description = "A leading-edge control system for quantum information experiments";

  inputs.nixpkgs.url = github:NixOS/nixpkgs/nixos-unstable;
  inputs.rust-overlay = {
      url = "github:oxalica/rust-overlay?ref=snapshot/2024-08-01";
      inputs.nixpkgs.follows = "nixpkgs";
  };
  inputs.sipyco.url = github:m-labs/sipyco;
  inputs.sipyco.inputs.nixpkgs.follows = "nixpkgs";
  inputs.src-pythonparser = { url = github:m-labs/pythonparser; flake = false; };
  inputs.artiq-comtools.url = github:m-labs/artiq-comtools;
  inputs.artiq-comtools.inputs.nixpkgs.follows = "nixpkgs";
  inputs.artiq-comtools.inputs.sipyco.follows = "sipyco";

  inputs.src-migen = { url = github:m-labs/migen; flake = false; };
  inputs.src-misoc = { type = "git"; url = "https://github.com/m-labs/misoc.git"; submodules = true; flake = false; };

  outputs = { self, nixpkgs, rust-overlay, sipyco, src-pythonparser, artiq-comtools, src-migen, src-misoc }:
    let
      pkgs = import nixpkgs { system = "x86_64-linux"; overlays = [ (import rust-overlay) ]; };
      pkgs-aarch64 = import nixpkgs { system = "aarch64-linux"; };

      python = pkgs.python311; # In order to accommodate numba

      artiqVersionMajor = 9;
      artiqVersionMinor = self.sourceInfo.revCount or 0;
      artiqVersionId = self.sourceInfo.shortRev or "unknown";
      artiqVersion = (builtins.toString artiqVersionMajor) + "." + (builtins.toString artiqVersionMinor) + "+" + artiqVersionId + ".beta";
      artiqRev = self.sourceInfo.rev or "unknown";

      rust = pkgs.rust-bin.nightly."2021-09-01".default.override {
        extensions = [ "rust-src" ];
        targets = [ ];
      };
      rustPlatform = pkgs.makeRustPlatform {
        rustc = rust;
        cargo = rust;
      };

      vivadoDeps = pkgs: with pkgs; let
        # Apply patch from https://github.com/nix-community/nix-environments/pull/54
        # to fix ncurses libtinfo.so's soname issue
        ncurses' = ncurses5.overrideAttrs (old: {
          configureFlags = old.configureFlags ++ [ "--with-termlib" ];
          postFixup = "";
        });
      in [
        libxcrypt-legacy
        (ncurses'.override { unicodeSupport = false; })
        zlib
        libuuid
        xorg.libSM
        xorg.libICE
        xorg.libXrender
        xorg.libX11
        xorg.libXext
        xorg.libXtst
        xorg.libXi
        freetype
        fontconfig
      ];

      pythonparser = python.pkgs.buildPythonPackage {
        pname = "pythonparser";
        version = "1.4";
        src = src-pythonparser;
        doCheck = false;
        propagatedBuildInputs = with python.pkgs; [ regex ];
      };

      sipyco-py311 = python.pkgs.buildPythonPackage {
        pname = "sipyco";
        version = "1.8";
        src = sipyco;
        doCheck = false;
      };

      artiq-comtools-py311 = python.pkgs.buildPythonPackage {
        pname = "artiq-comtools";
        version = "1.0";
        src = artiq-comtools;
        propagatedBuildInputs = [ sipyco-py311 ];
        doCheck = false;
      };

      libartiq-support = pkgs.stdenv.mkDerivation {
        name = "libartiq-support";
        src = self;
        buildInputs = [ rust ];
        buildPhase = ''
          rustc $src/artiq/test/libartiq_support/lib.rs -Cpanic=unwind -g
        '';
        installPhase = ''
          mkdir -p $out/lib $out/bin
          cp libartiq_support.so $out/lib
          cat > $out/bin/libartiq-support << EOF
          #!/bin/sh
          echo $out/lib/libartiq_support.so
          EOF
          chmod 755 $out/bin/libartiq-support
        '';
      };


      qasync = python.pkgs.buildPythonPackage rec {
        pname = "qasync";
        version = "0.23.0";  # 使用固定版本
        src = pkgs.fetchFromGitHub {
          owner = "CabbageDevelopment";
          repo = "qasync";
          rev = "v${version}";
          sha256 = "sha256-2wustBtShydCXM5L5IQbOaZ2BfGxbIPwLZ8sRfxFnM4=";
        };
        propagatedBuildInputs = with python.pkgs; [ pyqt6 ];
        doCheck = false;
      };

      artiq-upstream = python.pkgs.buildPythonPackage rec {
        pname = "artiq";
        version = artiqVersion;
        src = self;

        preBuild = ''
          export VERSIONEER_OVERRIDE=${artiqVersion}
          export VERSIONEER_REV=${artiqRev}
        '';

        doCheck = false;

        nativeBuildInputs = [ pkgs.qt6.wrapQtAppsHook ];
        propagatedBuildInputs = [ 
          pkgs.llvm_15 
          pkgs.lld_15 
          sipyco-py311
          pythonparser 
          python.pkgs.llvmlite 
          pkgs.qt6.qtsvg 
          artiq-comtools-py311
          qasync
        ] ++ (with python.pkgs; [ 
          pyqtgraph 
          pygit2 
          numpy 
          dateutil 
          scipy 
          prettytable 
          pyserial 
          levenshtein 
          h5py 
          pyqt6 
          tqdm 
          lmdb 
          jsonschema 
          platformdirs
          numba
          llvmlite
        ]);

        dontWrapQtApps = true;
        postFixup = ''
          wrapQtApp "$out/bin/artiq_dashboard"
          wrapQtApp "$out/bin/artiq_browser"
          wrapQtApp "$out/bin/artiq_session"
        '';

        preFixup = ''
          wrapProgram() { wrapProgramShell "$@"; }
        '';

        makeWrapperArgs = [
          ''--run 'if [ ! -z "$NIX_PYTHONPREFIX" ]; then export PATH=$NIX_PYTHONPREFIX/bin:$PATH;fi' ''
          "--set FONTCONFIG_FILE ${pkgs.fontconfig.out}/etc/fonts/fonts.conf"
        ];

        nativeCheckInputs = with pkgs; [ 
          lld_15 
          llvm_15 
          lit 
          outputcheck 
          cacert 
          python.pkgs.numba 
          python.pkgs.llvmlite
        ] ++ [ libartiq-support ];
        checkPhase = ''
          python -m unittest discover -v artiq.test
          TESTDIR=`mktemp -d`
          cp --no-preserve=mode,ownership -R $src/artiq/test/lit $TESTDIR
          LIBARTIQ_SUPPORT=`libartiq-support` lit -v $TESTDIR/lit
        '';
      };

      artiq = artiq-upstream;

      migen = pkgs.python3Packages.buildPythonPackage rec {
        name = "migen";
        src = src-migen;
        format = "pyproject";
        nativeBuildInputs = [ pkgs.python3Packages.setuptools ];
        propagatedBuildInputs = [ pkgs.python3Packages.colorama ];
      };

      asyncserial = pkgs.python3Packages.buildPythonPackage rec {
        pname = "asyncserial";
        version = "1.0";
        src = pkgs.fetchFromGitHub {
          owner = "m-labs";
          repo = "asyncserial";
          rev = version;
          sha256 = "sha256-ZHzgJnbsDVxVcp09LXq9JZp46+dorgdP8bAiTB59K28=";
        };
        propagatedBuildInputs = [ pkgs.python3Packages.pyserial ];
      };

      misoc = pkgs.python3Packages.buildPythonPackage {
        name = "misoc";
        src = src-misoc;
        propagatedBuildInputs = with pkgs.python3Packages; [ jinja2 numpy migen pyserial asyncserial ];
      };

      microscope = pkgs.python3Packages.buildPythonPackage rec {
        pname = "microscope";
        version = "unstable-2020-12-28";
        src = pkgs.fetchFromGitHub {
          owner = "m-labs";
          repo = "microscope";
          rev = "c21afe7a53258f05bde57e5ebf2e2761f3d495e4";
          sha256 = "sha256-jzyiLRuEf7p8LdhmZvOQj/dyQx8eUE8p6uRlwoiT8vg=";
        };
        propagatedBuildInputs = with pkgs.python3Packages; [ pyserial prettytable msgpack migen ];
      };

      vivadoEnv = pkgs.buildFHSEnv {
        name = "vivado-env";
        targetPkgs = vivadoDeps;
      };

      vivado = pkgs.buildFHSEnv {
        name = "vivado";
        targetPkgs = vivadoDeps;
        profile = "set -e; source /opt/Xilinx/Vivado/2022.2/settings64.sh";
        runScript = "vivado";
      };

      makeArtiqBoardPackage = { target, variant, buildCommand ? "python -m artiq.gateware.targets.${target} -V ${variant}", experimentalFeatures ? [] }:
        pkgs.stdenv.mkDerivation {
          name = "artiq-board-${target}-${variant}";
          phases = [ "buildPhase" "checkPhase" "installPhase" ];
          cargoDeps = rustPlatform.importCargoLock {
            lockFile = ./artiq/firmware/Cargo.lock;
            outputHashes = {
              "fringe-1.2.1" = "sha256-u7NyZBzGrMii79V+Xs4Dx9tCpiby6p8IumkUl7oGBm0=";
              "tar-no-std-0.1.8" = "sha256-xm17108v4smXOqxdLvHl9CxTCJslmeogjm4Y87IXFuM=";
            };
          };
          nativeBuildInputs = [
            (pkgs.python3.withPackages(ps: [ migen misoc (artiq.withExperimentalFeatures experimentalFeatures) ps.packaging ]))
            rust
            pkgs.llvmPackages_15.clang-unwrapped
            pkgs.llvm_15
            pkgs.lld_15
            vivado
            rustPlatform.cargoSetupHook
          ];
          buildPhase =
            ''
            ARTIQ_PATH=`python -c "import artiq; print(artiq.__path__[0])"`
            ln -s $ARTIQ_PATH/firmware/Cargo.lock .
            cargoSetupPostUnpackHook
            cargoSetupPostPatchHook
            ${buildCommand}
            '';
          doCheck = true;
          checkPhase =
            ''
            # Search for PCREs in the Vivado output to check for errors
            check_log() {
              grep -Pe "$1" artiq_${target}/${variant}/gateware/vivado.log && exit 1 || true
            }
            check_log "\d+ constraint not met\."
            check_log "Timing constraints are not met\."
            '';
          installPhase =
            ''
            mkdir $out
            cp artiq_${target}/${variant}/gateware/top.bit $out
            if [ -e artiq_${target}/${variant}/software/bootloader/bootloader.bin ]
            then cp artiq_${target}/${variant}/software/bootloader/bootloader.bin $out
            fi
            if [ -e artiq_${target}/${variant}/software/runtime ]
            then cp artiq_${target}/${variant}/software/runtime/runtime.{elf,fbi} $out
            else cp artiq_${target}/${variant}/software/satman/satman.{elf,fbi} $out
            fi

            mkdir $out/nix-support
            for i in $out/*.*; do
            echo file binary-dist $i >> $out/nix-support/hydra-build-products
            done
            '';
          # don't mangle ELF files as they are not for NixOS
          dontFixup = true;
        };

      openocd-bscanspi-f = pkgs: let
        bscan_spi_bitstreams-pkg = pkgs.stdenv.mkDerivation {
          name = "bscan_spi_bitstreams";
          src = pkgs.fetchFromGitHub {
            owner = "quartiq";
            repo = "bscan_spi_bitstreams";
            rev = "01d8f819f15baf9a8cc5d96945a51e4d267ff564";
            sha256 = "1zqv47kzgvbn4c8cr019a6wcja7gn5h1z4kvw5bhpc72fyhagal9";
          };
          phases = ["installPhase"];
          installPhase =
          ''
          mkdir -p $out/share/bscan-spi-bitstreams
          cp $src/*.bit $out/share/bscan-spi-bitstreams
          '';
        };
      in pkgs.buildEnv {
        name = "openocd-bscanspi";
        paths = [ pkgs.openocd bscan_spi_bitstreams-pkg ];
      };

      latex-artiq-manual = pkgs.texlive.combine {
        inherit (pkgs.texlive)
          scheme-basic latexmk cmap collection-fontsrecommended fncychap
          titlesec tabulary varwidth framed fancyvrb float wrapfig parskip
          upquote capt-of needspace etoolbox booktabs pgf pgfplots;
      };

      artiq-frontend-dev-wrappers = pkgs.runCommandNoCC "artiq-frontend-dev-wrappers" {}
        ''
        mkdir -p $out/bin
        for program in ${self}/artiq/frontend/*.py; do
          if [ -x $program ]; then
            progname=`basename -s .py $program`
            outname=$out/bin/$progname
            echo "#!${pkgs.bash}/bin/bash" >> $outname
            echo "exec python3 -m artiq.frontend.$progname \"\$@\"" >> $outname
            chmod 755 $outname
          fi
        done
        '';

      python-packages = ps: with ps; [
        migen 
        misoc 
        paramiko 
        packaging
        jupyter 
        notebook 
        ipykernel
        jupyterlab
        matplotlib
        numpy
        pandas
        seaborn
        numba
        ps.llvmlite
        pkgconfig
        cython
        six
      ] ++ (
        builtins.filter (p: 
          p.pname != "llvmlite" && 
          p.pname != "numba"
        ) artiq.propagatedBuildInputs
      );

      python-with-packages = python.withPackages python-packages;
    in rec {
      packages.x86_64-linux = {
        inherit pythonparser qasync artiq;
        inherit migen misoc asyncserial microscope vivadoEnv vivado;
        openocd-bscanspi = openocd-bscanspi-f pkgs;
        artiq-board-kc705-nist_clock = makeArtiqBoardPackage {
          target = "kc705";
          variant = "nist_clock";
        };
        artiq-board-efc-shuttler = makeArtiqBoardPackage {
          target = "efc";
          variant = "shuttler";
        };
        inherit latex-artiq-manual;
        artiq-manual-html = pkgs.stdenvNoCC.mkDerivation rec {
          name = "artiq-manual-html-${version}";
          version = artiqVersion;
          src = self;
          buildInputs = with pkgs.python3Packages; [
            sphinx sphinx_rtd_theme sphinxcontrib-tikz
            sphinx-argparse sphinxcontrib-wavedrom
          ] ++ [ latex-artiq-manual artiq-comtools.packages.x86_64-linux.artiq-comtools
            pkgs.pdf2svg
          ];
          buildPhase = ''
            export VERSIONEER_OVERRIDE=${artiqVersion}
            export SOURCE_DATE_EPOCH=${builtins.toString self.sourceInfo.lastModified}
            cd doc/manual
            make html
          '';
          installPhase = ''
            cp -r _build/html $out
            mkdir $out/nix-support
            echo doc manual $out index.html >> $out/nix-support/hydra-build-products
          '';
        };
        artiq-manual-pdf = pkgs.stdenvNoCC.mkDerivation rec {
          name = "artiq-manual-pdf-${version}";
          version = artiqVersion;
          src = self;
          buildInputs = with pkgs.python3Packages; [
            sphinx sphinx_rtd_theme sphinxcontrib-tikz
            sphinx-argparse sphinxcontrib-wavedrom
          ] ++ [ latex-artiq-manual artiq-comtools.packages.x86_64-linux.artiq-comtools
            pkgs.pdf2svg
          ];
          buildPhase = ''
            export VERSIONEER_OVERRIDE=${artiq.version}
            export SOURCE_DATE_EPOCH=${builtins.toString self.sourceInfo.lastModified}
            cd doc/manual
            make latexpdf
          '';
          installPhase = ''
            mkdir $out
            cp _build/latex/ARTIQ.pdf $out
            mkdir $out/nix-support
            echo doc-pdf manual $out ARTIQ.pdf >> $out/nix-support/hydra-build-products
          '';
        };
      };

      inherit makeArtiqBoardPackage openocd-bscanspi-f;

      defaultPackage.x86_64-linux = pkgs.python3.withPackages(ps: [ packages.x86_64-linux.artiq ]);

      # Main development shell with everything you need to develop ARTIQ on Linux.
      # The current copy of the ARTIQ sources is added to PYTHONPATH so changes can be tested instantly.
      # Additionally, executable wrappers that import the current ARTIQ sources for the ARTIQ frontends
      # are added to PATH.
      devShells.x86_64-linux.default = pkgs.mkShell {
        name = "artiq-dev-shell";
        buildInputs = [
          (python.withPackages (ps: [
            ps.h5py
            ps.numpy
            ps.scipy
            ps.pyqt6
            qasync
            ps.pyqtgraph
            ps.prettytable
            ps.levenshtein
            ps.tqdm
            ps.lmdb
            ps.jsonschema
            ps.platformdirs
            ps.numba
            ps.llvmlite
            migen 
            misoc 
            artiq
          ]))
          rust
          pkgs.llvmPackages_15.clang-unwrapped
          pkgs.llvm_15
          pkgs.lld_15
          pkgs.git
          pkgs.hdf5
        ];
        
        shellHook = ''
          export LIBARTIQ_SUPPORT=`libartiq-support`
          export QT_PLUGIN_PATH=${pkgs.qt6.qtbase}/${pkgs.qt6.qtbase.dev.qtPluginPrefix}:${pkgs.qt6.qtsvg}/${pkgs.qt6.qtbase.dev.qtPluginPrefix}
          export QML2_IMPORT_PATH=${pkgs.qt6.qtbase}/${pkgs.qt6.qtbase.dev.qtQmlPrefix}
          
          find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
          find . -name "*.pyc" -delete
          
          echo "Python version:"
          python --version
          python -c "import h5py; print('h5py Version:', h5py.__version__)" || echo "h5py Import Failed"
          python -c "import numba; print('numba Version:', numba.__version__)" || echo "numba Import Failed"
        '';

        PYTHONPATH = "${python-with-packages}/${python-with-packages.sitePackages}";
        LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
          pkgs.hdf5
          pkgs.stdenv.cc.cc.lib
        ];
      };

      # Lighter development shell optimized for building firmware and flashing boards.
      devShells.x86_64-linux.boards = pkgs.mkShell {
        name = "artiq-boards-shell";
        buildInputs = [
          (pkgs.python3.withPackages(ps: with packages.x86_64-linux; [ migen misoc artiq ps.packaging ps.paramiko ]))
          rust
          pkgs.llvmPackages_15.clang-unwrapped
          pkgs.llvm_15
          pkgs.lld_15
          packages.x86_64-linux.vivado
          packages.x86_64-linux.openocd-bscanspi
        ];
      };

      packages.aarch64-linux = {
        openocd-bscanspi = openocd-bscanspi-f pkgs-aarch64;
      };

      hydraJobs = {
        inherit (packages.x86_64-linux) artiq artiq-board-kc705-nist_clock artiq-board-efc-shuttler openocd-bscanspi;
        gateware-sim = pkgs.stdenvNoCC.mkDerivation {
          name = "gateware-sim";
          buildInputs = [
            (pkgs.python3.withPackages(ps: with packages.x86_64-linux; [ migen misoc artiq ]))
          ];
          phases = [ "buildPhase" ];
          buildPhase =
            ''
            python -m unittest discover -v artiq.gateware.test
            touch $out
            '';
        };
        kc705-hitl = pkgs.stdenvNoCC.mkDerivation {
          name = "kc705-hitl";

          __networked = true;  # compatibility with old patched Nix
          # breaks hydra, https://github.com/NixOS/hydra/issues/1216
          #__impure = true;     # Nix 2.8+

          buildInputs = [
            (pkgs.python3.withPackages(ps: with packages.x86_64-linux; [
              artiq
              ps.paramiko
            ] ++ ps.paramiko.optional-dependencies.ed25519
            ))
            pkgs.llvm_15
            pkgs.lld_15
            pkgs.openssh
            packages.x86_64-linux.openocd-bscanspi  # for the bscanspi bitstreams
          ];
          phases = [ "buildPhase" ];
          buildPhase =
            ''
            export HOME=`mktemp -d`
            mkdir $HOME/.ssh
            cp /opt/hydra_id_ed25519 $HOME/.ssh/id_ed25519
            cp /opt/hydra_id_ed25519.pub $HOME/.ssh/id_ed25519.pub
            echo "rpi-1 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIACtBFDVBYoAE4fpJCTANZSE0bcVpTR3uvfNvb80C4i5" > $HOME/.ssh/known_hosts
            chmod 600 $HOME/.ssh/id_ed25519
            LOCKCTL=$(mktemp -d)
            mkfifo $LOCKCTL/lockctl

            cat $LOCKCTL/lockctl | ${pkgs.openssh}/bin/ssh \
              -i $HOME/.ssh/id_ed25519 \
              -o UserKnownHostsFile=$HOME/.ssh/known_hosts \
              rpi-1 \
              'mkdir -p /tmp/board_lock && flock /tmp/board_lock/kc705-1 -c "echo Ok; cat"' \
            | (
              # End remote flock via FIFO
              atexit_unlock() {
                echo > $LOCKCTL/lockctl
              }
              trap atexit_unlock EXIT

              # Read "Ok" line when remote successfully locked
              read LOCK_OK

              artiq_flash -t kc705 -H rpi-1 -d ${packages.x86_64-linux.artiq-board-kc705-nist_clock}
              sleep 30

              export ARTIQ_ROOT=`python -c "import artiq; print(artiq.__path__[0])"`/examples/kc705_nist_clock
              export ARTIQ_LOW_LATENCY=1
              python -m unittest discover -v artiq.test.coredevice
            )

            touch $out
            '';
        };
        inherit (packages.x86_64-linux) artiq-manual-html artiq-manual-pdf;
      };
    };

  nixConfig = {
    extra-trusted-public-keys = "nixbld.m-labs.hk-1:5aSRVA5b320xbNvu30tqxVPXpld73bhtOeH6uAjRyHc=";
    extra-substituters = "https://nixbld.m-labs.hk";
    extra-sandbox-paths = "/opt";
  };
}
