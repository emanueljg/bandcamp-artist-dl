{ pkgs ? <nixpkgs> {} }:

with pkgs; let

  nixpkgsMaster = (import (fetchFromGitHub {
    owner = "NixOS";
    repo = "nixpkgs";
    rev = "131808261a30a2dd9742098a2a5d864dbc70cfc5";
    sha256 = "sha256-NNxdrVRooAiqMWUwjer+gc2cGfx4buijhtPydPzg4gM=";
  }) { inherit system; });

  inherit (nixpkgsMaster) playwright-driver;

in (poetry2nix.mkPoetryEnv {
  projectDir = ./.;
  python = pkgs.python311;

  overrides =  with python311Packages; poetry2nix.defaultPoetryOverrides.extend (self: super: let

    bandaidBuildInputs = {
      "beautifulsoup4" = [ "setuptools" "hatchling" ];
      "urllib3" = [ "hatchling" ];
      "aioimaplib" = [ ];
      "attrs" = [ "hatchling" "hatch-fancy-pypi-readme" "hatch-vcs" ];
    };

  in builtins.mapAttrs (name: value: 
    super.${name}.overrideAttrs (old: {
      buildInputs = (old.buildInputs or [ ]) 
        ++ builtins.map (pkg: super.${pkg}) value;

      src = if (name == "aioimaplib") then fetchFromGitHub {
        owner = "bamthomas";
        repo = "aioimaplib";
        rev = "master";
        sha256 = "sha256-j6tT9SQZL7vopWItSbNzcsCDtByLT8T7YWKdqjekhDY=";
      } else old.src;
      
    })
  ) bandaidBuildInputs);

  
}).env.overrideAttrs(oldAttrs: {
  buildInputs = [
    poetry
  ];
  shellHook = ''
    LD_LIBRARY_PATH=${stdenv.cc.cc.lib}/lib/
    export PLAYWRIGHT_BROWSERS_PATH=${playwright-driver.browsers}
  '';
})

