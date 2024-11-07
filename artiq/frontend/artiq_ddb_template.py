#!/usr/bin/env python3

import argparse
import sys
import textwrap
from collections import defaultdict
from itertools import count, filterfalse

from artiq import __version__ as artiq_version
from artiq.coredevice import jsondesc
from artiq.coredevice.phaser import PHASER_GW_MIQRO, PHASER_GW_BASE


def get_cpu_target(description):
    if description.get("type", None) == "shuttler":
        return "rv32g"
    if description["target"] == "kasli":
        if description["hw_rev"] in ("v1.0", "v1.1"):
            return "rv32ima"
        else:
            return "rv32g"
    elif description["target"] == "kasli_soc":
        return "cortexa9"
    else:
        raise NotImplementedError


def get_num_leds(description):
    drtio_role = description["drtio_role"]
    target = description["target"]
    hw_rev = description["hw_rev"]
    kasli_board_leds = {
        "v1.0": 4,
        "v1.1": 6,
        "v2.0": 3
    }
    if target == "kasli":
        if hw_rev in ("v1.0", "v1.1") and drtio_role != "standalone":
            # LEDs are used for DRTIO status on v1.0 and v1.1
            return kasli_board_leds[hw_rev] - 3
        return kasli_board_leds[hw_rev]
    elif target == "kasli_soc":
        return 2
    else:
        raise ValueError
     

def process_header(output, description):
    print(textwrap.dedent("""
        # Autogenerated for the {variant} variant
        core_addr = "{core_addr}"

        device_db = {{
            "core": {{
                "type": "local",
                "module": "artiq.coredevice.core",
                "class": "Core",
                "arguments": {{
                    "host": core_addr,
                    "ref_period": {ref_period},
                    "analyzer_proxy": "core_analyzer",
                    "target": "{cpu_target}",
                    "satellite_cpu_targets": {{}}
                }},
            }},
            "core_log": {{
                "type": "controller",
                "host": "::1",
                "port": 1068,
                "command": "aqctl_corelog -p {{port}} --bind {{bind}} " + core_addr
            }},
            "core_moninj": {{
                "type": "controller",
                "host": "::1",
                "port_proxy": 1383,
                "port": 1384,
                "command": "aqctl_moninj_proxy --port-proxy {{port_proxy}} --port-control {{port}} --bind {{bind}} " + core_addr
            }},
            "core_analyzer": {{
                "type": "controller",
                "host": "::1",
                "port_proxy": 1385,
                "port": 1386,
                "command": "aqctl_coreanalyzer_proxy --port-proxy {{port_proxy}} --port-control {{port}} --bind {{bind}} " + core_addr
            }},
            "core_cache": {{
                "type": "local",
                "module": "artiq.coredevice.cache",
                "class": "CoreCache"
            }},
            "core_dma": {{
                "type": "local",
                "module": "artiq.coredevice.dma",
                "class": "CoreDMA"
            }},

            "i2c_switch0": {{
                "type": "local",
                "module": "artiq.coredevice.i2c",
                "class": "I2CSwitch",
                "arguments": {{"address": 0xe0}}
            }},
            "i2c_switch1": {{
                "type": "local",
                "module": "artiq.coredevice.i2c",
                "class": "I2CSwitch",
                "arguments": {{"address": 0xe2}}
            }},
        }}
        """).format(
            variant=description["variant"],
            core_addr=description["core_addr"],
            ref_period=1/(8*description["rtio_frequency"]),
            cpu_target=get_cpu_target(description)),
        file=output)


class PeripheralManager:
    def __init__(self, output, primary_description):
        self.counts = defaultdict(int)
        self.output = output
        self.primary_description = primary_description

    def get_name(self, ty):
        count = self.counts[ty]
        self.counts[ty] = count + 1
        return "{}{}".format(ty, count)

    def gen(self, string, **kwargs):
        print(textwrap.dedent(string).format(**kwargs), file=self.output)

    def process_dio(self, rtio_offset, peripheral, num_channels=8):
        class_names = {
            "input": "TTLInOut",
            "output": "TTLOut",
            "clkgen": "TTLClockGen"
        }
        classes = [
            class_names[peripheral["bank_direction_low"]],
            class_names[peripheral["bank_direction_high"]]
        ]
        channel = count(0)
        name = [self.get_name("ttl") for _ in range(num_channels)]
        for i in range(num_channels):
            self.gen("""
                device_db["{name}"] = {{
                    "type": "local",
                    "module": "artiq.coredevice.ttl",
                    "class": "{class_name}",
                    "arguments": {{"channel": 0x{channel:06x}}},
                }}""",
                     name=name[i],
                     class_name=classes[i // 4],
                     channel=rtio_offset + next(channel))
        if peripheral["edge_counter"]:
            for i in range(num_channels):
                class_name = classes[i // 4]
                if class_name == "TTLInOut":
                    self.gen("""
                        device_db["{name}_counter"] = {{
                            "type": "local",
                            "module": "artiq.coredevice.edge_counter",
                            "class": "EdgeCounter",
                            "arguments": {{"channel": 0x{channel:06x}}},
                        }}""",
                             name=name[i],
                             channel=rtio_offset + next(channel))
        return next(channel)

    def process_dio_spi(self, rtio_offset, peripheral):
        channel = count(0)
        for spi in peripheral["spi"]:
            self.gen("""
                        device_db["{name}"] = {{
                            "type": "local",
                            "module": "artiq.coredevice.spi2",
                            "class": "SPIMaster",
                            "arguments": {{"channel": 0x{channel:06x}}}
                        }}""",
                     name=self.get_name(spi["name"]),
                     channel=rtio_offset + next(channel))
        for ttl in peripheral["ttl"]:
            ttl_class_names = {
                "input": "TTLInOut",
                "output": "TTLOut"
            }
            name = self.get_name(ttl["name"])
            self.gen("""
                device_db["{name}"] = {{
                    "type": "local",
                    "module": "artiq.coredevice.ttl",
                    "class": "{class_name}",
                    "arguments": {{"channel": 0x{channel:06x}}},
                }}""",
                     name=name,
                     class_name=ttl_class_names[ttl["direction"]],
                     channel=rtio_offset + next(channel))
            if ttl["edge_counter"]:
                self.gen("""
                    device_db["{name}_counter"] = {{
                        "type": "local",
                        "module": "artiq.coredevice.edge_counter",
                        "class": "EdgeCounter",
                        "arguments": {{"channel": 0x{channel:06x}}},
                    }}""",
                         name=name,
                         channel=rtio_offset + next(channel))
        return next(channel)

    def process_urukul(self, rtio_offset, peripheral):
        urukul_name = self.get_name("urukul")
        synchronization = peripheral["synchronization"]
        channel = count(0)
        pll_en = peripheral["pll_en"]
        clk_div = peripheral.get("clk_div")
        if clk_div is None:
            clk_div = 0 if pll_en else 1

        self.gen("""
            device_db["eeprom_{name}"] = {{
                "type": "local",
                "module": "artiq.coredevice.kasli_i2c",
                "class": "KasliEEPROM",
                "arguments": {{"port": "EEM{eem}"}}
            }}

            device_db["spi_{name}"] = {{
                "type": "local",
                "module": "artiq.coredevice.spi2",
                "class": "SPIMaster",
                "arguments": {{"channel": 0x{channel:06x}}}
            }}""",
            name=urukul_name,
            eem=peripheral["ports"][0],
            channel=rtio_offset+next(channel))
        if synchronization:
            self.gen("""
                device_db["ttl_{name}_sync"] = {{
                    "type": "local",
                    "module": "artiq.coredevice.ttl",
                    "class": "TTLClockGen",
                    "arguments": {{"channel": 0x{channel:06x}, "acc_width": 4}}
                }}""",
                name=urukul_name,
                channel=rtio_offset+next(channel))
        self.gen("""
            device_db["ttl_{name}_io_update"] = {{
                "type": "local",
                "module": "artiq.coredevice.ttl",
                "class": "TTLOut",
                "arguments": {{"channel": 0x{channel:06x}}}
            }}""",
            name=urukul_name,
            channel=rtio_offset+next(channel))
        if len(peripheral["ports"]) > 1:
            for i in range(4):
                self.gen("""
                    device_db["ttl_{name}_sw{uchn}"] = {{
                        "type": "local",
                        "module": "artiq.coredevice.ttl",
                        "class": "TTLOut",
                        "arguments": {{"channel": 0x{channel:06x}}}
                    }}""",
                    name=urukul_name,
                    uchn=i,
                    channel=rtio_offset+next(channel))
        self.gen("""
            device_db["{name}_cpld"] = {{
                "type": "local",
                "module": "artiq.coredevice.urukul",
                "class": "CPLD",
                "arguments": {{
                    "spi_device": "spi_{name}",
                    "sync_device": {sync_device},
                    "io_update_device": "ttl_{name}_io_update",
                    "refclk": {refclk},
                    "clk_sel": {clk_sel},
                    "clk_div": {clk_div}
                }}
            }}""",
            name=urukul_name,
            sync_device="\"ttl_{name}_sync\"".format(name=urukul_name) if synchronization else "None",
            refclk=peripheral.get("refclk", self.primary_description["rtio_frequency"]),
            clk_sel=peripheral["clk_sel"],
            clk_div=clk_div)
        dds = peripheral["dds"]
        pll_vco = peripheral.get("pll_vco")
        for i in range(4):
            if dds == "ad9910":
                self.gen("""
                    device_db["{name}_ch{uchn}"] = {{
                        "type": "local",
                        "module": "artiq.coredevice.ad9910",
                        "class": "AD9910",
                        "arguments": {{
                            "pll_n": {pll_n},
                            "pll_en": {pll_en},
                            "chip_select": {chip_select},
                            "cpld_device": "{name}_cpld"{sw}{pll_vco}{sync_delay_seed}{io_update_delay}
                        }}
                    }}""",
                    name=urukul_name,
                    chip_select=4 + i,
                    uchn=i,
                    sw=",\n        \"sw_device\": \"ttl_{name}_sw{uchn}\"".format(name=urukul_name, uchn=i) if len(peripheral["ports"]) > 1 else "",
                    pll_vco=",\n        \"pll_vco\": {}".format(pll_vco) if pll_vco is not None else "",
                    pll_n=peripheral.get("pll_n", 32), pll_en=pll_en,
                    sync_delay_seed=",\n        \"sync_delay_seed\": \"eeprom_{}:{}\"".format(urukul_name, 64 + 4*i) if synchronization else "",
                    io_update_delay=",\n        \"io_update_delay\": \"eeprom_{}:{}\"".format(urukul_name, 64 + 4*i) if synchronization else "")
            elif dds == "ad9912":
                self.gen("""
                    device_db["{name}_ch{uchn}"] = {{
                        "type": "local",
                        "module": "artiq.coredevice.ad9912",
                        "class": "AD9912",
                        "arguments": {{
                            "pll_n": {pll_n},
                            "pll_en": {pll_en},
                            "chip_select": {chip_select},
                            "cpld_device": "{name}_cpld"{sw}{pll_vco}
                        }}
                    }}""",
                    name=urukul_name,
                    chip_select=4 + i,
                    uchn=i,
                    sw=",\n        \"sw_device\": \"ttl_{name}_sw{uchn}\"".format(name=urukul_name, uchn=i) if len(peripheral["ports"]) > 1 else "",
                    pll_vco=",\n        \"pll_vco\": {}".format(pll_vco) if pll_vco is not None else "",
                    pll_n=peripheral.get("pll_n", 8), pll_en=pll_en)
            else:
                raise ValueError
        return next(channel)

    def process_mirny(self, rtio_offset, peripheral):
        legacy_almazny = ("v1.0", "v1.1")
        mirny_name = self.get_name("mirny")
        channel = count(0)
        self.gen("""
           device_db["spi_{name}"]={{
               "type": "local",
               "module": "artiq.coredevice.spi2",
               "class": "SPIMaster",
               "arguments": {{"channel": 0x{channel:06x}}}
           }}""",
            name=mirny_name,
            channel=rtio_offset+next(channel))

        for i in range(4):
            self.gen("""
                device_db["ttl_{name}_sw{mchn}"] = {{
                    "type": "local",
                    "module": "artiq.coredevice.ttl",
                    "class": "TTLOut",
                    "arguments": {{"channel": 0x{ttl_channel:06x}}}
                }}""",
                name=mirny_name,
                mchn=i,
                ttl_channel=rtio_offset+next(channel))

        for i in range(4):
            self.gen("""
                device_db["{name}_ch{mchn}"] = {{
                    "type": "local",
                    "module": "artiq.coredevice.adf5356",
                    "class": "ADF5356",
                    "arguments": {{
                        "channel": {mchn},
                        "sw_device": "ttl_{name}_sw{mchn}",
                        "cpld_device": "{name}_cpld",
                    }}
                }}""",
                name=mirny_name,
                mchn=i)

            if peripheral["almazny"] and peripheral["almazny_hw_rev"] not in legacy_almazny:
                self.gen("""
                    device_db["{name}_almazny{i}"] = {{
                        "type": "local",
                        "module": "artiq.coredevice.almazny",
                        "class": "AlmaznyChannel",
                        "arguments": {{
                            "host_mirny": "{name}_cpld",
                            "channel": {i},
                        }},
                    }}""",
                    name=mirny_name,
                    i=i)

        clk_sel = peripheral["clk_sel"]
        if isinstance(peripheral["clk_sel"], str):
            clk_sel = '"' + peripheral["clk_sel"] + '"'
        self.gen("""
            device_db["{name}_cpld"] = {{
                "type": "local",
                "module": "artiq.coredevice.mirny",
                "class": "Mirny",
                "arguments": {{
                    "spi_device": "spi_{name}",
                    "refclk": {refclk},
                    "clk_sel": {clk_sel}
                }},
            }}""",
            name=mirny_name,
            refclk=peripheral["refclk"],
            clk_sel=clk_sel)
        if peripheral["almazny"] and peripheral["almazny_hw_rev"] in legacy_almazny:
            self.gen("""
            device_db["{name}_almazny"] = {{
                "type": "local",
                "module": "artiq.coredevice.almazny",
                "class": "AlmaznyLegacy",
                "arguments": {{
                    "host_mirny": "{name}_cpld",
                }},
            }}""",
            name=mirny_name)

        return next(channel)

    def process_novogorny(self, rtio_offset, peripheral):
        self.gen("""
            device_db["spi_{name}_adc"] = {{
                "type": "local",
                "module": "artiq.coredevice.spi2",
                "class": "SPIMaster",
                "arguments": {{"channel": 0x{adc_channel:06x}}}
            }}
            device_db["ttl_{name}_cnv"] = {{
                "type": "local",
                "module": "artiq.coredevice.ttl",
                "class": "TTLOut",
                "arguments": {{"channel": 0x{cnv_channel:06x}}},
            }}
            device_db["{name}"] = {{
                "type": "local",
                "module": "artiq.coredevice.novogorny",
                "class": "Novogorny",
                "arguments": {{
                    "spi_adc_device": "spi_{name}_adc",
                    "cnv_device": "ttl_{name}_cnv"
                }}
            }}""",
            name=self.get_name("novogorny"),
            adc_channel=rtio_offset,
            cnv_channel=rtio_offset + 1)
        return 2

    def process_sampler(self, rtio_offset, peripheral):
        self.gen("""
            device_db["spi_{name}_adc"] = {{
                "type": "local",
                "module": "artiq.coredevice.spi2",
                "class": "SPIMaster",
                "arguments": {{"channel": 0x{adc_channel:06x}}}
            }}
            device_db["spi_{name}_pgia"] = {{
                "type": "local",
                "module": "artiq.coredevice.spi2",
                "class": "SPIMaster",
                "arguments": {{"channel": 0x{pgia_channel:06x}}}
            }}
            device_db["ttl_{name}_cnv"] = {{
                "type": "local",
                "module": "artiq.coredevice.ttl",
                "class": "TTLOut",
                "arguments": {{"channel": 0x{cnv_channel:06x}}},
            }}
            device_db["{name}"] = {{
                "type": "local",
                "module": "artiq.coredevice.sampler",
                "class": "Sampler",
                "arguments": {{
                    "spi_adc_device": "spi_{name}_adc",
                    "spi_pgia_device": "spi_{name}_pgia",
                    "cnv_device": "ttl_{name}_cnv",
                    "hw_rev": "{hw_rev}"
                }}
            }}""",
            name=self.get_name("sampler"),
            hw_rev=peripheral.get("hw_rev", "v2.2"),
            adc_channel=rtio_offset,
            pgia_channel=rtio_offset + 1,
            cnv_channel=rtio_offset + 2)
        return 3

    def process_suservo(self, rtio_offset, peripheral):
        suservo_name = self.get_name("suservo")
        sampler_name = self.get_name("sampler")
        urukul_names = [self.get_name("urukul") for _ in range(2)]
        channel = count(0)
        for i in range(8):
            self.gen("""
                device_db["{suservo_name}_ch{suservo_chn}"] = {{
                    "type": "local",
                    "module": "artiq.coredevice.suservo",
                    "class": "Channel",
                    "arguments": {{"channel": 0x{suservo_channel:06x}, "servo_device": "{suservo_name}"}}
                }}""",
                suservo_name=suservo_name,
                suservo_chn=i,
                suservo_channel=rtio_offset+next(channel))
        self.gen("""
            device_db["{suservo_name}"] = {{
                "type": "local",
                "module": "artiq.coredevice.suservo",
                "class": "SUServo",
                "arguments": {{
                    "channel": 0x{suservo_channel:06x},
                    "pgia_device": "spi_{sampler_name}_pgia",
                    "cpld_devices": {cpld_names_list},
                    "dds_devices": {dds_names_list},
                    "sampler_hw_rev": "{sampler_hw_rev}"
                }}
            }}""",
            suservo_name=suservo_name,
            sampler_name=sampler_name,
            sampler_hw_rev=peripheral["sampler_hw_rev"],
            cpld_names_list=[urukul_name + "_cpld" for urukul_name in urukul_names],
            dds_names_list=[urukul_name + "_dds" for urukul_name in urukul_names],
            suservo_channel=rtio_offset+next(channel))
        self.gen("""
            device_db["spi_{sampler_name}_pgia"] = {{
                "type": "local",
                "module": "artiq.coredevice.spi2",
                "class": "SPIMaster",
                "arguments": {{"channel": 0x{sampler_channel:06x}}}
            }}""",
            sampler_name=sampler_name,
            sampler_channel=rtio_offset+next(channel))
        pll_vco = peripheral.get("pll_vco")
        for urukul_name in urukul_names:
            self.gen("""
                device_db["spi_{urukul_name}"] = {{
                    "type": "local",
                    "module": "artiq.coredevice.spi2",
                    "class": "SPIMaster",
                    "arguments": {{"channel": 0x{urukul_channel:06x}}}
                }}
                device_db["{urukul_name}_cpld"] = {{
                    "type": "local",
                    "module": "artiq.coredevice.urukul",
                    "class": "CPLD",
                    "arguments": {{
                        "spi_device": "spi_{urukul_name}",
                        "refclk": {refclk},
                        "clk_sel": {clk_sel}
                    }}
                }}
                device_db["{urukul_name}_dds"] = {{
                    "type": "local",
                    "module": "artiq.coredevice.ad9910",
                    "class": "AD9910",
                    "arguments": {{
                        "pll_n": {pll_n},
                        "pll_en": {pll_en},
                        "chip_select": 3,
                        "cpld_device": "{urukul_name}_cpld"{pll_vco}
                    }}
                }}""",
                urukul_name=urukul_name,
                urukul_channel=rtio_offset+next(channel),
                refclk=peripheral.get("refclk", self.primary_description["rtio_frequency"]),
                clk_sel=peripheral["clk_sel"],
                pll_vco=",\n        \"pll_vco\": {}".format(pll_vco) if pll_vco is not None else "",
                pll_n=peripheral["pll_n"],  pll_en=peripheral["pll_en"])
        return next(channel)

    def process_zotino(self, rtio_offset, peripheral):
        self.gen("""
            device_db["spi_{name}"] = {{
                "type": "local",
                "module": "artiq.coredevice.spi2",
                "class": "SPIMaster",
                "arguments": {{"channel": 0x{spi_channel:06x}}}
            }}
            device_db["ttl_{name}_ldac"] = {{
                "type": "local",
                "module": "artiq.coredevice.ttl",
                "class": "TTLOut",
                "arguments": {{"channel": 0x{ldac_channel:06x}}}
            }}
            device_db["ttl_{name}_clr"] = {{
                "type": "local",
                "module": "artiq.coredevice.ttl",
                "class": "TTLOut",
                "arguments": {{"channel": 0x{clr_channel:06x}}}
            }}
            device_db["{name}"] = {{
                "type": "local",
                "module": "artiq.coredevice.zotino",
                "class": "Zotino",
                "arguments": {{
                    "spi_device": "spi_{name}",
                    "ldac_device": "ttl_{name}_ldac",
                    "clr_device": "ttl_{name}_clr"
                }}
            }}""",
            name=self.get_name("zotino"),
            spi_channel=rtio_offset,
            ldac_channel=rtio_offset + 1,
            clr_channel=rtio_offset + 2)
        return 3

    def process_grabber(self, rtio_offset, peripheral):
        self.gen("""
            device_db["{name}"] = {{
                "type": "local",
                "module": "artiq.coredevice.grabber",
                "class": "Grabber",
                "arguments": {{"channel_base": 0x{channel:06x}}}
            }}""",
            name=self.get_name("grabber"),
            channel=rtio_offset)
        return 2

    def process_fastino(self, rtio_offset, peripheral):
        self.gen("""
            device_db["{name}"] = {{
                "type": "local",
                "module": "artiq.coredevice.fastino",
                "class": "Fastino",
                "arguments": {{"channel": 0x{channel:06x}, "log2_width": {log2_width}}}
            }}""",
            name=self.get_name("fastino"),
            channel=rtio_offset,
            log2_width=peripheral["log2_width"])
        return 1

    def process_phaser(self, rtio_offset, peripheral):
        mode = peripheral["mode"]
        if mode == "miqro":
            dac = f', "dac": {{"pll_m": 16, "pll_n": 3, "interpolation": 2}}, "gw_rev": {PHASER_GW_MIQRO}'
            n_channels = 3
        else:
            dac = f', "gw_rev": {PHASER_GW_BASE}'
            n_channels = 5
        self.gen("""
            device_db["{name}"] = {{
                "type": "local",
                "module": "artiq.coredevice.phaser",
                "class": "Phaser",
                "arguments": {{
                    "channel_base": 0x{channel:06x},
                    "miso_delay": 1{dac}
                }}
            }}""",
            name=self.get_name("phaser"),
            dac=dac,
            channel=rtio_offset)
        return n_channels

    def process_hvamp(self, rtio_offset, peripheral):
        hvamp_name = self.get_name("hvamp")
        for i in range(8):
            self.gen("""
                device_db["ttl_{name}_sw{ch}"] = {{
                    "type": "local",
                    "module": "artiq.coredevice.ttl",
                    "class": "TTLOut",
                    "arguments": {{"channel": 0x{channel:06x}}}
                }}""",
                name=hvamp_name,
                ch=i,
                channel=rtio_offset+i)
        return 8

    def process_shuttler(self, shuttler_peripheral):
        shuttler_name = self.get_name("shuttler")
        rtio_offset = shuttler_peripheral["drtio_destination"] << 16
        rtio_offset += self.add_board_leds(rtio_offset, board_name=shuttler_name)
        
        channel = count(0)
        self.gen("""
            device_db["{name}_config"] = {{
                "type": "local",
                "module": "artiq.coredevice.shuttler",
                "class": "Config",
                "arguments": {{"channel": 0x{channel:06x}}},
            }}""",
            name=shuttler_name,
            channel=rtio_offset + next(channel))
        self.gen("""
            device_db["{name}_trigger"] = {{
                "type": "local",
                "module": "artiq.coredevice.shuttler",
                "class": "Trigger",
                "arguments": {{"channel": 0x{channel:06x}}},
            }}""",
            name=shuttler_name,
            channel=rtio_offset + next(channel))
        for i in range(16):
            self.gen("""
                device_db["{name}_dcbias{ch}"] = {{
                    "type": "local",
                    "module": "artiq.coredevice.shuttler",
                    "class": "DCBias",
                    "arguments": {{"channel": 0x{channel:06x}}},
                }}""",
                name=shuttler_name,
                ch=i,
                channel=rtio_offset + next(channel))
            self.gen("""
                device_db["{name}_dds{ch}"] = {{
                    "type": "local",
                    "module": "artiq.coredevice.shuttler",
                    "class": "DDS",
                    "arguments": {{"channel": 0x{channel:06x}}},
                }}""",
                name=shuttler_name,
                ch=i,
                channel=rtio_offset + next(channel))

        device_class_names = ["Relay", "ADC"]
        for i, device_name in enumerate(device_class_names):
            spi_name = "{name}_spi{ch}".format(
                name=shuttler_name,
                ch=i)
            self.gen("""
                device_db["{spi}"] = {{
                    "type": "local",
                    "module": "artiq.coredevice.spi2",
                    "class": "SPIMaster",
                    "arguments": {{"channel": 0x{channel:06x}}},
                }}""",
                spi=spi_name,
                channel=rtio_offset + next(channel))
            self.gen("""
                device_db["{name}_{device}"] = {{
                    "type": "local",
                    "module": "artiq.coredevice.shuttler",
                    "class": "{dev_class}",
                    "arguments": {{"spi_device": "{spi}"}},
                }}""",
                name=shuttler_name,
                device=device_name.lower(),
                dev_class=device_name,
                spi=spi_name)
        return 0

    def process(self, rtio_offset, peripheral):
        processor = getattr(self, "process_"+str(peripheral["type"]))
        return processor(rtio_offset, peripheral)

    def add_board_leds(self, rtio_offset, board_name=None, num_leds=2):
        for i in range(num_leds):
            if board_name is None:
                led_name = self.get_name("led")
            else:
                led_name = self.get_name("{}_led".format(board_name))
            self.gen("""
                device_db["{name}"] = {{
                    "type": "local",
                    "module": "artiq.coredevice.ttl",
                    "class": "TTLOut",
                    "arguments": {{"channel": 0x{channel:06x}}}
                }}""",
                name=led_name,
                channel=rtio_offset+i)
        return num_leds


def split_drtio_eem(peripherals):
    # Shuttler is the only peripheral that uses DRTIO-over-EEM at this moment
    drtio_eem_filter = lambda peripheral: peripheral["type"] == "shuttler"
    return filterfalse(drtio_eem_filter, peripherals), \
        list(filter(drtio_eem_filter, peripherals))


def process(output, primary_description, satellites):
    drtio_role = primary_description["drtio_role"]
    if drtio_role not in ("standalone", "master"):
        raise ValueError("Invalid primary node DRTIO role")

    if drtio_role == "standalone" and satellites:
        raise ValueError("A standalone system cannot have satellites")

    process_header(output, primary_description)

    pm = PeripheralManager(output, primary_description)

    local_peripherals, drtio_peripherals = split_drtio_eem(primary_description["peripherals"])

    print("# {} peripherals".format(drtio_role), file=output)
    rtio_offset = 0
    for peripheral in local_peripherals:
        n_channels = pm.process(rtio_offset, peripheral)
        rtio_offset += n_channels

    num_leds = get_num_leds(primary_description)
    pm.add_board_leds(rtio_offset, num_leds=num_leds)
    rtio_offset += num_leds

    for destination, description in satellites:
        if description["drtio_role"] != "satellite":
            raise ValueError("Invalid DRTIO role for satellite at destination {}".format(destination))
        peripherals, satellite_drtio_peripherals = split_drtio_eem(description["peripherals"])
        drtio_peripherals.extend(satellite_drtio_peripherals)

        print(textwrap.dedent("""
            # DEST#{dest} peripherals

            device_db["core"]["arguments"]["satellite_cpu_targets"][{dest}] = \"{target}\"""").format(
                dest=destination,
                target=get_cpu_target(description)),
            file=output)
        rtio_offset = destination << 16
        for peripheral in peripherals:
            n_channels = pm.process(rtio_offset, peripheral)
            rtio_offset += n_channels

        num_leds = get_num_leds(description)
        pm.add_board_leds(rtio_offset, num_leds=num_leds)
        rtio_offset += num_leds

    for i, peripheral in enumerate(drtio_peripherals):
        if not("drtio_destination" in peripheral):
            if primary_description["target"] == "kasli":
                if primary_description["hw_rev"] in ("v1.0", "v1.1"):
                    peripheral["drtio_destination"] = 3 + i
                else:
                    peripheral["drtio_destination"] = 4 + i
            elif primary_description["target"] == "kasli_soc":
                peripheral["drtio_destination"] = 5 + i
            else:
                raise NotImplementedError
        print(textwrap.dedent("""
            # DEST#{dest} peripherals

            device_db["core"]["arguments"]["satellite_cpu_targets"][{dest}] = \"{target}\"""").format(
                dest=peripheral["drtio_destination"],
                target=get_cpu_target(peripheral)),
            file=output)
        processor = getattr(pm, "process_"+str(peripheral["type"]))
        processor(peripheral)


def get_argparser(): 
    parser = argparse.ArgumentParser(
        description="ARTIQ device database template builder")
    parser.add_argument("--version", action="version",
                        version="ARTIQ v{}".format(artiq_version),
                        help="print the ARTIQ version number")
    parser.add_argument("primary_description", metavar="PRIMARY_DESCRIPTION",
                        help="JSON system description file for the primary (standalone or master) node")
    parser.add_argument("-o", "--output",
                        help="output file, defaults to standard output if omitted")
    parser.add_argument("-s", "--satellite", nargs=2, action="append",
                        default=[], metavar=("DESTINATION", "DESCRIPTION"), type=str,
                        help="add DRTIO satellite at the given destination number with "
                             "devices from the given JSON description")
    return parser


def main():
    args = get_argparser().parse_args()

    primary_description = jsondesc.load(args.primary_description)

    satellites = []
    for destination, description_path in args.satellite:
        satellite_description = jsondesc.load(description_path)
        satellites.append((int(destination, 0), satellite_description))

    if args.output is not None:
        with open(args.output, "w") as f:
            process(f, primary_description, satellites)
    else:
        process(sys.stdout, primary_description, satellites)


if __name__ == "__main__":
    main()