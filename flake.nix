{
  description = "Download a bandcamp artists' discography";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.05";
  inputs.nix2jobs.url = "path:/home/ejg/nix2jobs";

  outputs = { self, nixpkgs }@inputs: let
    name = "bandcamp-artist-dl";
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };

    nix2jobs-lib = inputs.nix2jobs.lib.${system};

    devShell = import ./shell.nix { inherit pkgs; };
    module = import ./module.nix { inherit nix2jobs-lib; };
  in {
    devShells.${system} = {
      ${name} = devShell;
      default = devShell;
    };
    nixosModules.${name} = module;
    nixosModules.default = module; 
  };
}
