import os
import sys
from typing import Dict
import shutil

import amulet
import amulet_nbt
import numpy
import zstd
from amulet import Block, SelectionGroup, SelectionBox
from amulet.api.block_entity import BlockEntity
from amulet.api.entity import Entity
from amulet.api.chunk import Chunk
from io import BytesIO

from amulet.api.registry import BlockManager, BiomeManager
from amulet.level.formats.anvil_world import AnvilFormat
from amulet.level.interfaces.chunk.anvil.anvil_2844 import Anvil2844Interface
from amulet_nbt import CompoundTag, IntTag, NamedTag

from DataInputStream import DataInputStream

import logging
LOGGER = logging.getLogger(__name__)

ARRAY_SIZE = int(16 * 16 * 16 / (8 / 4))


# IMPORTANT+++++++
# COMMENT or REMOVE LINE 585 IN .venv/lib/python3.12/site-packages/amulet/api/wrapper/format_wrapper.py
# (chunk = self._convert_to_save(chunk, chunk_version, translator, recurse))
# (Data is already "translated", we DONT want it to try to convert it from universal :skull:)

def main():
    for i in range(1, len(sys.argv)):
        # if sys.argv[i].endswith(".slime"):
        complete_convert_world(sys.argv[i])
        # else:
        #     LOGGER.info(f"Argument {i}: {sys.argv[i]} is not a slime world (.slime) Skipping.")
    LOGGER.info("Done.")


def complete_convert_world(world_name: str):
    LOGGER.info(f"Converting world {world_name}")
    if not os.path.exists("slime_worlds"):
        os.mkdir("slime_worlds")
    if not os.path.exists("slime_worlds/" + world_name + ".slime"):
        raise Exception("No slime world found")
    prepare_mc_world(world_name)

    convert_slime_world("slime_worlds/" + world_name + ".slime", world_name)
    zip_world(world_name)
    LOGGER.info("Saved archive of the world in converted_worlds_zips/")


def zip_world(mc_world_name: str):
    shutil.make_archive(mc_world_name, 'zip', mc_world_name)
    if not os.path.exists("converted_worlds_zips"):
        os.mkdir("converted_worlds_zips")
    shutil.move(f"{mc_world_name}.zip", f"converted_worlds_zips/{mc_world_name}.zip")
    shutil.rmtree(mc_world_name)


def prepare_mc_world(mc_world_name: str):
    # Create the world from template/
    if os.path.exists(mc_world_name):
        shutil.rmtree(mc_world_name)
    shutil.copytree("template/", mc_world_name)

    # Change the level name from level.dat
    level = amulet.load_level(mc_world_name)
    level.level_wrapper.level_name = mc_world_name
    level.save()
    level.close()


def convert_slime_world(slime_world_path: str, mc_world_path: str):
    file = open(slime_world_path, "rb", buffering=0)
    stream = DataInputStream(file)

    slime_secret = stream.read_bytes(2)
    if slime_secret != b"\xb1\x0b":
        raise Exception("Not a valid slime file")

    slime_version = stream.read_byte()
    if slime_version != 12:
        raise Exception(f"Unsupported slime version {slime_version}")

    world_version = stream.read_int()
    LOGGER.info(f"World version: {world_version}")
    if world_version != 3839:
        raise Exception(f"Unsupported world version {world_version}")

    level = amulet.load_level(mc_world_path)

    # Read chunks
    chunk_bytes = read_compressed(stream)
    chunk_stream = DataInputStream(BytesIO(chunk_bytes))
    chunk_len = chunk_stream.read_int()
    LOGGER.info(f"Found {chunk_len} chunks.")
    for i in range(chunk_len):
        x = chunk_stream.read_int()
        z = chunk_stream.read_int()
        LOGGER.info(f"Converting Chunk {i+1}/{chunk_len}: x={x}, z={z}")
        chunk = Chunk(x, z)

        # sections_amount = 19 - -4 + 1
        sections_amount = chunk_stream.read_int()

        blocks: Dict[int, numpy.ndarray] = {}
        blocks_palette = [Block(namespace="minecraft", base_name="air")]
        biomes: Dict[int, numpy.ndarray] = {}
        biomes_palette = BiomeManager()
        for sectionId in range(sections_amount):
            block_lights = None
            if chunk_stream.read_boolean():
                block_lights = chunk_stream.read_bytes(ARRAY_SIZE)
            sky_lights = None
            if chunk_stream.read_boolean():
                sky_lights = chunk_stream.read_bytes(ARRAY_SIZE)

        #     block data
            block_state_data = chunk_stream.read_bytes(chunk_stream.read_int())
            block_states_tag = read_compound(block_state_data)

            fake_section_tag = CompoundTag()
            fake_section_tag["block_states"] = block_states_tag
            blocks_data = Anvil2844Interface()._decode_block_section(fake_section_tag)
            if blocks_data is not None:
                arr, section_palette = blocks_data
                blocks[sectionId-4] = arr + len(blocks_palette)
                blocks_palette += section_palette

            #     Biomes
            biomes_data = chunk_stream.read_bytes(chunk_stream.read_int())
            biomes_tag = read_compound(biomes_data)
            fake_section_tag["biomes"] = biomes_tag

            blocks_data = Anvil2844Interface()._decode_biome_section(fake_section_tag)
            if blocks_data is not None:
                arr, section_palette = blocks_data
                lut = numpy.array(
                    [biomes_palette.get_add_biome(biome) for biome in section_palette]
                )
                biomes[sectionId] = lut[arr].astype(numpy.uint32)

        # Blocks math? idkkkkk
        np_palette, inverse = numpy.unique(blocks_palette, return_inverse=True)
        np_palette: numpy.ndarray
        inverse: numpy.ndarray
        inverse = inverse.astype(numpy.uint32)
        for cy in blocks:
            blocks[cy] = inverse[blocks[cy]]
        chunk.blocks = blocks
        chunk.misc["block_palette"] = np_palette
        chunk.block_palette = BlockManager(np_palette)

        # Biomes stuff
        chunk.biomes = biomes
        chunk.biome_palette = biomes_palette

        # Heightmap. unused
        heightmaps = read_compound(chunk_stream.read_bytes(chunk_stream.read_int()))

        # block/tile entities
        tile_entities: list[CompoundTag] = read_compound(chunk_stream.read_bytes(chunk_stream.read_int())).get("tileEntities")
        block_entities_list = []
        for tile_entity in tile_entities:
            block_entities_list.append(BlockEntity("minecraft", tile_entity.get_string("id").py_str[10:], tile_entity.get_int("x").py_int, tile_entity.get_int("y").py_int, tile_entity.get_int("z").py_int, NamedTag(tile_entity)))
        chunk.block_entities = block_entities_list

        # entities
        entities: list[CompoundTag] = read_compound(chunk_stream.read_bytes(chunk_stream.read_int())).get("entities")
        for entity in entities:
            pos = entity.get_list("Pos")
            obj = Entity("minecraft", entity.get_string("id").py_str[10:], float(pos.get_double(0)), float(pos.get_double(1)), float(pos.get_double(2)), NamedTag(entity))
            chunk._native_entities.append(obj)

        # misc/extra data
        extra_data = read_compound(chunk_stream.read_bytes(chunk_stream.read_int()))

        if extra_data is not None:
            chunk.misc = extra_data.py_dict

        chunk.changed = True
        level.put_chunk(chunk, "minecraft:overworld")

    level.save()
    level.close()


def read_compressed(stream: DataInputStream):
    compressed_length = stream.read_int()
    decompressed_length = stream.read_int()
    compressed_data = stream.read_bytes(compressed_length)
    decompressed_data = zstd.decompress(compressed_data)
    return decompressed_data


def read_compound(block_state_data) -> CompoundTag | None:
    if len(block_state_data) == 0:
        return None

    try:
        return amulet_nbt.load(block_state_data, compressed=False, little_endian=False).compound
    except Exception as e:
        print(e)
        pass


if __name__ == "__main__":
    main()
