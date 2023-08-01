{ lib, pkgs, config, ...}: with lib; with types; let
  cfg = config.services.bandcamp-artist-dl;
  inherit (import ./utils.nix)
    mkNullOption
    mkParamOption
    mkVerbosityOption
  ;
in {
  options.services.bandcamp-artist-dl = let
    workerOpts = [ "default" "pageParser" "download" "unzip" ];
    dirNames = [ "download" "unzip" ];
    jobOptions = {
      email = mkOption {
        type = submodule {
          options = {
            address = mkParamOption 2 {
              type = str;
            };
            passwordFile = mkParamOption 3 {
              type = path;
            };
            user = mkParamOption "--override-email-user" {
              type = str;
            };
            host = mkParamOption "--override-email-host" {
              type = str;
            };
          };
        };
        description = ''
          Authentication details for email.
        '';
        example = literalExpression ''
          { 
            address = "johndoe@example.com"; 
            passwordFile = /run/secrets/mailpass;
            # elegant sops-nix solution
            passwordFile = config.sops.secrets.mailpass.path;
          }
        '';
      };
      dirs = mkNullOption {
        type = submodule {
          options = attrsets.genAttrs dirNames (name: mkParamOption "${name}-dir" {
            type = str;
          });
        };
      };        
      maxWorkers = mkNullOption {
        type = submodule {
          options = attrsets.genAttrs workerOpts (name: let
            param = 
              if (name == "default") then 
                "--max-workers" 
              else
                "--max-${name}-workers";
          in mkParamOption param {
            type = ints.positive;
          });
        };
      };
      format = mkParamOption "--format" {
        type = enum [ "flac" ];
      };
      mailbox = mkParamOption "--mailbox" {
        type = str;
      };
      verbosity = mkVerbosityOption;
    };
  in {
    enable = mkEnableOption "Bandcamp artist downloader";

    jobDefaults = mkOption {
      type = attrsOf (submodule {
        options = jobOptions;
      });
      default = { };
    };
    
    jobs = mkOption {
      type = listOf (either str (submodule {
        options = jobOptions // {
          artist = mkParamOption 1 {
            type = str;
            description = ''
              The artist to download from.
            '';
          };
        };
      }));
      default = [ ];
      apply = value: 
        if builtins.isString value then { artist = value; } else value;
    };

  };

  config = mkIf cfg.enable {
    environment.systemPackages = [
      
    x = with strings; let
      mkJob = job: let
        job = "haircutsformen";
      
        getJobOpt = opt: foldor [ job.${opt} cfg.jobDefaults.${opt} ];

        addFlag = flag: opt: let
          value = resolveJobOpt job opt;
          valString = optionalString (!(builtins.isBool value)) " ${value}";
        in 
          or' "--${flag}${valString}" null;

        args = [
          job.artist
          (getJobOpt "email.address")
          (getJobOpt "email.passwordFile")
        ];
        flags = [
          (addFlag "download-dir" "dirs.download")
          (addFlag "unzip-dir" "dirs.unzip")
          (addFlag "format" "format")
          (addFlag "max-workers" "workers.default")
          (addFlag "max-page-parser-workers" "workers.pageParser")
          (addFlag "max-download-workers" "workers.download")
          (addFlag "max-unzip-workers" "workers.unzip")
          (addFlag "override-email-host" "email.host")
          (addFlag "override-email-user" "email.user")
          (addFlag "mailbox" "mailbox")
        ] ++ [
          (if ((getJobOpt "verbose") == 1) then "-v" else
           if ((getJobOpt "verbose") == 2) then "-vv" else 
           null
          )
        ];
        cmdLines = [ "bandcamp-artist-dl" ] ++ args ++ flags;
      
      in concatStringsSep '' \\n  '' (builtins.filter (flag != null) flags);
  };
}