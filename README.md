# Temporal Redux
Temporal Redux is a remake of Michael Springer's Temporal Flux, an editor used to create Chrono Trigger mods. It has been implemented using a significant amount of code from the Jets of Time Chrono Trigger randomizer.

## Installation
1. Create virtual environment:
```bash
python -m venv env
source env/bin/activate  # Unix
env\Scripts\activate     # Windows

pip install .

python -m sourcefiles.temporalredux
```

Requires Python 3.7+ and PyQt6.

## Known Issues
1. Strings can't be edited
1. Sometimes crashes happen when editing the same command twice, or the subcommand menu won't change

In addition to these known issues there has not been extensive testing of the various commands and their menus.

## Credits

### Temporal Flux
The original (as far as I know) Chrono Trigger editor by Michael Springer that the community has been using for decades
to create mods and hacks. Without the work done for Temporal Flux to build upon this project would not exist.

### Jets of Time
Jets of Time is the open world Chrono Trigger randomizer that Temporal Redux is based on.

Online Seed Generator: https://www.ctjot.com  
Discord: https://discord.gg/cKYjHwj  
Wiki: https://wiki.ctjot.com/ 

Most contributions can be seen in the Jets of Time commit history, but special thanks go:
* Mauron, Myself086, and Lagolunatic for general technical assistance; 
* Abyssonym for initial work on Chrono Trigger randomization (Eternal Nightmare, Wings of Time); and 
* Anskiy for originally inventing Jets of Time and developing the initial set of open world event scripts.

### CTViewer

[CTViewer](https://github.com/GitExl/CTViewer) is a project by GitExl that is a utility to display Chrono Trigger scene 
and world maps complete with debug information. This is the project that inspired me to update Temporal Redux to handle
both SNES and PC events and it's code was the basis from which I developed the PC reading code.