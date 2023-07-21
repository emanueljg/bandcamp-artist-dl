{
  description = "Download a bandcamp artists' discography";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.05";

  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
    devShell = import ./shell.nix { inherit pkgs; };
  in {
    devShells.${system}.default = devShell;
  };
}
