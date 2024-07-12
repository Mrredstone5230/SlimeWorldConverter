# Strange slime world to vanilla world converter

This runs on python 3.12 using amulet! It was made on MacOS 14.5, but this should work perfectly fine on WSL.

Install requirements with `pip install -r requirements.txt`

Supports slime worlds v12 and MC worlds v3839(1.20.6) (don't worry, this gets checked)

# IMPORTANT NOTE: YOU MUST EDIT THE AMULET FILES TO MAKE THIS WORK!!!!!
COMMENT or REMOVE LINE 585 IN [.venv/lib/python3.12/site-packages/amulet/api/wrapper/format_wrapper.py](.venv%2Flib%2Fpython3.12%2Fsite-packages%2Famulet%2Fapi%2Fwrapper%2Fformat_wrapper.py)
(chunk = self._convert_to_save(chunk, chunk_version, translator, recurse))

I know this isn't ideal, but it's the only way I could get it to work properly. If you forget to do that, block entities might not save properly, or other strange stuff could happen. I'm sorry.


# Usage
1. Place your world in the `slime_worlds` folder (ending with .slime)
2. Run `python main.py <world_name>` (without the .slime) (you can put multiple world names)
3. Your worlds will be in the 'converted_worlds_zips' as .zip files.
4. Enjoy!

### cool detail
The converter will always copy the contents of the 'template' before converting the world. This is to get a valid level.dat file. If you want to change default settings, like gamerules or dificulties, you can do it by changing that template/level.dat file. (Level names always get translated though.)

